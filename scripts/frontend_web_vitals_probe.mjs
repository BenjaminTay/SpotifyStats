#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'

const DEFAULT_ROUTES = ['/', '/analysis/stats', '/analysis/charts', '/billboard/number-ones', '/account', '/settings']
const DEFAULT_BASE_URL = 'http://127.0.0.1:5173'
const DEFAULT_WAIT_MS = 5000
const REWRITE_PATH_PREFIXES = ['/api', '/covers']

const VIEWPORTS = {
  desktop: {
    width: 1280,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
  },
  mobile: {
    width: 390,
    height: 844,
    deviceScaleFactor: 3,
    mobile: true,
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  },
}

const VITALS_OBSERVER = `
(() => {
  window.__codexVitals = { cls: 0, lcp: 0, fid: null, firstInput: null, longTasks: [] };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.__codexVitals.lcp = entry.renderTime || entry.loadTime || entry.startTime || 0;
      }
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {}
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) window.__codexVitals.cls += entry.value || 0;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch {}
  try {
    new PerformanceObserver((list) => {
      const entry = list.getEntries()[0];
      if (entry && window.__codexVitals.fid == null) {
        window.__codexVitals.fid = Math.max(0, entry.processingStart - entry.startTime);
        window.__codexVitals.firstInput = {
          name: entry.name,
          startTime: entry.startTime,
          processingStart: entry.processingStart,
          duration: entry.duration,
        };
      }
    }).observe({ type: 'first-input', buffered: true });
  } catch {}
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.__codexVitals.longTasks.push({
          startTime: entry.startTime,
          duration: entry.duration,
        });
      }
    }).observe({ type: 'longtask', buffered: true });
  } catch {}
})();
`

const METRICS_EXPRESSION = `
(() => {
  const nav = performance.getEntriesByType('navigation')[0];
  const paints = Object.fromEntries(performance.getEntriesByType('paint').map((entry) => [entry.name, entry.startTime]));
  const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
  const lcpEntry = lcpEntries[lcpEntries.length - 1];
  const resources = performance.getEntriesByType('resource');
  const vitals = window.__codexVitals || {};
  const fcp = paints['first-contentful-paint'] || 0;
  const tbt = (vitals.longTasks || [])
    .filter((entry) => entry.startTime >= fcp && entry.startTime <= 5000)
    .reduce((sum, entry) => sum + Math.max(0, entry.duration - 50), 0);

  return {
    url: location.href,
    title: document.title,
    lcp: (lcpEntry && (lcpEntry.renderTime || lcpEntry.loadTime || lcpEntry.startTime)) || vitals.lcp || null,
    cls: vitals.cls || 0,
    fid: vitals.fid,
    firstInput: vitals.firstInput,
    tbtApprox: tbt,
    fcp,
    domContentLoaded: nav ? nav.domContentLoadedEventEnd : null,
    load: nav ? nav.loadEventEnd : null,
    responseEnd: nav ? nav.responseEnd : null,
    transferKB: nav ? Math.round((nav.transferSize || 0) / 102.4) / 10 : null,
    encodedResourceKB: Math.round(resources.reduce((sum, entry) => sum + (entry.encodedBodySize || 0), 0) / 102.4) / 10,
    resourceCount: resources.length,
    bodyScrollWidth: document.body ? document.body.scrollWidth : null,
    documentScrollWidth: document.documentElement ? document.documentElement.scrollWidth : null,
    viewportWidth: innerWidth,
  };
})();
`

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBaseUrl: null,
    routes: DEFAULT_ROUTES,
    waitMs: DEFAULT_WAIT_MS,
    viewports: ['desktop', 'mobile'],
    output: null,
    chrome: null,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
    else if (arg === '--routes') args.routes = argv[++i].split(',').map((route) => route.trim()).filter(Boolean)
    else if (arg === '--wait-ms') args.waitMs = Number(argv[++i])
    else if (arg === '--viewport') {
      const value = argv[++i]
      args.viewports = value === 'both' ? ['desktop', 'mobile'] : [value]
    } else if (arg === '--output') args.output = argv[++i]
    else if (arg === '--chrome') args.chrome = argv[++i]
    else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  for (const viewport of args.viewports) {
    if (!VIEWPORTS[viewport]) throw new Error(`Unsupported viewport: ${viewport}`)
  }

  if (!Number.isFinite(args.waitMs) || args.waitMs < 1000) {
    throw new Error('--wait-ms must be at least 1000')
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_web_vitals_probe.mjs [options]

Options:
  --base-url <url>       Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>   Rewrite same-origin /api and /covers requests to this API URL
  --routes <a,b,c>       Comma-separated route paths, default ${DEFAULT_ROUTES.join(',')}
  --viewport <mode>      desktop, mobile, or both, default both
  --wait-ms <ms>         Wait after load before reading metrics, default ${DEFAULT_WAIT_MS}
  --output <path>        Write JSON results to a file
  --chrome <path>        Chrome/Chromium executable path
`)
}

function findChrome(explicitPath) {
  const candidates = [
    explicitPath,
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ].filter(Boolean)

  const match = candidates.find((candidate) => existsSync(candidate))
  if (!match) {
    throw new Error('Chrome/Chromium executable not found. Pass --chrome or set CHROME_PATH.')
  }
  return match
}

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

async function waitForJson(url, timeoutMs = 10000) {
  const started = Date.now()
  let lastError
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return response.json()
      lastError = new Error(`HTTP ${response.status}`)
    } catch (error) {
      lastError = error
    }
    await sleep(150)
  }
  throw lastError || new Error(`Timed out waiting for ${url}`)
}

async function createTarget(port) {
  const base = `http://127.0.0.1:${port}`
  for (const method of ['PUT', 'GET']) {
    const response = await fetch(`${base}/json/new?${encodeURIComponent('about:blank')}`, { method })
    if (response.ok) return response.json()
  }
  const list = await waitForJson(`${base}/json/list`)
  if (list[0]) return list[0]
  throw new Error('Could not create or find a Chrome target')
}

