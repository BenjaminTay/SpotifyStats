#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 5000
const DYNAMIC_ROUTE_WAIT_MS = 12000
const DEFAULT_MAX_SCROLL_OVERFLOW = 0
const REWRITE_PATH_PREFIXES = ['/api', '/covers']
const DETAIL_ROUTE_FILTERS = {
  min_ms: 30000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: true,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  merge_level: 2,
}
const DEFAULT_ROUTES = [
  '/',
  '/analysis',
  '/analysis/stats',
  '/analysis/charts',
  '/analysis/records',
  '/analysis/timeline',
  '/analysis/leaderboard',
  '/analysis/behavior',
  '/analysis/listening-hours',
  '/analysis/artists',
  '/yearly-review',
  '/billboard',
  '/billboard/number-ones',
  '/billboard/all-time',
  '/billboard/year-end',
  '/billboard/records',
  '/billboard/versus',
  '/community',
  '/ai-insights',
  '/account',
  '/settings',
]

const ROUTE_READY_MARKERS = {
  '/': ['DASHBOARD /', '总播放次数'],
  '/analysis': ['PERSONAL STATS', '总体播放统计'],
  '/analysis/stats': ['PERSONAL STATS', '总体播放统计'],
  '/analysis/charts': ['PERSONAL CHARTS', '个人排行榜'],
  '/analysis/records': ['PLAYBACK RECORDS', '狂热时刻'],
  '/analysis/timeline': ['PERSONAL STATS', '总体播放统计'],
  '/analysis/leaderboard': ['PERSONAL CHARTS', '个人排行榜'],
  '/analysis/behavior': ['PERSONAL STATS', '总体播放统计'],
  '/analysis/listening-hours': ['PERSONAL STATS', '总体播放统计'],
  '/analysis/artists': ['PERSONAL CHARTS', '个人排行榜'],
  '/yearly-review': ['YEARLY / REVIEW', '听歌人格'],
  '/billboard': ['CHART / WEEKLY', 'Billboard 周榜'],
  '/billboard/number-ones': ['CHART / NUMBER ONES', '每周冠军歌曲'],
  '/billboard/all-time': ['CHART / ALL-TIME', 'Billboard 总榜'],
  '/billboard/year-end': ['CHART / YEAR-END', 'Billboard 年榜'],
  '/billboard/records': ['CHART / HALL OF FAME', '冠军圣殿'],
  '/billboard/versus': ['CHART / VERSUS', '请搜索并添加歌曲开始对决'],
  '/community': ['COMMUNITY / FEED', '榜单社区'],
  '/ai-insights': ['AI / INSIGHTS', 'AI 洞察'],
  '/account': ['ACCOUNT / CENTER', '你的收藏'],
  '/settings': ['设置', 'Spotify 连接'],
}

const DYNAMIC_ROUTE_READY_MARKERS = [
  { pattern: /^\/music\/tracks\/[^/]+$/, markers: ['单曲详情', '播放统计'] },
  { pattern: /^\/music\/albums\/[^/]+$/, markers: ['专辑详情', '播放统计'] },
  { pattern: /^\/music\/artists\/[^/]+$/, markers: ['艺人详情', '播放统计'] },
  { pattern: /^\/community\/post\/[^/]+$/, markers: ['COMMUNITY / POST'] },
  { pattern: /^\/community\/account\/[^/]+$/, markers: ['COMMUNITY / ACCOUNT', 'Posts'] },
]

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

