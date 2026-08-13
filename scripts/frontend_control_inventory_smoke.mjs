#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 8000
const DYNAMIC_ROUTE_WAIT_MS = 12000
const SLOW_ROUTE_WAIT_MS = 12000
const DEFAULT_MAX_VIOLATIONS = 0
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
  '/analysis/stats',
  '/analysis/charts',
  '/analysis/records',
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

const SLOW_ROUTES = new Set(['/analysis/records'])

const ROUTE_READY_MARKERS = {
  '/': ['最近一章', '最新个人 Billboard'],
  '/analysis/stats': ['PLAYBACK / ANALYSIS', '播放统计'],
  '/analysis/charts': ['PLAYBACK RANKING', '播放排行'],
  '/analysis/records': ['播放记录', '高光时刻'],
  '/yearly-review': ['年度总结'],
  '/billboard': ['CHART / WEEKLY', 'Billboard 周榜'],
  '/billboard/number-ones': ['每周榜首'],
  '/billboard/all-time': ['总榜'],
  '/billboard/year-end': ['年榜'],
  '/billboard/records': ['榜单记录'],
  '/billboard/versus': ['对决'],
  '/community': ['社区', '精选'],
  '/ai-insights': ['AI / INSIGHTS', 'AI 洞察'],
  '/account': ['账号中心', '播放'],
  '/settings': ['参数与配置', '01 · SPOTIFY 连接', 'PREFERENCES / MOBILE', 'SETTINGS / MOBILE'],
}

