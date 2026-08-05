#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 12000
const DEFAULT_ACCOUNT_CHART_WAIT_MS = 12000
const DEFAULT_DATAZOOM_WAIT_MS = 12000
const DEFAULT_SCENARIOS = ['chart-hover-tooltip', 'legend-toggle', 'datazoom-drag']
const LEGEND_EVENT_NAME = 'legendselectchanged'
const DEFAULT_BILLBOARD_PARAMS = {
  min_ms: 30000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: true,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  merge_level: 2,
}

const MouseEvent = {
  mouseMoved: 'mouseMoved',
  mousePressed: 'mousePressed',
  mouseReleased: 'mouseReleased',
}

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
    scenarios: DEFAULT_SCENARIOS,
    viewport: 'desktop',
    waitMs: DEFAULT_WAIT_MS,
    output: null,
    chrome: null,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
    else if (arg === '--viewport') args.viewport = argv[++i]
    else if (arg === '--scenario' || arg === '--scenarios') {
      args.scenarios = argv[++i].split(',').map((scenario) => scenario.trim()).filter(Boolean)
    } else if (arg === '--wait-ms') args.waitMs = Number(argv[++i])
    else if (arg === '--output') args.output = argv[++i]
    else if (arg === '--chrome') args.chrome = argv[++i]
    else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (args.scenarios.length === 0) throw new Error('--scenario must include at least one scenario')
  if (!Number.isFinite(args.waitMs) || args.waitMs < 250) throw new Error('--wait-ms must be at least 250')
  if (!VIEWPORTS[args.viewport]) throw new Error(`Unsupported viewport: ${args.viewport}`)
  for (const scenario of args.scenarios) {
    if (!SCENARIOS[scenario]) throw new Error(`Unsupported scenario: ${scenario}`)
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_chart_interaction_smoke.mjs [options]

Options:
  --base-url <url>        Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>    API URL for dynamic fixture discovery, defaults to --base-url
  --viewport <mode>       desktop or mobile, default desktop
  --scenario <a,b,c>      Comma-separated scenarios, default ${DEFAULT_SCENARIOS.join(',')}
  --wait-ms <ms>          Max wait for route/text assertions, default ${DEFAULT_WAIT_MS}
  --output <path>         Write JSON results to a file
  --chrome <path>         Chrome/Chromium executable path

Scenarios:
  chart-hover-tooltip     Hover an ECharts canvas and require a visible tooltip
  legend-toggle           Click a canvas legend area and require a rendered canvas delta
  datazoom-drag           Switch a rank chart to detail mode and drag the dataZoom slider
  mobile-tap-tooltip      Tap a mobile listening-clock segment and require its tooltip
  mobile-fullscreen       Open and close a real mobile fullscreen chart with focus restoration
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

async function fetchFrontendJson(baseUrl, path, params = {}) {
  const url = new URL(path, baseUrl)
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, String(value))
  }
  const response = await fetch(url)
  if (!response.ok) throw new Error(`GET ${url.pathname} returned HTTP ${response.status}`)
  return response.json()
}