function rewriteRequestUrl(requestUrl, frontendBaseUrl, apiBaseUrl) {
  if (!apiBaseUrl) return null
  const frontendOrigin = new URL(frontendBaseUrl).origin
  const apiOrigin = new URL(apiBaseUrl).origin
  if (frontendOrigin === apiOrigin) return null

  let url
  try {
    url = new URL(requestUrl)
  } catch {
    return null
  }
  if (url.origin !== frontendOrigin) return null
  const shouldRewrite = REWRITE_PATH_PREFIXES.some((prefix) => (
    url.pathname === prefix || url.pathname.startsWith(`${prefix}/`)
  ))
  if (!shouldRewrite) return null

  return new URL(`${url.pathname}${url.search}${url.hash}`, apiBaseUrl).toString()
}

async function setupApiRequestRewrite(client, frontendBaseUrl, apiBaseUrl) {
  if (!apiBaseUrl) return

  client.on('Fetch.requestPaused', (params) => {
    const rewrittenUrl = rewriteRequestUrl(params.request.url, frontendBaseUrl, apiBaseUrl)
    const request = rewrittenUrl
      ? { requestId: params.requestId, url: rewrittenUrl }
      : { requestId: params.requestId }
    void client.send('Fetch.continueRequest', request).catch(() => {})
  })

  await client.send('Fetch.enable', {
    patterns: [{ urlPattern: '*', requestStage: 'Request' }],
  })
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
      const { resolve, reject } = this.pending.get(message.id)
      this.pending.delete(message.id)
      if (message.error) reject(new Error(message.error.message))
      else resolve(message.result)
      return
    }

    const handlers = this.handlers.get(message.method) || []
    for (const handler of handlers) handler(message.params || {})
  }

  send(method, params = {}) {
    const id = this.nextId
    this.nextId += 1
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`CDP call timed out: ${method}`))
        }
      }, 15000)
    })
  }

  once(method, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const handler = (params) => {
        clearTimeout(timer)
        const next = (this.handlers.get(method) || []).filter((item) => item !== handler)
        this.handlers.set(method, next)
        resolve(params)
      }
      const timer = setTimeout(() => {
        const next = (this.handlers.get(method) || []).filter((item) => item !== handler)
        this.handlers.set(method, next)
        reject(new Error(`Timed out waiting for ${method}`))
      }, timeoutMs)
      this.handlers.set(method, [...(this.handlers.get(method) || []), handler])
    })
  }

  on(method, handler) {
    this.handlers.set(method, [...(this.handlers.get(method) || []), handler])
  }

  close() {
    this.ws.close()
  }
}