const PAGE_STATE_EXPRESSION = `
(() => {
  const root = document.querySelector('#root');
  const bodyText = document.body ? document.body.innerText : '';
  const rootText = root ? root.textContent || '' : '';
  const bodyScrollWidth = document.body ? document.body.scrollWidth : 0;
  const documentScrollWidth = document.documentElement ? document.documentElement.scrollWidth : 0;
  const selectors = [
    'vite-error-overlay',
    '#webpack-dev-server-client-overlay',
  ];

  return {
    title: document.title,
    readyState: document.readyState,
    bodyText,
    bodyTextSample: bodyText.slice(0, 800),
    rootTextLength: rootText.trim().length,
    bodyScrollWidth,
    documentScrollWidth,
    viewportWidth: window.innerWidth,
    hasDevOverlay: selectors.some((selector) => Boolean(document.querySelector(selector))),
    hasFatalText: /Internal Server Error|Failed to fetch dynamically imported module|ReferenceError|TypeError|Unhandled Runtime Error/.test(bodyText),
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
    maxScrollOverflow: DEFAULT_MAX_SCROLL_OVERFLOW,
    failOnConsoleWarning: false,
    enforceRouteMarkers: true,
    includeDetailRoutes: false,
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
    else if (arg === '--max-scroll-overflow') args.maxScrollOverflow = Number(argv[++i])
    else if (arg === '--fail-on-console-warning') args.failOnConsoleWarning = true
    else if (arg === '--disable-route-markers') args.enforceRouteMarkers = false
    else if (arg === '--include-detail-routes') args.includeDetailRoutes = true
    else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (args.routes.length === 0) throw new Error('--routes must include at least one route')
  if (!Number.isFinite(args.waitMs) || args.waitMs < 500) throw new Error('--wait-ms must be at least 500')
  if (!Number.isFinite(args.maxScrollOverflow) || args.maxScrollOverflow < 0) {
    throw new Error('--max-scroll-overflow must be a non-negative number')
  }
  for (const viewport of args.viewports) {
    if (!VIEWPORTS[viewport]) throw new Error(`Unsupported viewport: ${viewport}`)
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_route_smoke.mjs [options]

Options:
  --base-url <url>              Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>          Rewrite same-origin /api and /covers requests to this API URL
  --routes <a,b,c>              Comma-separated route paths, default ${DEFAULT_ROUTES.join(',')}
  --viewport <mode>             desktop, mobile, or both, default both
  --wait-ms <ms>                Wait after load before reading page state, default ${DEFAULT_WAIT_MS}
  --max-scroll-overflow <px>    Allowed horizontal overflow over viewport width, default ${DEFAULT_MAX_SCROLL_OVERFLOW}
  --fail-on-console-warning     Treat console warnings as failures
  --disable-route-markers       Do not require built-in route content markers for default routes
  --include-detail-routes       Resolve and append music/community detail routes from local API data
  --output <path>               Write JSON results to a file
  --chrome <path>               Chrome/Chromium executable path
`)
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

function normalizeRoute(route) {
  const parsed = new URL(route, 'http://127.0.0.1')
  const path = parsed.pathname || '/'
  return path !== '/' && path.endsWith('/') ? path.slice(0, -1) : path
}

function getRouteReadyMarkers(route) {
  const normalized = normalizeRoute(route)
  const exact = ROUTE_READY_MARKERS[normalized]
  if (exact) return exact
  return DYNAMIC_ROUTE_READY_MARKERS.find((entry) => entry.pattern.test(normalized))?.markers || []
}

function isDynamicRoute(route) {
  const normalized = normalizeRoute(route)
  return DYNAMIC_ROUTE_READY_MARKERS.some((entry) => entry.pattern.test(normalized))
}

async function fetchJson(baseUrl, path, params = {}) {
  const url = new URL(path, baseUrl)
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, String(value))
  }
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url.pathname} returned HTTP ${response.status}`)
  return response.json()
}

function detailApiBaseUrl(baseUrl, apiBaseUrl) {
  return apiBaseUrl || baseUrl
}

async function resolveDetailRoutes(baseUrl, apiBaseUrl) {
  const apiUrl = detailApiBaseUrl(baseUrl, apiBaseUrl)
  const [entities, feed] = await Promise.all([
    fetchJson(apiUrl, '/api/billboard/entity-lists', DETAIL_ROUTE_FILTERS),
    fetchJson(apiUrl, '/api/community/feed', { limit: 1 }),
  ])

  const track = entities.tracks?.find((item) => item.track_id != null)
  const album = entities.albums?.find((item) => item.album_name && item.artist_name)
  const artist = entities.artists?.find((item) => item.artist_name)
  const post = feed.posts?.find((item) => item.id)

  const routes = []
  if (track) routes.push(`/music/tracks/${encodeURIComponent(String(track.track_id))}`)
  if (album) {
    routes.push(
      `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
    )
  }
  if (artist) routes.push(`/music/artists/${encodeURIComponent(artist.artist_name)}`)
  if (post) {
    routes.push(`/community/post/${encodeURIComponent(post.id)}`)
    if (post.account_handle) {
      routes.push(`/community/account/${encodeURIComponent(post.account_handle)}`)
    }
  }

  if (routes.length < 5) {
    throw new Error(`Could not resolve all detail routes from /api/billboard/entity-lists and /api/community/feed; got ${routes.length}`)
  }
  return routes
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

  on(method, handler) {
    this.handlers.set(method, [...(this.handlers.get(method) || []), handler])
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

  once(method, timeoutMs = 30000) {
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
      this.on(method, handler)
    })
  }

  close() {
    this.ws.close()
  }
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