async function resolveDataZoomPath(baseUrl) {
  const allTime = await fetchFrontendJson(baseUrl, '/api/billboard/all-time', DEFAULT_BILLBOARD_PARAMS)
  const artist = (allTime.artist_power_scores || []).find((item) => item.artist_name && item.weeks_on_chart > 50)
  if (artist) {
    return {
      path: `/music/artists/${encodeURIComponent(artist.artist_name)}`,
      readyText: artist.artist_name,
      marker: '排名趋势',
      label: `${artist.artist_name} (${artist.weeks_on_chart} weeks)`,
    }
  }

  const album = (allTime.album_power_scores || []).find((item) => item.album_name && item.artist_name && item.weeks_on_chart > 50)
  if (album) {
    return {
      path: `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
      readyText: album.album_name,
      marker: '排名趋势',
      label: `${album.album_name} (${album.weeks_on_chart} weeks)`,
    }
  }

  throw new Error('No artist or album with enough chart history for dataZoom smoke')
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
  client.targetId = target.id
  return client
}

async function setupPage(client, viewport) {
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Log.enable')
  await client.send('Network.enable')
  await client.send('Emulation.setDeviceMetricsOverride', viewport)
  await client.send('Emulation.setUserAgentOverride', { userAgent: viewport.userAgent })
  await client.send('Emulation.setTouchEmulationEnabled', { enabled: viewport.mobile, maxTouchPoints: viewport.mobile ? 5 : 1 })
}

async function navigate(client, baseUrl, path) {
  const url = new URL(path, baseUrl).toString()
  const loadEvent = client.once('Page.loadEventFired')
  await client.send('Page.navigate', { url })
  await loadEvent
  await sleep(250)
}

async function evaluate(client, expression) {
  const result = await client.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Evaluation failed')
  }
  return result.result.value
}

async function pageState(client) {
  return evaluate(client, `
    (() => ({
      path: location.pathname,
      bodyText: document.body ? document.body.innerText : '',
      scrollWidth: Math.max(document.body ? document.body.scrollWidth : 0, document.documentElement ? document.documentElement.scrollWidth : 0),
      viewportWidth: innerWidth,
    }))();
  `)
}

async function canvasState(client) {
  return evaluate(client, `
    (() => {
      const canvases = Array.from(document.querySelectorAll('canvas'));
      const resources = performance.getEntriesByType('resource')
        .map((entry) => entry.name)
        .filter((name) => /echarts|chart|Analysis|RankTrend|core|\\.js(\\?|$)/i.test(name));
      const rects = canvases.map((canvas, index) => {
        const rect = canvas.getBoundingClientRect();
        return {
          index,
          left: Math.round(rect.left),
          top: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          visible: rect.width > 0 && rect.height > 0,
        };
      });
      const bodyText = document.body ? document.body.innerText : '';
      return {
        path: location.pathname,
        readyState: document.readyState,
        bodyTextLength: bodyText.length,
        bodyTextPreview: bodyText.slice(0, 180),
        canvasCount: canvases.length,
        visibleCanvasCount: rects.filter((rect) => rect.visible).length,
        canvasRects: rects.slice(0, 6),
        svgCount: document.querySelectorAll('svg').length,
        chartContainerCount: document.querySelectorAll('[_echarts_instance_], [class*="echarts"], [style*="zrender"]').length,
        canvas2dAvailable: Boolean(document.createElement('canvas').getContext('2d')),
        devicePixelRatio,
        resourcePreview: resources.slice(-12).map((name) => name.split('/').slice(-2).join('/')),
        loadingNodeCount: document.querySelectorAll('[aria-busy="true"], .animate-pulse').length,
      };
    })();
  `)
}

function describeCanvasState(state) {
  if (!state) return ''
  return `; last canvas state ${JSON.stringify({
    path: state.path,
    readyState: state.readyState,
    bodyTextLength: state.bodyTextLength,
    canvasCount: state.canvasCount,
    visibleCanvasCount: state.visibleCanvasCount,
    svgCount: state.svgCount,
    chartContainerCount: state.chartContainerCount,
    canvas2dAvailable: state.canvas2dAvailable,
    loadingNodeCount: state.loadingNodeCount,
    canvasRects: state.canvasRects,
    resourcePreview: state.resourcePreview,
  })}`
}

async function clickText(client, text, waitMs) {
  const clicked = await evaluate(client, `
    (() => {
      const targetText = ${JSON.stringify(text)};
      const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"]'))
        .filter((el) => (el.innerText || el.textContent || '').trim().includes(targetText));
      const el = candidates[0];
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })();
  `)
  if (!clicked) throw new Error(`Clickable text not found: ${text}`)
  await sleep(Math.min(250, waitMs))
}

async function clickByAriaLabel(client, label, waitMs) {
  return waitForCondition(
    async () => evaluate(client, `
      (() => {
        const label = ${JSON.stringify(label)};
        const el = Array.from(document.querySelectorAll('button, a, [role="button"]'))
          .find((item) => item.getAttribute('aria-label') === label);
        if (!el) return null;
        el.scrollIntoView({ block: 'center', inline: 'center' });
        el.click();
        return { path: location.pathname };
      })();
    `),
    waitMs,
    `Clickable aria-label not found: ${label}`,
  )
}

async function waitForSelector(client, selector, timeoutMs) {
  return waitForCondition(
    async () => evaluate(client, `
      (() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 ? { path: location.pathname } : null;
      })();
    `),
    timeoutMs,
    `Expected visible selector: ${selector}`,
  )
}

async function waitForSelectorGone(client, selector, timeoutMs) {
  return waitForCondition(
    async () => evaluate(client, `document.querySelector(${JSON.stringify(selector)}) ? null : ({ path: location.pathname })`),
    timeoutMs,
    `Expected selector to close: ${selector}`,
  )
}

async function waitForText(client, text, timeoutMs) {
  return waitForCondition(
    async () => {
      const state = await pageState(client)
      return state.bodyText.includes(text) ? state : null
    },
    timeoutMs,
    `Expected page text not found: ${text}`,
  )
}

async function waitForCanvasCount(client, minCount, timeoutMs) {
  let lastCanvasState = null
  return waitForCondition(
    async () => {
      lastCanvasState = await canvasState(client)
      return lastCanvasState.canvasCount >= minCount ? lastCanvasState : null
    },
    timeoutMs,
    `Expected at least ${minCount} ECharts canvas element(s)`,
    () => describeCanvasState(lastCanvasState),
  )
}

async function waitForCondition(check, timeoutMs, failureMessage, describeLastState = null) {
  const started = Date.now()
  let lastState = null
  while (Date.now() - started < timeoutMs) {
    lastState = await check()
    if (lastState) return lastState
    await sleep(150)
  }
  const suffix = describeLastState ? describeLastState(lastState) : lastState && lastState.path ? `; last path ${lastState.path}` : ''
  throw new Error(`${failureMessage}${suffix}`)
}

async function getCanvasRect(client, index = 0) {
  const rect = await evaluate(client, `
    (() => {
      const canvases = Array.from(document.querySelectorAll('canvas'))
        .map((canvas, index) => {
          const rect = canvas.getBoundingClientRect();
          return { index, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
        })
        .filter((rect) => rect.width > 120 && rect.height > 120)
        .sort((a, b) => a.top - b.top || a.left - b.left);
      return canvases[${index}] || null;
    })();
  `)
  if (!rect) throw new Error(`Visible ECharts canvas not found at index ${index}`)
  return rect
}

async function hashCanvas(client, index = 0) {
  return evaluate(client, `
    (() => {
      const canvases = Array.from(document.querySelectorAll('canvas'))
        .filter((canvas) => {
          const rect = canvas.getBoundingClientRect();
          return rect.width > 120 && rect.height > 120;
        })
        .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top || a.getBoundingClientRect().left - b.getBoundingClientRect().left);
      const canvas = canvases[${index}];
      if (!canvas) return null;
      const data = canvas.toDataURL('image/png');
      let hash = 2166136261;
      const step = Math.max(1, Math.floor(data.length / 5000));
      for (let i = 0; i < data.length; i += step) {
        hash ^= data.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
      }
      return String(hash >>> 0);
    })();
  `)
}

async function dispatchMouse(client, type, x, y, button = 'none') {
  await client.send('Input.dispatchMouseEvent', {
    type,
    x,
    y,
    button,
    clickCount: button === 'left' ? 1 : 0,
  })
}

async function findTooltipText(client) {
  return evaluate(client, `
    (() => {
      const nodes = Array.from(document.querySelectorAll('body div'));
      const candidates = nodes
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const text = (el.innerText || el.textContent || '').trim();
          return { el, rect, style, text };
        })
        .filter(({ el, rect, style, text }) =>
          text.length > 0 &&
          style.position === 'absolute' &&
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          rect.width > 20 &&
          rect.height > 10 &&
          rect.left >= 0 &&
          rect.top >= 0 &&
          (style.zIndex === '9999999' || el.getAttribute('style')?.includes('box-shadow') || el.getAttribute('style')?.includes('border-radius'))
        );
      return candidates[0]?.text || '';
    })();
  `)
}

async function hoverUntilTooltip(client, canvasIndex, waitMs) {
  const rect = await getCanvasRect(client, canvasIndex)
  const ratios = [
    [0.22, 0.48],
    [0.35, 0.52],
    [0.5, 0.48],
    [0.65, 0.52],
    [0.78, 0.48],
  ]
  for (const [rx, ry] of ratios) {
    const x = rect.left + rect.width * rx
    const y = rect.top + rect.height * ry
    await dispatchMouse(client, MouseEvent.mouseMoved, x, y)
    await sleep(Math.min(300, waitMs))
    const tooltip = await findTooltipText(client)
    if (tooltip) return { tooltip, x, y }
  }
  throw new Error('ECharts tooltip did not appear after hovering the canvas')
}

async function tapListeningClockUntilTooltip(client, waitMs) {
  const target = await waitForCondition(
    async () => evaluate(client, `
      (() => {
        const el = document.querySelector('.mobile-chart-card svg path[role="button"][aria-label]');
        if (!el) return null;
        el.scrollIntoView({ block: 'center', inline: 'center' });
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return null;
        return {
          path: location.pathname,
          label: el.getAttribute('aria-label'),
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        };
      })();
    `),
    waitMs,
    'Mobile listening-clock touch target was not ready',
  )
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x: target.x, y: target.y, radiusX: 8, radiusY: 8, force: 1 }],
  })
  await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await waitForCondition(
    async () => evaluate(client, `
      (() => {
        const label = ${JSON.stringify(target.label)};
        const el = Array.from(document.querySelectorAll('.mobile-chart-card div'))
          .find((item) => (item.innerText || item.textContent || '').trim() === label);
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 ? { path: location.pathname, label } : null;
      })();
    `),
    waitMs,
    'Mobile chart tooltip did not appear after touch input',
  )
  return { tooltip: target.label, pointerType: 'touch', x: target.x, y: target.y }
}

async function clickCanvasPoint(client, rect, rx, ry) {
  const x = rect.left + rect.width * rx
  const y = rect.top + rect.height * ry
  await dispatchMouse(client, MouseEvent.mousePressed, x, y, 'left')
  await dispatchMouse(client, MouseEvent.mouseReleased, x, y, 'left')
}

async function dragCanvasPoint(client, rect, fromRx, toRx, ry) {
  const startX = rect.left + rect.width * fromRx
  const endX = rect.left + rect.width * toRx
  const y = rect.top + rect.height * ry
  await dispatchMouse(client, MouseEvent.mouseMoved, startX, y)
  await dispatchMouse(client, MouseEvent.mousePressed, startX, y, 'left')
  for (const ratio of [0.3, 0.55, 0.8, 1]) {
    const x = startX + (endX - startX) * ratio
    await dispatchMouse(client, MouseEvent.mouseMoved, x, y, 'left')
    await sleep(80)
  }
  await dispatchMouse(client, MouseEvent.mouseReleased, endX, y, 'left')
}

async function clickLegendUntilCanvasDelta(client, canvasIndex, waitMs) {
  const rect = await getCanvasRect(client, canvasIndex)
  const before = await hashCanvas(client, canvasIndex)
  const points = [
    [0.5, 0.94],
    [0.38, 0.94],
    [0.62, 0.94],
    [0.25, 0.94],
    [0.75, 0.94],
  ]
  for (const [rx, ry] of points) {
    await clickCanvasPoint(client, rect, rx, ry)
    await sleep(Math.min(400, waitMs))
    const after = await hashCanvas(client, canvasIndex)
    if (before && after && before !== after) {
      return { before, after, eventName: LEGEND_EVENT_NAME, rx, ry }
    }
  }
  throw new Error('Legend click did not change the rendered ECharts canvas')
}

async function dragDataZoomUntilCanvasDelta(client, canvasIndex, waitMs) {
  const rect = await getCanvasRect(client, canvasIndex)
  const before = await hashCanvas(client, canvasIndex)
  await dragCanvasPoint(client, rect, 0.42, 0.62, 0.92)
  await sleep(Math.min(600, waitMs))
  const after = await hashCanvas(client, canvasIndex)
  if (!before || !after || before === after) {
    throw new Error('dataZoom drag did not change the rendered ECharts canvas')
  }
  return { before, after, dataZoom: true }
}

function collectConsole(client) {
  const consoleEntries = []
  const pageErrors = []

  client.on('Runtime.exceptionThrown', (params) => {
    pageErrors.push(params.exceptionDetails?.text || params.exceptionDetails?.exception?.description || 'Runtime exception')
  })
  client.on('Runtime.consoleAPICalled', (params) => {
    consoleEntries.push({ level: params.type, text: formatConsoleArgs(params.args || []) })
  })
  client.on('Log.entryAdded', (params) => {
    if (params.entry) consoleEntries.push({ level: params.entry.level, text: params.entry.text || '' })
  })

  return { consoleEntries, pageErrors }
}

const SCENARIOS = {
  'chart-hover-tooltip': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/analysis/stats')
    await waitForText(client, '播放统计', waitMs)
    await waitForCanvasCount(client, 1, waitMs)
    return hoverUntilTooltip(client, 0, waitMs)
  },

  'legend-toggle': async ({ client, baseUrl, apiBaseUrl, waitMs }) => {
    const scenarioWaitMs = Math.max(waitMs, DEFAULT_ACCOUNT_CHART_WAIT_MS)
    const target = await resolveDataZoomPath(apiBaseUrl)
    await navigate(client, baseUrl, target.path)
    await waitForText(client, target.readyText, scenarioWaitMs)
    await clickText(client, '榜单成绩', scenarioWaitMs)
    await waitForText(client, target.marker, scenarioWaitMs)
    await waitForCanvasCount(client, 1, scenarioWaitMs)
    return { ...(await clickLegendUntilCanvasDelta(client, 0, scenarioWaitMs)), target: target.label }
  },

  'datazoom-drag': async ({ client, baseUrl, apiBaseUrl, waitMs }) => {
    const scenarioWaitMs = Math.max(waitMs, DEFAULT_DATAZOOM_WAIT_MS)
    const target = await resolveDataZoomPath(apiBaseUrl)
    await navigate(client, baseUrl, target.path)
    await waitForText(client, target.readyText, scenarioWaitMs)
    await clickText(client, '榜单成绩', scenarioWaitMs)
    await waitForText(client, target.marker, scenarioWaitMs)
    await clickText(client, '细节', scenarioWaitMs)
    await waitForCanvasCount(client, 1, scenarioWaitMs)
    return { ...(await dragDataZoomUntilCanvasDelta(client, 0, scenarioWaitMs)), target: target.label }
  },

  'mobile-tap-tooltip': async ({ client, baseUrl, waitMs, viewportName }) => {
    if (viewportName !== 'mobile') throw new Error('mobile-tap-tooltip requires --viewport mobile')
    await navigate(client, baseUrl, '/analysis/stats?period=lifetime')
    await waitForText(client, '听歌时钟', waitMs)
    return tapListeningClockUntilTooltip(client, waitMs)
  },

  'mobile-fullscreen': async ({ client, baseUrl, waitMs, viewportName }) => {
    if (viewportName !== 'mobile') throw new Error('mobile-fullscreen requires --viewport mobile')
    await navigate(client, baseUrl, '/analysis/stats?period=lifetime')
    await waitForText(client, '每日播放', waitMs)
    await clickByAriaLabel(client, '全屏查看每日播放', waitMs)
    await waitForSelector(client, '[data-mobile-fullscreen="chart"]', waitMs)
    const opened = await waitForCondition(
      async () => evaluate(client, `(() => {
        const dialog = document.querySelector('[data-mobile-fullscreen="chart"]');
        const canvas = dialog?.querySelector('canvas');
        return dialog && canvas && document.body.style.overflow === 'hidden'
          ? { path: location.pathname, canvasCount: dialog.querySelectorAll('canvas').length, bodyOverflow: document.body.style.overflow }
          : null;
      })()`),
      waitMs,
      'Fullscreen chart did not render a locked interactive canvas',
    )
    await clickByAriaLabel(client, '关闭每日播放全屏图表', waitMs)
    await waitForSelectorGone(client, '[data-mobile-fullscreen="chart"]', waitMs)
    const restored = await waitForCondition(
      async () => evaluate(client, `document.activeElement?.getAttribute('aria-label') === '全屏查看每日播放' ? ({ path: location.pathname }) : null`),
      waitMs,
      'Fullscreen chart did not restore focus to its trigger',
    )
    return { ...opened, focusRestored: Boolean(restored) }
  },
}

async function runScenario({ port, baseUrl, apiBaseUrl, scenario, waitMs, viewportName }) {
  const client = await makeClient(port)
  const { consoleEntries, pageErrors } = collectConsole(client)

  try {
    await setupPage(client, VIEWPORTS[viewportName])
    const evidence = await SCENARIOS[scenario]({ client, baseUrl, apiBaseUrl, waitMs, viewportName })
    const consoleErrors = consoleEntries.filter((entry) => ['error', 'assert'].includes(entry.level))
    const consoleWarnings = consoleEntries.filter((entry) => ['warning', 'warn'].includes(entry.level))
    const finalState = await pageState(client)
    const scrollOverflow = Math.max(0, finalState.scrollWidth - finalState.viewportWidth)

    return {
      scenario,
      viewport: viewportName,
      ok: consoleErrors.length === 0 && consoleWarnings.length === 0 && pageErrors.length === 0 && scrollOverflow === 0,
      failures: [
        ...(consoleErrors.length ? [`${consoleErrors.length} console error(s)`] : []),
        ...(consoleWarnings.length ? [`${consoleWarnings.length} console warning(s)`] : []),
        ...(pageErrors.length ? [`${pageErrors.length} page error(s)`] : []),
        ...(scrollOverflow ? [`horizontal overflow ${scrollOverflow}px`] : []),
      ],
      finalPath: finalState.path,
      consoleErrorCount: consoleErrors.length,
      consoleWarningCount: consoleWarnings.length,
      pageErrorCount: pageErrors.length,
      scrollOverflow,
      evidence,
      consoleErrors: consoleErrors.slice(0, 5),
      consoleWarnings: consoleWarnings.slice(0, 5),
      pageErrors: pageErrors.slice(0, 5),
    }
  } catch (error) {
    const failureState = await canvasState(client).catch(() => null)
    const scrollOverflow =
      failureState && Number.isFinite(failureState.scrollWidth) && Number.isFinite(failureState.viewportWidth)
        ? Math.max(0, failureState.scrollWidth - failureState.viewportWidth)
        : null

    return {
      scenario,
      viewport: viewportName,
      ok: false,
      failures: [error instanceof Error ? error.message : String(error)],
      finalPath: failureState?.path || null,
      consoleErrorCount: 0,
      consoleWarningCount: 0,
      pageErrorCount: pageErrors.length,
      scrollOverflow,
      evidence: failureState,
      consoleErrors: [],
      consoleWarnings: [],
      pageErrors: pageErrors.slice(0, 5),
    }
  } finally {
    client.close()
    await fetch(`http://127.0.0.1:${port}/json/close/${client.targetId}`).catch(() => {})
  }
}

