#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findHeadedChrome } from './lib/chrome_executable.mjs'

const DEFAULT_ROUTES = [
  '/',
  '/analysis/stats',
  '/analysis/charts',
  '/analysis/records',
  '/music/search?q=Taylor%20Swift',
  '/music/tracks/48616',
  '/music/album-projects/42947?artist=Olivia%20Rodrigo',
  '/music/artists/JJ%20Lin',
  '/billboard',
  '/billboard/number-ones',
  '/billboard/all-time',
  '/billboard/records',
  '/community',
  '/account',
  '/yearly-review?year=2026',
]

function parseArgs(argv) {
  const args = {
    baseUrl: 'http://127.0.0.1:4173',
    rounds: 3,
    roundSeconds: 1200,
    stableSeconds: 300,
    sampleSeconds: 10,
    routes: DEFAULT_ROUTES,
    output: null,
    browserPidFile: null,
    phaseFile: null,
    chrome: null,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const option = argv[index]
    if (option === '--base-url') args.baseUrl = argv[++index]
    else if (option === '--rounds') args.rounds = Number(argv[++index])
    else if (option === '--round-seconds') args.roundSeconds = Number(argv[++index])
    else if (option === '--stable-seconds') args.stableSeconds = Number(argv[++index])
    else if (option === '--sample-seconds') args.sampleSeconds = Number(argv[++index])
    else if (option === '--routes') {
      args.routes = argv[++index].split(',').map((route) => route.trim()).filter(Boolean)
    } else if (option === '--output') args.output = argv[++index]
    else if (option === '--browser-pid-file') args.browserPidFile = argv[++index]
    else if (option === '--phase-file') args.phaseFile = argv[++index]
    else if (option === '--chrome') args.chrome = argv[++index]
    else if (option === '--help' || option === '-h') {
      console.log(`Usage: node scripts/frontend_runtime_soak.mjs [options]

Runs repeated interactions in one SPA document and verifies a real hidden tab.

  --base-url <url>          Loopback frontend URL
  --rounds <n>              Repeated rounds, default 3
  --round-seconds <seconds> Total duration per round, default 1200
  --stable-seconds <sec>    Hidden stable window at each round end, default 300
  --sample-seconds <sec>    Stable-window sample interval, default 10
  --routes <a,b,c>          Fixed route set; each route is visited twice per round
  --output <path>           Required JSON evidence path
  --browser-pid-file <path> Browser root PID for the process resource probe
  --phase-file <path>       Publish interaction/hidden phase labels for resource samples
  --chrome <path>           Chrome/Chromium executable
`)
      process.exit(0)
    } else throw new Error(`Unknown option: ${option}`)
  }
  const parsed = new URL(args.baseUrl)
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)) {
    throw new Error('--base-url must be loopback')
  }
  for (const [name, value] of [
    ['rounds', args.rounds],
    ['round-seconds', args.roundSeconds],
    ['stable-seconds', args.stableSeconds],
    ['sample-seconds', args.sampleSeconds],
  ]) {
    if (!Number.isFinite(value) || value <= 0) throw new Error(`--${name} must be positive`)
  }
  if (!args.output) throw new Error('--output is required')
  if (!args.routes.length) throw new Error('--routes must not be empty')
  if (args.stableSeconds >= args.roundSeconds) {
    throw new Error('--stable-seconds must be less than --round-seconds')
  }
  return args
}

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      server.close(() => resolve(address.port))
    })
  })
}

async function fetchJson(url, options, timeoutMs = 15000) {
  const started = Date.now()
  let error
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url, options)
      if (response.ok) return response.json()
      error = new Error(`HTTP ${response.status}: ${url}`)
    } catch (caught) {
      error = caught
    }
    await sleep(100)
  }
  throw error || new Error(`Timed out: ${url}`)
}

async function createTarget(port, url) {
  const endpoint = `http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`
  for (const method of ['PUT', 'GET']) {
    try {
      return await fetchJson(endpoint, { method }, 1000)
    } catch {}
  }
  throw new Error(`Could not create browser target: ${url}`)
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.nextId = 1
    this.pending = new Map()
    this.handlers = new Map()
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl)
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true })
      this.ws.addEventListener('error', reject, { once: true })
    })
    this.ws.addEventListener('message', (event) => this.handleMessage(event))
    return this
  }

  handleMessage(event) {
    const message = JSON.parse(event.data)
    if (message.id && this.pending.has(message.id)) {
      const pending = this.pending.get(message.id)
      clearTimeout(pending.timer)
      this.pending.delete(message.id)
      if (message.error) pending.reject(new Error(message.error.message))
      else pending.resolve(message.result)
      return
    }
    for (const handler of this.handlers.get(message.method) || []) handler(message.params || {})
  }

  send(method, params = {}) {
    const id = this.nextId++
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`CDP call timed out: ${method}`))
      }, 15000)
      this.pending.set(id, { resolve, reject, timer })
    })
  }

  on(method, handler) {
    this.handlers.set(method, [...(this.handlers.get(method) || []), handler])
  }

  close() {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(new Error('CDP closed'))
    }
    this.pending.clear()
    this.ws.close()
  }
}