async function smokeRoute({
  port,
  baseUrl,
  apiBaseUrl,
  route,
  viewportName,
  waitMs,
  maxScrollOverflow,
  failOnConsoleWarning,
  enforceRouteMarkers,
}) {
  const viewport = VIEWPORTS[viewportName]
  const target = await createTarget(port)
  const client = await new CdpClient(target.webSocketDebuggerUrl).connect()
  const consoleEntries = []
  const pageErrors = []

  try {
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Log.enable')
    await client.send('Network.enable')
    await setupApiRequestRewrite(client, baseUrl, apiBaseUrl)
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: viewport.deviceScaleFactor,
      mobile: viewport.mobile,
    })
    await client.send('Emulation.setUserAgentOverride', { userAgent: viewport.userAgent })

    client.on('Runtime.exceptionThrown', (params) => {
      pageErrors.push(params.exceptionDetails?.text || params.exceptionDetails?.exception?.description || 'Runtime exception')
    })
    client.on('Runtime.consoleAPICalled', (params) => {
      consoleEntries.push({
        level: params.type,
        text: formatConsoleArgs(params.args || []),
      })
    })
    client.on('Log.entryAdded', (params) => {
      if (params.entry) {
        consoleEntries.push({
          level: params.entry.level,
          text: params.entry.text || '',
        })
      }
    })

    const url = new URL(route, baseUrl).toString()
    const loadEvent = client.once('Page.loadEventFired')
    await client.send('Page.navigate', { url })
    await loadEvent
    const routeMarkers = enforceRouteMarkers ? getRouteReadyMarkers(route) : []
    const routeWaitMs = isDynamicRoute(route) ? Math.max(waitMs, DYNAMIC_ROUTE_WAIT_MS) : waitMs
    await sleep(routeWaitMs)

    const evaluation = await client.send('Runtime.evaluate', {
      expression: PAGE_STATE_EXPRESSION,
      returnByValue: true,
      awaitPromise: true,
    })
    const state = evaluation.result.value
    const scrollWidth = Math.max(state.bodyScrollWidth || 0, state.documentScrollWidth || 0)
    const scrollOverflow = Math.max(0, scrollWidth - (state.viewportWidth || viewport.width))
    const consoleErrors = consoleEntries.filter((entry) => ['error', 'assert'].includes(entry.level))
    const consoleWarnings = consoleEntries.filter((entry) => ['warning', 'warn'].includes(entry.level))
    const missingRouteMarkers = routeMarkers.filter((marker) => !state.bodyText.includes(marker))

    const failures = []
    if (pageErrors.length > 0) failures.push(`${pageErrors.length} runtime exception(s)`)
    if (consoleErrors.length > 0) failures.push(`${consoleErrors.length} console error(s)`)
    if (failOnConsoleWarning && consoleWarnings.length > 0) failures.push(`${consoleWarnings.length} console warning(s)`)
    if (state.hasDevOverlay) failures.push('dev error overlay detected')
    if (state.hasFatalText) failures.push('fatal error text detected')
    if (state.rootTextLength < 20) failures.push(`root text too short (${state.rootTextLength})`)
    if (missingRouteMarkers.length > 0) {
      failures.push(`missing route content marker(s): ${missingRouteMarkers.join(', ')}`)
    }
    if (scrollOverflow > maxScrollOverflow) {
      failures.push(`horizontal overflow ${scrollOverflow}px > ${maxScrollOverflow}px`)
    }

    return {
      route,
      viewport: viewportName,
      url,
      ok: failures.length === 0,
      failures,
      title: state.title,
      readyState: state.readyState,
      rootTextLength: state.rootTextLength,
      scrollOverflow,
      bodyScrollWidth: state.bodyScrollWidth,
      documentScrollWidth: state.documentScrollWidth,
      viewportWidth: state.viewportWidth,
      consoleErrorCount: consoleErrors.length,
      consoleWarningCount: consoleWarnings.length,
      pageErrorCount: pageErrors.length,
      consoleErrors: consoleErrors.slice(0, 5),
      consoleWarnings: consoleWarnings.slice(0, 5),
      pageErrors: pageErrors.slice(0, 5),
      missingRouteMarkers,
      bodyTextSample: state.bodyTextSample,
    }
  } finally {
    client.close()
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(() => {})
  }
}