const DYNAMIC_ROUTE_READY_MARKERS = [
  { pattern: /^\/music\/tracks\/[^/]+$/, markers: ['单曲详情', '统计'] },
  { pattern: /^\/music\/albums\/[^/]+$/, markers: ['专辑详情', '统计'] },
  { pattern: /^\/music\/artists\/[^/]+$/, markers: ['艺人详情', '统计'] },
  { pattern: /^\/community\/post\/[^/]+$/, markers: ['COMMUNITY / POST', '回复'] },
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

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBaseUrl: null,
    routes: DEFAULT_ROUTES,
    waitMs: DEFAULT_WAIT_MS,
    viewports: ['desktop', 'mobile'],
    includeDetailRoutes: false,
    maxViolations: DEFAULT_MAX_VIOLATIONS,
    output: null,
    chrome: null,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
    else if (arg === '--routes') args.routes = argv[++i].split(',').map((route) => route.trim()).filter(Boolean)
    else if (arg === '--viewport') {
      const value = argv[++i]
      args.viewports = value === 'both' ? ['desktop', 'mobile'] : [value]
    } else if (arg === '--include-detail-routes') args.includeDetailRoutes = true
    else if (arg === '--wait-ms') args.waitMs = Number(argv[++i])
    else if (arg === '--max-violations') args.maxViolations = Number(argv[++i])
    else if (arg === '--output') args.output = argv[++i]
    else if (arg === '--chrome') args.chrome = argv[++i]
    else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (args.routes.length === 0) throw new Error('--routes must include at least one route')
  if (!Number.isFinite(args.waitMs) || args.waitMs < 500) throw new Error('--wait-ms must be at least 500')
  if (!Number.isFinite(args.maxViolations) || args.maxViolations < 0) {
    throw new Error('--max-violations must be a non-negative number')
  }
  for (const viewport of args.viewports) {
    if (!VIEWPORTS[viewport]) throw new Error(`Unsupported viewport: ${viewport}`)
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_control_inventory_smoke.mjs [options]

Options:
  --base-url <url>              Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>          Rewrite same-origin /api and /covers requests to this API URL
  --routes <a,b,c>              Comma-separated route paths, default ${DEFAULT_ROUTES.join(',')}
  --viewport <mode>             desktop, mobile, or both, default both
  --include-detail-routes       Resolve and append music/community detail routes from local API data
  --wait-ms <ms>                Max wait for route content, default ${DEFAULT_WAIT_MS}; dynamic detail routes use at least ${DYNAMIC_ROUTE_WAIT_MS}
  --max-violations <n>          Allowed interactive control inventory violations, default ${DEFAULT_MAX_VIOLATIONS}
  --output <path>               Write JSON results to a file
  --chrome <path>               Chrome/Chromium executable path

Checks:
  interactive control inventory validates missing accessible name, nested interactive control,
  disabled but tabbable, input without label, duplicate id, and mobile primary touch targets below 44px.
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

async function makeClient(port) {
  const target = await createTarget(port)
  const client = await new CdpClient(target.webSocketDebuggerUrl).connect()
  await client.send('Runtime.enable')
  await client.send('Page.enable')
  await client.send('Network.enable')
  return client
}

async function setupApiRequestRewrite(client, baseUrl, apiBaseUrl) {
  if (!apiBaseUrl) return

  const frontendOrigin = new URL(baseUrl).origin
  const apiOrigin = new URL(apiBaseUrl).origin
  await client.send('Fetch.enable', {
    patterns: REWRITE_PATH_PREFIXES.map((path) => ({ urlPattern: `${frontendOrigin}${path}*` })),
  })

  client.on('Fetch.requestPaused', async (event) => {
    try {
      const url = new URL(event.request.url)
      const shouldRewrite = REWRITE_PATH_PREFIXES.some((path) => url.pathname.startsWith(path))
      if (!shouldRewrite) {
        await client.send('Fetch.continueRequest', { requestId: event.requestId })
        return
      }

      const rewritten = `${apiOrigin}${url.pathname}${url.search}`
      await client.send('Fetch.continueRequest', { requestId: event.requestId, url: rewritten })
    } catch {
      await client.send('Fetch.continueRequest', { requestId: event.requestId }).catch(() => {})
    }
  })
}

function absoluteUrl(baseUrl, route) {
  return new URL(route, baseUrl).toString()
}

async function navigate(client, url, viewport, timeoutMs) {
  await client.send('Emulation.setDeviceMetricsOverride', viewport)
  await client.send('Emulation.setUserAgentOverride', { userAgent: viewport.userAgent })
  // Reset same-route viewport passes so SPA navigation cannot reuse a half-updated shell.
  const resetLoaded = client.once('Page.loadEventFired', timeoutMs + 10000)
  await client.send('Page.navigate', { url: 'about:blank' })
  await resetLoaded.catch(() => {})
  const loaded = client.once('Page.loadEventFired', timeoutMs + 10000)
  await client.send('Page.navigate', { url })
  await loaded.catch(() => {})
}

async function evaluate(client, expression, awaitPromise = false) {
  const result = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise,
    returnByValue: true,
  })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'Runtime evaluation failed')
  }
  return result.result.value
}

async function waitForRouteReady(client, route, timeoutMs) {
  const markers = markersForRoute(route)
  const minimumTextLength = route.split('?')[0] === '/settings' ? 60 : 80
  const effectiveTimeoutMs = waitMsForRoute(route, timeoutMs)
  const started = Date.now()
  let state = null
  while (Date.now() - started < effectiveTimeoutMs) {
    state = await evaluate(
      client,
      `(() => {
        const bodyText = document.body ? document.body.innerText : '';
        return {
          readyState: document.readyState,
          bodyText,
          rootTextLength: (document.querySelector('#root')?.textContent || '').trim().length,
          hasMarker: ${JSON.stringify(markers)}.some((marker) => bodyText.includes(marker)),
          hasFatalText: /Internal Server Error|Failed to fetch dynamically imported module|ReferenceError|TypeError|Unhandled Runtime Error/.test(bodyText),
        };
      })()`,
    )
    if (state.hasFatalText) throw new Error(`Fatal page text at ${route}`)
    if (state.rootTextLength > minimumTextLength && (!markers.length || state.hasMarker)) return state
    await sleep(150)
  }
  throw new Error(`Timed out waiting for route content at ${route}: ${JSON.stringify(state)}`)
}