function renderMarkdown(results) {
  const lines = [
    '# Frontend Chart Interaction Smoke',
    '',
    `> Generated: ${new Date().toISOString()}`,
    '',
    '| Scenario | Viewport | Status | Final path | Console errors | Warnings | Page errors | Scroll overflow |',
    '| --- | --- | --- | --- | ---: | ---: | ---: | ---: |',
  ]

  for (const row of results) {
    lines.push(
      `| ${row.scenario} | ${row.viewport} | ${row.ok ? 'PASS' : 'FAIL'} | \`${row.finalPath || '-'}\` | ${row.consoleErrorCount} | ${row.consoleWarningCount} | ${row.pageErrorCount} | ${row.scrollOverflow ?? '-'}px |`,
    )
  }

  const failed = results.filter((row) => !row.ok)
  if (failed.length > 0) {
    lines.push('')
    lines.push('## Failures')
    for (const row of failed) {
      lines.push('')
      lines.push(`- ${row.scenario}: ${row.failures.join('; ')}`)
      for (const error of row.consoleErrors) lines.push(`  - console ${error.level}: ${error.text}`)
      for (const warning of row.consoleWarnings || []) lines.push(`  - console ${warning.level}: ${warning.text}`)
      for (const error of row.pageErrors) lines.push(`  - page error: ${error}`)
    }
  }

  return lines.join('\n')
}

function formatConsoleArgs(args) {
  return args
    .map((arg) => arg.value ?? arg.description ?? arg.unserializableValue ?? '')
    .filter((value) => value !== '')
    .join(' ')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const chromePath = findChrome(args.chrome)
  const port = await getFreePort()
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-stats-chart-smoke-'))

  const chrome = spawn(
    chromePath,
    [
      '--headless=new',
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
    const results = []
    for (const scenario of args.scenarios) {
      process.stderr.write(`Running ${scenario} ... `)
      const result = await runScenario({
        port,
        baseUrl: args.baseUrl,
        apiBaseUrl: args.apiBaseUrl || args.baseUrl,
        scenario,
        waitMs: args.waitMs,
        viewportName: args.viewport,
      })
      results.push(result)
      process.stderr.write(`${result.ok ? 'PASS' : 'FAIL'}\n`)
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