function formatConsoleArgs(args) {
  return args
    .map((arg) => arg.value ?? arg.description ?? arg.unserializableValue ?? '')
    .filter((value) => value !== '')
    .join(' ')
}

function renderMarkdown(results) {
  const lines = [
    '# Frontend Route Smoke',
    '',
    `> Generated: ${new Date().toISOString()}`,
    '',
    '| Route | Viewport | Status | Console errors | Console warnings | Page errors | Scroll overflow | Root text |',
    '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |',
  ]

  for (const row of results) {
    lines.push(
      `| \`${row.route}\` | ${row.viewport} | ${row.ok ? 'PASS' : 'FAIL'} | ${row.consoleErrorCount} | ${row.consoleWarningCount} | ${row.pageErrorCount} | ${row.scrollOverflow}px | ${row.rootTextLength} |`,
    )
  }

  const failed = results.filter((row) => !row.ok)
  if (failed.length > 0) {
    lines.push('')
    lines.push('## Failures')
    for (const row of failed) {
      lines.push('')
      lines.push(`- \`${row.route}\` (${row.viewport}): ${row.failures.join('; ')}`)
      for (const error of row.consoleErrors) lines.push(`  - console ${error.level}: ${error.text}`)
      for (const error of row.pageErrors) lines.push(`  - page error: ${error}`)
    }
  }

  return lines.join('\n')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const chromePath = findChrome(args.chrome)
  const port = await getFreePort()
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-stats-route-smoke-'))

  const chrome = spawn(
    chromePath,
    [
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
    ],
    { stdio: 'ignore' },
  )

  const cleanup = async () => {
    chrome.kill('SIGTERM')
    await rm(profileDir, { recursive: true, force: true }).catch(() => {})
  }

  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`)

    let routes = args.routes
    if (args.includeDetailRoutes) {
      const detailRoutes = await resolveDetailRoutes(args.baseUrl, args.apiBaseUrl)
      routes = [...new Set([...routes, ...detailRoutes])]
      process.stderr.write(`Resolved detail routes: ${detailRoutes.join(', ')}\n`)
    }

    const results = []
    for (const route of routes) {
      for (const viewport of args.viewports) {
        process.stderr.write(`Checking ${route} (${viewport}) ... `)
        const result = await smokeRoute({
          port,
          baseUrl: args.baseUrl,
          apiBaseUrl: args.apiBaseUrl,
          route,
          viewportName: viewport,
          waitMs: args.waitMs,
          maxScrollOverflow: args.maxScrollOverflow,
          failOnConsoleWarning: args.failOnConsoleWarning,
          enforceRouteMarkers: args.enforceRouteMarkers,
        })
        results.push(result)
        process.stderr.write(`${result.ok ? 'PASS' : 'FAIL'}\n`)
      }
    }

    const markdown = renderMarkdown(results)
    console.log(markdown)

    if (args.output) {
      await writeFile(args.output, `${JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2)}\n`)
      console.error(`JSON written to ${args.output}`)
    }

    if (results.some((row) => !row.ok)) process.exitCode = 1
  } finally {
    await cleanup()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