async function evaluate(client, expression) {
  const response = await client.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.text || 'Runtime.evaluate failed')
  }
  return response.result.value
}

async function waitForApp(client, expectedUrl, activeApiRequests, timeoutMs = 20000) {
  const expected = new URL(expectedUrl)
  const deadline = Date.now() + timeoutMs
  let settledSince = null
  let state
  while (Date.now() < deadline) {
    state = await evaluate(client, `(() => {
      const main = document.querySelector('main') || document.body
      const visibleAlerts = [...document.querySelectorAll('[role="alert"]')]
        .filter((node) => node.getBoundingClientRect().height > 0)
        .map((node) => node.textContent || '')
      return {
        href: location.href,
        path: location.pathname + location.search,
        mainTextLength: (main?.innerText || '').length,
        visibleAlerts,
      }
    })()`)
    const settled = (
      state.path === expected.pathname + expected.search
      && state.mainTextLength > 0
      && activeApiRequests.size === 0
    )
    if (settled) {
      settledSince ??= Date.now()
      if (Date.now() - settledSince >= 300) return state
    } else {
      settledSince = null
    }
    await sleep(100)
  }
  throw new Error(`SPA route did not settle: ${expected.pathname}${expected.search}; ${JSON.stringify(state)}`)
}

async function metrics(client, phase, round, apiRequestCount) {
  const [heap, dom, page] = await Promise.all([
    client.send('Runtime.getHeapUsage'),
    client.send('Memory.getDOMCounters'),
    evaluate(client, `(() => ({
      href: location.href,
      visibility: document.visibilityState,
      timeOrigin: performance.timeOrigin,
      navigationEntries: performance.getEntriesByType('navigation').length,
      resourceEntries: performance.getEntriesByType('resource').length,
      bodyTextLength: document.body?.innerText?.length || 0,
    }))()`),
  ])
  return {
    timestamp: Date.now(),
    phase,
    round,
    apiRequestCount,
    usedHeapBytes: heap.usedSize,
    totalHeapBytes: heap.totalSize,
    documents: dom.documents,
    domNodes: dom.nodes,
    eventListeners: dom.jsEventListeners,
    ...page,
  }
}