async function navigateAndWaitForRouteReady(client, route, url, viewport, timeoutMs) {
  let lastError
  const effectiveTimeoutMs = waitMsForRoute(route, timeoutMs)
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await navigate(client, url, viewport, effectiveTimeoutMs)
    try {
      return await waitForRouteReady(client, route, effectiveTimeoutMs)
    } catch (error) {
      lastError = error
      if (attempt < 2) {
        process.stderr.write(`Retrying control inventory route ${route}: ${error.message}\n`)
      }
    }
  }
  throw lastError
}

function markersForRoute(route) {
  const routePath = route.split('?')[0]
  if (ROUTE_READY_MARKERS[routePath]) return ROUTE_READY_MARKERS[routePath]
  const dynamic = DYNAMIC_ROUTE_READY_MARKERS.find(({ pattern }) => pattern.test(routePath))
  return dynamic ? dynamic.markers : []
}

function isDynamicRoute(route) {
  const routePath = route.split('?')[0]
  return DYNAMIC_ROUTE_READY_MARKERS.some(({ pattern }) => pattern.test(routePath))
}

function waitMsForRoute(route, timeoutMs) {
  const routePath = route.split('?')[0]
  if (isDynamicRoute(route)) return Math.max(timeoutMs, DYNAMIC_ROUTE_WAIT_MS)
  if (SLOW_ROUTES.has(routePath)) return Math.max(timeoutMs, SLOW_ROUTE_WAIT_MS)
  return timeoutMs
}