async function measureRoute({ port, baseUrl, apiBaseUrl, route, viewportName, waitMs }) {
  const viewport = VIEWPORTS[viewportName]
  const target = await createTarget(port)
  const client = await new CdpClient(target.webSocketDebuggerUrl).connect()

  try {
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Network.enable')
    await setupApiRequestRewrite(client, baseUrl, apiBaseUrl)
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: viewport.deviceScaleFactor,
      mobile: viewport.mobile,
    })
    await client.send('Emulation.setUserAgentOverride', { userAgent: viewport.userAgent })
    await client.send('Page.addScriptToEvaluateOnNewDocument', { source: VITALS_OBSERVER })

    const url = new URL(route, baseUrl).toString()
    const loadEvent = client.once('Page.loadEventFired', 30000)
    await client.send('Page.navigate', { url })
    await loadEvent
    await sleep(waitMs)

    await client.send('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      x: Math.floor(viewport.width / 2),
      y: Math.floor(viewport.height / 2),
      button: 'left',
      clickCount: 1,
    })
    await client.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      x: Math.floor(viewport.width / 2),
      y: Math.floor(viewport.height / 2),
      button: 'left',
      clickCount: 1,
    })
    await sleep(500)

    const result = await client.send('Runtime.evaluate', {
      expression: METRICS_EXPRESSION,
      returnByValue: true,
      awaitPromise: true,
    })

    return {
      route,
      viewport: viewportName,
      ...roundMetrics(result.result.value),
    }
  } finally {
    client.close()
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(() => {})
  }
}

function roundMetrics(result) {
  const numeric = [
    'lcp',
    'cls',
    'fid',
    'tbtApprox',
    'fcp',
    'domContentLoaded',
    'load',
    'responseEnd',
  ]
  for (const key of numeric) {
    if (typeof result[key] === 'number') {
      result[key] = Math.round(result[key] * 10) / 10
    }
  }
  return result
}

function renderMarkdown(results) {
  const lines = [
    '# Frontend Web Vitals Probe',
    '',
    `> Generated: ${new Date().toISOString()}`,
    '',
    '| Route | Viewport | LCP | CLS | FID | TBT approx | FCP | DCL | Load | Resources | Encoded resources | Scroll width |',
    '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  ]

  for (const row of results) {
    const fid = row.fid == null ? 'n/a' : `${row.fid}ms`
    const scrollWidth = `${row.documentScrollWidth ?? 'n/a'} / ${row.viewportWidth ?? 'n/a'}`
    lines.push(
      `| \`${row.route}\` | ${row.viewport} | ${formatMs(row.lcp)} | ${row.cls} | ${fid} | ${formatMs(row.tbtApprox)} | ${formatMs(row.fcp)} | ${formatMs(row.domContentLoaded)} | ${formatMs(row.load)} | ${row.resourceCount} | ${row.encodedResourceKB}KB | ${scrollWidth} |`,
    )
  }

  lines.push('')
  lines.push('Notes:')
  lines.push('- LCP/CLS are collected with PerformanceObserver in headless Chrome.')
  lines.push('- FID is only present if Chrome exposes a first-input entry for the synthetic click; use TBT approx as the lab proxy when FID is n/a.')
  lines.push('- TBT approx sums long tasks over 50ms from FCP through the first 5 seconds after navigation.')
  return lines.join('\n')
}

function formatMs(value) {
  if (value == null) return 'n/a'
  return `${value}ms`
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const chromePath = findChrome(args.chrome)
  const port = await getFreePort()
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-stats-chrome-'))

  const chrome = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    '--disable-background-networking',
    '--disable-extensions',
    '--disable-dev-shm-usage',
    '--hide-scrollbars',
    '--mute-audio',
    '--no-default-browser-check',
    '--no-first-run',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: 'ignore' })

  const cleanup = async () => {
    chrome.kill('SIGTERM')
    await rm(profileDir, { recursive: true, force: true }).catch(() => {})
  }

  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`)

    const results = []
    for (const route of args.routes) {
      for (const viewport of args.viewports) {
        process.stderr.write(`Measuring ${route} (${viewport}) ... `)
        const result = await measureRoute({
          port,
          baseUrl: args.baseUrl,
          apiBaseUrl: args.apiBaseUrl,
          route,
          viewportName: viewport,
          waitMs: args.waitMs,
        })
        results.push(result)
        process.stderr.write(`LCP=${formatMs(result.lcp)} CLS=${result.cls} TBT=${formatMs(result.tbtApprox)}\n`)
      }
    }

    const markdown = renderMarkdown(results)
    console.log(markdown)

    if (args.output) {
      await writeFile(args.output, `${JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2)}\n`)
      console.error(`JSON written to ${args.output}`)
    }
  } finally {
    await cleanup()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