async function waitForVisibility(client, expected, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs
  let observed
  while (Date.now() < deadline) {
    observed = await evaluate(client, 'document.visibilityState')
    if (observed === expected) return observed
    await sleep(100)
  }
  throw new Error(`visibilityState did not become ${expected}; observed ${observed}`)
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

function summarizeStable(samples) {
  return {
    samples: samples.length,
    usedHeapBytesMedian: median(samples.map((sample) => sample.usedHeapBytes)),
    domNodesMedian: median(samples.map((sample) => sample.domNodes)),
    eventListenersMedian: median(samples.map((sample) => sample.eventListeners)),
    resourceEntriesMedian: median(samples.map((sample) => sample.resourceEntries)),
    apiRequestsDuringWindow: samples.at(-1).apiRequestCount - samples[0].apiRequestCount,
    visibilityStates: [...new Set(samples.map((sample) => sample.visibility))].sort(),
  }
}

async function spaNavigate(client, baseUrl, route) {
  const destination = new URL(route, baseUrl).toString()
  await evaluate(client, `(() => {
    const destination = ${JSON.stringify(destination)}
    history.pushState({}, '', destination)
    window.dispatchEvent(new PopStateEvent('popstate', { state: history.state }))
    window.scrollTo(0, 0)
  })()`)
  return destination
}

async function exerciseRoute(client) {
  await evaluate(client, `(() => {
    window.scrollTo(0, Math.min(document.documentElement.scrollHeight, 1200))
    const tabs = [...document.querySelectorAll('[role="tab"]')]
      .filter((node) => !node.disabled && node.getAttribute('aria-selected') !== 'true')
    if (tabs[0]) tabs[0].click()
    window.scrollTo(0, 0)
    return { clickedTab: Boolean(tabs[0]) }
  })()`)
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const debugPort = await getFreePort()
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-runtime-soak-chrome-'))
  const chrome = spawn(findHeadedChrome(args.chrome), [
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--mute-audio',
    '--no-proxy-server',
    '--no-default-browser-check',
    '--no-first-run',
    '--window-size=1280,900',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: 'ignore' })
  if (args.browserPidFile) await writeFile(args.browserPidFile, String(chrome.pid))
  if (args.phaseFile) await writeFile(args.phaseFile, 'soak_start')

  let browserClient
  let pageClient
  let pageTarget
  let backgroundTarget
  const cleanup = async () => {
    pageClient?.close()
    browserClient?.close()
    chrome.kill('SIGTERM')
    if (chrome.exitCode == null && chrome.signalCode == null) {
      await Promise.race([
        new Promise((resolve) => chrome.once('exit', resolve)),
        sleep(5000),
      ])
    }
    if (chrome.exitCode == null && chrome.signalCode == null) chrome.kill('SIGKILL')
    await rm(profileDir, { recursive: true, force: true })
    if (args.browserPidFile) await rm(args.browserPidFile, { force: true })
  }
  const onSignal = () => { void cleanup().finally(() => process.exit(130)) }
  process.once('SIGINT', onSignal)
  process.once('SIGTERM', onSignal)

  const requests = []
  const activeApiRequests = new Set()
  const consoleErrors = []
  const failures = []
  const rounds = []
  try {
    const version = await fetchJson(`http://127.0.0.1:${debugPort}/json/version`)
    browserClient = await new CdpClient(version.webSocketDebuggerUrl).connect()
    pageTarget = await createTarget(debugPort, args.baseUrl)
    backgroundTarget = await createTarget(debugPort, 'about:blank')
    pageClient = await new CdpClient(pageTarget.webSocketDebuggerUrl).connect()
    await pageClient.send('Page.enable')
    await pageClient.send('Runtime.enable')
    await pageClient.send('Network.enable')
    await pageClient.send('Memory.enable').catch(() => {})
    pageClient.on('Fetch.requestPaused', (event) => {
      const url = new URL(event.request.url)
      const allowed = ['http:', 'https:'].includes(url.protocol)
        && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
        && ['GET', 'HEAD'].includes(event.request.method)
      const command = allowed
        ? pageClient.send('Fetch.continueRequest', { requestId: event.requestId })
        : pageClient.send('Fetch.failRequest', { requestId: event.requestId, errorReason: 'BlockedByClient' })
      void command.catch(() => {})
    })
    pageClient.on('Runtime.exceptionThrown', (event) => {
      consoleErrors.push({ timestamp: Date.now(), type: 'exception', text: event.exceptionDetails.text })
    })
    pageClient.on('Runtime.consoleAPICalled', (event) => {
      if (event.type === 'error') {
        consoleErrors.push({
          timestamp: Date.now(),
          type: 'console',
          text: event.args.map((argument) => argument.value || argument.description || '').join(' '),
        })
      }
    })
    pageClient.on('Network.requestWillBeSent', (event) => {
      const api = new URL(event.request.url).pathname.startsWith('/api/')
      requests.push({
        requestId: event.requestId,
        timestamp: Date.now(),
        url: event.request.url,
        method: event.request.method,
        type: event.type,
        api,
        status: null,
        error: null,
      })
      if (api) activeApiRequests.add(event.requestId)
    })
    const requestFor = (requestId) => requests.findLast((request) => request.requestId === requestId)
    pageClient.on('Network.responseReceived', (event) => {
      const request = requestFor(event.requestId)
      if (request) request.status = event.response.status
    })
    pageClient.on('Network.loadingFinished', (event) => activeApiRequests.delete(event.requestId))
    pageClient.on('Network.loadingFailed', (event) => {
      const request = requestFor(event.requestId)
      if (request) request.error = event.errorText
      activeApiRequests.delete(event.requestId)
    })

    await browserClient.send('Target.activateTarget', { targetId: pageTarget.id })
    await pageClient.send('Page.navigate', { url: args.baseUrl })
    await waitForApp(pageClient, args.baseUrl, activeApiRequests)
    await pageClient.send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] })
    const baseline = await metrics(pageClient, 'baseline', 0, requests.filter((item) => item.api).length)
    const timeOrigin = baseline.timeOrigin
    const routeSequence = [...args.routes, ...args.routes]
    const interactionSeconds = args.roundSeconds - args.stableSeconds
    const dwellMs = interactionSeconds * 1000 / routeSequence.length

    for (let roundNumber = 1; roundNumber <= args.rounds; roundNumber += 1) {
      if (args.phaseFile) await writeFile(args.phaseFile, `soak_round_${roundNumber}_interaction`)
      const round = { round: roundNumber, startedAt: Date.now(), visits: [], stable: [] }
      for (const route of routeSequence) {
        const visitStarted = Date.now()
        const destination = await spaNavigate(pageClient, args.baseUrl, route)
        const ready = await waitForApp(pageClient, destination, activeApiRequests)
        await exerciseRoute(pageClient)
        const visitMetrics = await metrics(
          pageClient,
          'interaction',
          roundNumber,
          requests.filter((item) => item.api).length,
        )
        round.visits.push({ route, ready, ...visitMetrics })
        if (visitMetrics.timeOrigin !== timeOrigin || visitMetrics.navigationEntries !== 1) {
          failures.push(`round ${roundNumber} ${route}: document navigation reset detected`)
        }
        const remaining = dwellMs - (Date.now() - visitStarted)
        if (remaining > 0) await sleep(remaining)
      }

      await spaNavigate(pageClient, args.baseUrl, '/music/search?q=Taylor%20Swift')
      await waitForApp(pageClient, new URL('/music/search?q=Taylor%20Swift', args.baseUrl), activeApiRequests)
      if (args.phaseFile) await writeFile(args.phaseFile, `soak_round_${roundNumber}_hidden`)
      await browserClient.send('Target.activateTarget', { targetId: backgroundTarget.id })
      try {
        await waitForVisibility(pageClient, 'hidden')
      } catch (error) {
        failures.push(`round ${roundNumber}: ${error.message}`)
      }
      const hiddenDeadline = Date.now() + args.stableSeconds * 1000
      while (Date.now() < hiddenDeadline) {
        const sample = await metrics(
          pageClient,
          'hidden_stable',
          roundNumber,
          requests.filter((item) => item.api).length,
        )
        round.stable.push(sample)
        if (sample.visibility !== 'hidden') {
          failures.push(`round ${roundNumber}: expected hidden, got ${sample.visibility}`)
          break
        }
        await sleep(Math.min(args.sampleSeconds * 1000, Math.max(0, hiddenDeadline - Date.now())))
      }
      await browserClient.send('Target.activateTarget', { targetId: pageTarget.id })
      try {
        await waitForVisibility(pageClient, 'visible')
      } catch (error) {
        failures.push(`round ${roundNumber}: ${error.message}`)
      }
      const visible = await metrics(
        pageClient,
        'visible_again',
        roundNumber,
        requests.filter((item) => item.api).length,
      )
      if (visible.visibility !== 'visible') {
        failures.push(`round ${roundNumber}: application tab did not become visible again`)
      }
      round.stableSummary = summarizeStable(round.stable)
      round.visibleAgain = visible
      round.endedAt = Date.now()
      rounds.push(round)
      process.stderr.write(`round ${roundNumber}/${args.rounds} complete\n`)
    }
    if (args.phaseFile) await writeFile(args.phaseFile, 'soak_complete')

    const blockedMutatingRequests = requests.filter((request) => (
      request.api
      && !['GET', 'HEAD'].includes(request.method)
      && request.error?.startsWith('net::ERR_BLOCKED_BY_CLIENT')
    ))
    const apiFailures = requests.filter((request) => (
      request.api
      && !blockedMutatingRequests.includes(request)
      && (request.error || (request.status != null && request.status >= 400))
    ))
    if (apiFailures.length) failures.push(`${apiFailures.length} API requests failed`)
    if (consoleErrors.length) failures.push(`${consoleErrors.length} console/runtime errors observed`)
    const report = {
      schemaVersion: 1,
      tool: 'frontend_runtime_soak',
      generatedAt: new Date().toISOString(),
      browser: { pid: chrome.pid, headed: true, targetLifecycle: 'one application target' },
      configuration: {
        baseUrl: args.baseUrl,
        rounds: args.rounds,
        roundSeconds: args.roundSeconds,
        stableSeconds: args.stableSeconds,
        sampleSeconds: args.sampleSeconds,
        routes: args.routes,
        visitsPerRound: routeSequence.length,
      },
      baseline,
      rounds,
      requests,
      blockedMutatingRequests,
      consoleErrors,
      failures,
      success: failures.length === 0,
    }
    await writeFile(args.output, `${JSON.stringify(report, null, 2)}\n`)
    console.log(JSON.stringify({
      success: report.success,
      rounds: rounds.map((round) => ({
        round: round.round,
        visits: round.visits.length,
        stable: round.stableSummary,
      })),
      apiRequests: requests.filter((request) => request.api).length,
      blockedMutatingRequests: blockedMutatingRequests.length,
      failures,
    }, null, 2))
    if (!report.success) process.exitCode = 1
  } finally {
    process.removeListener('SIGINT', onSignal)
    process.removeListener('SIGTERM', onSignal)
    await cleanup()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