async function collectControlInventory(client) {
  return evaluate(
    client,
    `(() => {
      const interactiveSelector = [
        'a[href]',
        'button',
        'input:not([type="hidden"]):not([id$="-hidden-input"])',
        'select',
        'textarea',
        'summary',
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="checkbox"]',
        '[role="switch"]',
        '[role="radio"]',
        '[role="menuitem"]',
        '[role="option"]',
        '[role="combobox"]',
      ].join(',');
      const inputSelector = 'input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="reset"]), select, textarea, [role="combobox"]';
      const primaryTouchSelector = [
        '.mobile-wordmark',
        '.mobile-bottom-nav-item',
        '.mobile-top-bar button',
        '.mobile-top-bar a',
        '.mobile-time-range-trigger',
        '.mobile-segmented button',
        '.mobile-chart-series-button',
        '.mobile-yearly-controls button',
        '.mobile-yearly-chapters button',
        '.mobile-year-chips button',
        '.mobile-list-toolbar button',
        '.mobile-versus-kind button',
        '.mobile-versus-selector button',
        '.community-feed-toggle button',
        '.mobile-community-filter-bar',
        '.mobile-community-search-field button',
        '.mobile-ai-mode-switch button',
        '[data-mobile-ai-reports="panel"] button',
        '[data-mobile-ai-reports="panel"] select',
        '[data-mobile-ai-reports="panel"] input',
        '.mobile-account-tabs button',
        '.mobile-settings-panel-header button',
        '.mobile-settings-switch',
        '.mobile-settings-select',
        '.mobile-settings-segment button',
        '.mobile-music-search-input input',
        '.mobile-music-search-kinds button',
        '.mobile-record-entity-toggle button',
        '.mobile-recent-sort button',
        '.mobile-recent-group-trigger',
        '.mobile-primary-button',
        '.mobile-secondary-button',
        '.mobile-icon-button',
        '.mobile-section-link',
        '.mobile-filter-option',
        '.mobile-time-option',
        '.mobile-pagination button',
        '.mobile-entity-row-interactive',
      ].join(',');
      const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
      };
      const textFromIds = (ids) => ids
        .split(/\\s+/)
        .filter(Boolean)
        .map((id) => document.getElementById(id)?.innerText || document.getElementById(id)?.textContent || '')
        .join(' ')
        .trim();
      const controlName = (el) => {
        const labelledBy = el.getAttribute('aria-labelledby');
        const fromLabelledBy = labelledBy ? textFromIds(labelledBy) : '';
        const labels = el.labels ? Array.from(el.labels).map((label) => label.innerText || label.textContent || '').join(' ') : '';
        const imgAlt = el.querySelector('img[alt]')?.getAttribute('alt') || '';
        return [
          el.getAttribute('aria-label'),
          fromLabelledBy,
          labels,
          el.getAttribute('title'),
          el.getAttribute('placeholder'),
          imgAlt,
          el.innerText,
          el.textContent,
        ].filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
      };
      const describe = (el) => {
        const name = controlName(el);
        return {
          tag: el.tagName.toLowerCase(),
          role: el.getAttribute('role') || '',
          type: el.getAttribute('type') || '',
          id: el.id || '',
          name: name.slice(0, 120),
          classes: el.className ? String(el.className).slice(0, 160) : '',
          text: (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
        };
      };
      const controls = Array.from(document.querySelectorAll(interactiveSelector)).filter(isVisible);
      const isPhone = document.querySelector('main[data-viewport-mode="phone"]') !== null;
      const touchTargets = isPhone
        ? Array.from(new Set(Array.from(document.querySelectorAll(primaryTouchSelector)))).filter(isVisible)
        : [];
      const idCounts = controls.reduce((counts, el) => {
        if (el.id) counts[el.id] = (counts[el.id] || 0) + 1;
        return counts;
      }, {});
      const violations = [];

      controls.forEach((el, index) => {
        const name = controlName(el);
        const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
        const tabIndexAttr = el.getAttribute('tabindex');
        const tabIndex = tabIndexAttr === null ? null : Number(tabIndexAttr);
        const descendant = Array.from(el.querySelectorAll(interactiveSelector)).find((child) => child !== el && isVisible(child));

        if (!name) {
          violations.push({ type: 'missing accessible name', index, control: describe(el) });
        }
        if (descendant) {
          violations.push({
            type: 'nested interactive control',
            index,
            control: describe(el),
            nested: describe(descendant),
          });
        }
        if (disabled && tabIndex !== null && tabIndex >= 0) {
          violations.push({ type: 'disabled but tabbable', index, control: describe(el) });
        }
        if (idCounts[el.id] > 1) {
          violations.push({ type: 'duplicate id', index, id: el.id, count: idCounts[el.id], control: describe(el) });
        }
        if (el.matches(inputSelector)) {
          const hasLabel = Boolean(name || el.closest('label') || el.getAttribute('aria-labelledby'));
          if (!hasLabel) {
            violations.push({ type: 'input without label', index, control: describe(el) });
          }
        }
      });

      touchTargets.forEach((el, index) => {
        const rect = el.getBoundingClientRect();
        if (rect.width < 43.5 || rect.height < 43.5) {
          violations.push({
            type: 'undersized primary touch target',
            index,
            width: Math.round(rect.width * 10) / 10,
            height: Math.round(rect.height * 10) / 10,
            control: describe(el),
          });
        }
      });

      return {
        totalControls: controls.length,
        namedControls: controls.filter((el) => Boolean(controlName(el))).length,
        inputControls: controls.filter((el) => el.matches(inputSelector)).length,
        primaryTouchTargets: touchTargets.length,
        undersizedTouchTargets: violations.filter((violation) => violation.type === 'undersized primary touch target').length,
        violations,
      };
    })()`,
  )
}

async function resolveDetailRoutes(baseUrl, apiBaseUrl, waitMs) {
  const apiRoot = apiBaseUrl || baseUrl
  const params = new URLSearchParams(Object.entries(DETAIL_ROUTE_FILTERS).map(([key, value]) => [key, String(value)]))
  const routes = []

  try {
    const entities = await waitForJson(`${apiRoot.replace(/\/$/, '')}/api/billboard/entity-lists?${params}`, waitMs + 5000)
    const track = entities.tracks?.find((item) => item.track_id != null)
    const album = entities.albums?.find((item) => item.album_name && item.artist_name)
    const artist = entities.artists?.find((item) => item.artist_name)
    if (track) routes.push(`/music/tracks/${encodeURIComponent(String(track.track_id))}`)
    if (album) {
      routes.push(
        `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
      )
    }
    if (artist) routes.push(`/music/artists/${encodeURIComponent(artist.artist_name)}`)
  } catch (error) {
    process.stderr.write(`Could not resolve music detail routes: ${error.message}\n`)
  }

  try {
    const feed = await waitForJson(`${apiRoot.replace(/\/$/, '')}/api/community/feed?limit=1`, waitMs + 5000)
    const post = feed.posts?.[0]
    if (post?.id) routes.push(`/community/post/${encodeURIComponent(post.id)}`)
    const handle = post?.account_handle || post?.author?.handle || post?.author_handle
    if (handle) routes.push(`/community/account/${encodeURIComponent(handle)}`)
  } catch (error) {
    process.stderr.write(`Could not resolve community detail routes: ${error.message}\n`)
  }

  return routes
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForProcessExit(childProcess) {
  if (childProcess.exitCode !== null || childProcess.signalCode !== null) return
  await new Promise((resolve) => {
    const timer = setTimeout(resolve, 3000)
    childProcess.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

async function run() {
  const args = parseArgs(process.argv.slice(2))
  const chrome = findChrome(args.chrome)
  const debugPort = await getFreePort()
  const userDataDir = await mkdtemp(join(tmpdir(), 'spotify-stats-control-inventory-'))
  const chromeProcess = spawn(
    chrome,
    [
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${userDataDir}`,
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      'about:blank',
    ],
    { stdio: 'ignore' },
  )

  let client
  try {
    await waitForJson(`http://127.0.0.1:${debugPort}/json/version`)
    client = await makeClient(debugPort)
    await setupApiRequestRewrite(client, args.baseUrl, args.apiBaseUrl)

    const routes = [...args.routes]
    if (args.includeDetailRoutes) {
      const detailRoutes = await resolveDetailRoutes(args.baseUrl, args.apiBaseUrl, args.waitMs)
      if (detailRoutes.length < 5) {
        throw new Error(
          `Could not resolve all control inventory detail routes: expected 5, got ${detailRoutes.length}`,
        )
      }
      routes.push(...detailRoutes.filter((route) => !routes.includes(route)))
      if (detailRoutes.length > 0) {
        process.stderr.write(`Resolved control inventory detail routes: ${detailRoutes.join(', ')}\n`)
      }
    }

    const results = []
    for (const route of routes) {
      for (const viewportName of args.viewports) {
        await navigateAndWaitForRouteReady(
          client,
          route,
          absoluteUrl(args.baseUrl, route),
          VIEWPORTS[viewportName],
          args.waitMs,
        )
        const inventory = await collectControlInventory(client)
        results.push({ route, viewport: viewportName, ...inventory })
        process.stderr.write(
          `PASS control-inventory ${route} ${viewportName}: controls=${inventory.totalControls}, touchTargets=${inventory.primaryTouchTargets}, violations=${inventory.violations.length}\n`,
        )
      }
    }

    const violations = results.flatMap((result) =>
      result.violations.map((violation) => ({ route: result.route, viewport: result.viewport, ...violation })),
    )
    const summary = {
      checked: results.length,
      routes,
      viewports: args.viewports,
      totalControls: results.reduce((sum, result) => sum + result.totalControls, 0),
      primaryTouchTargets: results.reduce((sum, result) => sum + result.primaryTouchTargets, 0),
      undersizedTouchTargets: results.reduce((sum, result) => sum + result.undersizedTouchTargets, 0),
      totalViolations: violations.length,
      violations,
      results,
    }

    if (args.output) await writeFile(args.output, `${JSON.stringify(summary, null, 2)}\n`)
    if (violations.length > args.maxViolations) {
      console.error(JSON.stringify({ totalViolations: violations.length, sample: violations.slice(0, 20) }, null, 2))
      throw new Error(`interactive control inventory violations ${violations.length} exceed max ${args.maxViolations}`)
    }
    console.log(JSON.stringify(summary, null, 2))
  } finally {
    if (client) client.close()
    chromeProcess.kill('SIGTERM')
    await waitForProcessExit(chromeProcess)
    await rm(userDataDir, { recursive: true, force: true })
  }
}

run().catch((error) => {
  console.error(error.stack || error.message)
  process.exit(1)
})
