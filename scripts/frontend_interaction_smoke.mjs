#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 5000
const MOBILE_DATA_WAIT_MS = 30000
const DEFAULT_SCENARIOS = [
  'analysis-tabs',
  'billboard-routing',
  'ai-insights-tabs',
  'music-search-quick-open',
  'settings-controls',
  'settings-data-import',
  'theme-toggle',
]
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
  node scripts/frontend_interaction_smoke.mjs [options]

Options:
  --base-url <url>        Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>    Rewrite same-origin /api and /covers requests to this API URL
  --viewport <mode>       desktop or mobile, default desktop
  --scenario <a,b,c>      Comma-separated scenarios, default ${DEFAULT_SCENARIOS.join(',')}
  --wait-ms <ms>          Max wait for route/text assertions, default ${DEFAULT_WAIT_MS}
  --output <path>         Write JSON results to a file
  --chrome <path>         Chrome/Chromium executable path

Scenarios:
  analysis-tabs           Click Analysis subnav between stats and personal charts
  billboard-routing       Click Billboard subnav and browser back/forward
  ai-insights-tabs        Click AI Insights report/chat tabs and report type pills
  music-search-quick-open Open Masthead music search and navigate to the full search page
  settings-controls       Inspect server settings controls and verify local display preference
  settings-data-import    Verify data import cards and import actions without starting jobs
  theme-toggle            Toggle light/dark theme buttons
  mobile-bottom-navigation Verify mobile bottom navigation routes and active state
  mobile-section-sheet    Open the mobile section sheet and preserve time query state
  mobile-time-filter      Apply the mobile time-range sheet and verify URL state
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
  client.targetId = target.id
  return client
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

async function setupPage(client, baseUrl, apiBaseUrl, viewport) {
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Log.enable')
  await client.send('Network.enable')
  await setupApiRequestRewrite(client, baseUrl, apiBaseUrl)
  await client.send('Emulation.setDeviceMetricsOverride', viewport)
  await client.send('Emulation.setUserAgentOverride', { userAgent: viewport.userAgent })
}

async function navigate(client, baseUrl, path, waitMs) {
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

async function clickText(client, text, waitMs) {
  const clicked = await evaluate(client, `
    (() => {
      const targetText = ${JSON.stringify(text)};
      const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"], [role="option"]'))
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
  await waitForCondition(
    async () => evaluate(client, `
      (() => {
        const targetLabel = ${JSON.stringify(label)};
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"], [role="option"]'))
          .filter((el) => (el.getAttribute('aria-label') || '').trim() === targetLabel);
        const el = candidates[0];
        if (!el) return null;
        el.scrollIntoView({ block: 'center', inline: 'center' });
        el.click();
        return { path: location.pathname };
      })();
    `),
    waitMs,
    `Clickable aria-label not found: ${label}`,
  )
  await sleep(Math.min(250, waitMs))
}

async function clickTextWithin(client, selector, text, waitMs) {
  const clicked = await evaluate(client, `
    (() => {
      const root = document.querySelector(${JSON.stringify(selector)});
      const targetText = ${JSON.stringify(text)};
      if (!root) return false;
      const candidates = Array.from(root.querySelectorAll('button, a, [role="button"], [role="tab"], [role="option"], [role="radio"]'));
      const el = candidates.find((item) => {
        const text = (item.innerText || item.textContent || '').trim();
        return text === targetText || text.startsWith(targetText) || text.includes(targetText);
      });
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })();
  `)
  if (!clicked) throw new Error(`Clickable text not found in ${selector}: ${text}`)
  await sleep(Math.min(250, waitMs))
}

async function waitForSelector(client, selector, timeoutMs) {
  return waitForCondition(
    async () => evaluate(client, `
      (() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
          ? { path: location.pathname, selector: ${JSON.stringify(selector)} }
          : null;
      })();
    `),
    timeoutMs,
    `Expected visible selector: ${selector}`,
  )
}

async function fillInputByAriaLabel(client, label, value, waitMs) {
  const filled = await evaluate(client, `
    (() => {
      const targetLabel = ${JSON.stringify(label)};
      const value = ${JSON.stringify(value)};
      const input = Array.from(document.querySelectorAll('input, textarea'))
        .find((el) => (el.getAttribute('aria-label') || '').trim() === targetLabel);
      if (!input) return false;
      input.scrollIntoView({ block: 'center', inline: 'center' });
      input.focus();
      const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
      descriptor?.set?.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })();
  `)
  if (!filled) throw new Error(`Input aria-label not found: ${label}`)
  await sleep(Math.min(300, waitMs))
}

async function assertSwitchAvailable(client, label, waitMs) {
  return waitForCondition(
    async () => {
      return evaluate(client, `
        (() => {
          const targetText = ${JSON.stringify(label)};
          const el = Array.from(document.querySelectorAll('[role="switch"]'))
            .find((item) => (item.getAttribute('aria-label') || item.innerText || item.textContent || '').trim().includes(targetText));
          if (!el) return null;
          const checked = el.getAttribute('aria-checked');
          if (!['true', 'false'].includes(checked) || el.hasAttribute('disabled')) return null;
          return { found: true, checked };
        })();
      `)
    },
    waitMs,
    `Enabled switch with valid state not found: ${label}`,
  )
}

async function assertClickableTextCount(client, texts, minimum, waitMs) {
  return waitForCondition(
    async () => {
      const state = await evaluate(client, `
        (() => {
          const targetTexts = ${JSON.stringify(texts)};
          const isVisible = (el) => {
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
          };
          const count = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"], [role="option"]'))
            .filter((el) => isVisible(el))
            .filter((el) => {
              const text = (el.innerText || el.textContent || '').trim();
              return targetTexts.some((targetText) => text.includes(targetText));
            }).length;
          return { count, path: location.pathname };
        })();
      `)
      return state && state.count >= minimum ? state : null
    },
    waitMs,
    `Expected at least ${minimum} clickable control(s): ${texts.join(', ')}`,
  )
}

async function fetchLlmAvailability(client) {
  const availability = await evaluate(client, `
    (async () => {
      try {
        const response = await fetch('/api/settings', { headers: { Accept: 'application/json' } });
        if (!response.ok) return null;
        const settings = await response.json();
        return Boolean(settings.llm_enabled && settings.has_llm_key);
      } catch {
        return null;
      }
    })();
  `)
  return typeof availability === 'boolean' ? availability : null
}

async function pageState(client) {
  return evaluate(client, `
    (() => ({
      path: location.pathname,
      url: location.href,
      bodyText: document.body ? document.body.innerText : '',
      isDark: document.documentElement.classList.contains('dark'),
      theme: localStorage.getItem('theme'),
      chineseStyle: localStorage.getItem('chineseStyle'),
      scrollWidth: Math.max(document.body ? document.body.scrollWidth : 0, document.documentElement ? document.documentElement.scrollWidth : 0),
      viewportWidth: innerWidth,
      search: location.search,
    }))();
  `)
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

async function hasPageText(client, text) {
  const state = await pageState(client)
  return state.bodyText.includes(text)
}

async function expandSectionForText(client, sectionTitle, targetText, waitMs) {
  await waitForText(client, sectionTitle, waitMs)
  if (!(await hasPageText(client, targetText))) {
    await clickText(client, sectionTitle, waitMs)
  }
  await waitForText(client, targetText, waitMs)
}

async function openExistingArtistLanguageReview(client, waitMs) {
  const opened = await evaluate(client, `
    (() => {
      const button = Array.from(document.querySelectorAll('button'))
        .find((el) => (el.getAttribute('aria-label') || '').startsWith('打开审核记录 '));
      if (!button) return false;
      button.scrollIntoView({ block: 'center', inline: 'center' });
      button.click();
      return true;
    })();
  `)
  if (!opened) return false
  await waitForText(client, '仅批准有可审计证据的艺人级结论', waitMs)
  await clickText(client, '关闭', waitMs)
  return true
}

async function assertArtistLanguageHealthControls(client, waitMs) {
  await expandSectionForText(client, '艺人语言数据', 'Top 未知艺人', waitMs)
  await waitForAnyText(client, ['审核', '暂无高播放量未知艺人。'], waitMs)
  await openExistingArtistLanguageReview(client, waitMs)

  const artistName = await evaluate(client, `
    (async () => {
      const reviewButton = Array.from(document.querySelectorAll('button'))
        .find((el) => (el.getAttribute('aria-label') || '').startsWith('审核 '));
      if (reviewButton) return reviewButton.getAttribute('aria-label').slice('审核 '.length);

      for (const query of ['a', 'e', 'i', 'o', 'u', '周', '张', '陈']) {
        const response = await fetch('/api/music/search?' + new URLSearchParams({
          q: query,
          kind: 'artist',
          limit_per_type: '1',
        }));
        if (!response.ok) continue;
        const payload = await response.json();
        if (payload.artists?.[0]?.label) return payload.artists[0].label;
      }
      return null;
    })();
  `)
  if (!artistName) throw new Error('No artist is available for the non-mutating review control check')

  await fillInputByAriaLabel(client, '查找待审核艺人', artistName, waitMs)
  const selected = await waitForCondition(
    async () => evaluate(client, `
      (() => {
        const button = Array.from(document.querySelectorAll('button'))
          .find((el) => (el.getAttribute('aria-label') || '').startsWith('选择艺人 '));
        if (!button) return null;
        button.scrollIntoView({ block: 'center', inline: 'center' });
        button.click();
        return { selected: true, path: location.pathname };
      })();
    `),
    waitMs,
    'Artist search did not expose a selectable result',
  )
  if (!selected) throw new Error('Artist search selection failed')

  await waitForCondition(
    async () => evaluate(client, `
      (() => {
        const button = Array.from(document.querySelectorAll('button'))
          .find((el) => (el.innerText || el.textContent || '').trim() === '开始审核');
        if (!button) return null;
        const rect = button.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && !button.disabled
          ? { accessible: true, path: location.pathname }
          : null;
      })();
    `),
    waitMs,
    '开始审核 command is not accessible',
  )
}

async function waitForAnyText(client, texts, timeoutMs) {
  return waitForCondition(
    async () => {
      const state = await pageState(client)
      return texts.some((text) => state.bodyText.includes(text)) ? state : null
    },
    timeoutMs,
    `Expected one of page texts not found: ${texts.join(', ')}`,
  )
}

async function waitForPath(client, expectedPath, timeoutMs) {
  return waitForCondition(
    async () => {
      const state = await pageState(client)
      return state.path === expectedPath ? state : null
    },
    timeoutMs,
    `Expected path ${expectedPath}`,
  )
}

async function waitForSearchParam(client, key, expectedValue, timeoutMs) {
  return waitForCondition(
    async () => {
      const state = await pageState(client)
      return new URL(state.url).searchParams.get(key) === expectedValue ? state : null
    },
    timeoutMs,
    `Expected search parameter ${key}=${expectedValue}`,
  )
}

async function waitForCondition(check, timeoutMs, failureMessage) {
  const started = Date.now()
  let lastState = null
  while (Date.now() - started < timeoutMs) {
    lastState = await check()
    if (lastState) return lastState
    await sleep(150)
  }
  const suffix = lastState && lastState.path ? `; last path ${lastState.path}` : ''
  throw new Error(`${failureMessage}${suffix}`)
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
  'analysis-tabs': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/analysis/stats', waitMs)
    await waitForText(client, '播放统计', waitMs)
    await clickText(client, '播放排行', waitMs)
    await waitForPath(client, '/analysis/charts', waitMs)
    await waitForText(client, '播放排行', waitMs)
    await clickText(client, '播放统计', waitMs)
    await waitForPath(client, '/analysis/stats', waitMs)
    await waitForText(client, '播放统计', waitMs)
  },

  'billboard-routing': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/billboard', waitMs)
    await waitForText(client, 'Billboard 周榜', waitMs)
    await clickText(client, '每周榜首', waitMs)
    await waitForPath(client, '/billboard/number-ones', waitMs)
    await waitForText(client, '每周冠军歌曲', waitMs)
    await clickText(client, '总榜', waitMs)
    await waitForPath(client, '/billboard/all-time', waitMs)
    await waitForText(client, 'Billboard 总榜', waitMs)
    await clickText(client, '榜单记录', waitMs)
    await waitForPath(client, '/billboard/records', waitMs)
    await waitForText(client, '冠军圣殿', waitMs)
    await evaluate(client, 'history.back(); true;')
    await waitForPath(client, '/billboard/all-time', waitMs)
    await evaluate(client, 'history.forward(); true;')
    await waitForPath(client, '/billboard/records', waitMs)
  },

  'ai-insights-tabs': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/ai-insights', waitMs)
    await waitForText(client, 'AI 洞察', waitMs)

    const llmAvailable = await fetchLlmAvailability(client)
    if (llmAvailable === false) {
      await waitForText(client, 'AI 功能尚未配置', waitMs)
      await clickText(client, '问答', waitMs)
      await waitForText(client, 'AI 功能尚未配置', waitMs)
      await clickText(client, '报告', waitMs)
      await waitForText(client, 'AI 功能尚未配置', waitMs)
      return
    }

    await waitForText(client, '月报', waitMs)
    await clickText(client, '月报', waitMs)
    await waitForText(client, '月报', waitMs)
    await clickText(client, '年度叙事', waitMs)
    await waitForText(client, '年度叙事', waitMs)
    await clickText(client, '问答', waitMs)
    await waitForText(client, '对话历史', waitMs)
    await clickText(client, '报告', waitMs)
    await waitForText(client, 'AI 洞察', waitMs)
  },

  'music-search-quick-open': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/', waitMs)
    await clickByAriaLabel(client, '搜索音乐详情', waitMs)
    await waitForText(client, '输入歌曲、专辑或艺人名称开始查找', waitMs)
    await fillInputByAriaLabel(client, '搜索歌曲、专辑或艺人', 'Fixture', waitMs)
    await waitForAnyText(client, ['单曲', '专辑', '艺人', '没有找到匹配的音乐详情'], waitMs)
    await waitForText(client, '查看全部结果', waitMs)
    await clickText(client, '查看全部结果', waitMs)
    await waitForPath(client, '/music/search', waitMs)
    await waitForText(client, '音乐查找', waitMs)
  },

  'settings-controls': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/settings', waitMs)
    await waitForText(client, '参数与配置', waitMs)
    await waitForText(client, 'SPOTIFY 连接', waitMs)
    await waitForText(client, '数据与显示', waitMs)
    await waitForText(client, '榜单参数', waitMs)
    await waitForText(client, '归并与版本', waitMs)
    await waitForText(client, '数据导入', waitMs)

    await assertSwitchAvailable(client, '动态阈值', waitMs)
    await assertSwitchAvailable(client, '仅音乐', waitMs)

    await clickText(client, '原样显示', waitMs)
    await clickText(client, '简体中文', waitMs)
    await waitForCondition(
      async () => {
        const state = await pageState(client)
        return state.chineseStyle === 'simplified' ? state : null
      },
      waitMs,
      'Chinese display preference did not update to simplified',
    )
    await clickText(client, '简体中文', waitMs)
    await clickText(client, '原样显示', waitMs)
    await waitForCondition(
      async () => {
        const state = await pageState(client)
        return state.chineseStyle === 'original' ? state : null
      },
      waitMs,
      'Chinese display preference did not reset to original',
    )

    await clickText(client, '流派与语言', waitMs)
    await waitForText(client, '流派与语言数据健康', waitMs)
    await assertArtistLanguageHealthControls(client, waitMs)

    await waitForAnyText(client, ['连接 Spotify', '同步收藏时间'], waitMs)
  },

  'settings-data-import': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/settings', waitMs)
    await waitForText(client, '参数与配置', waitMs)
    await expandSectionForText(client, '数据导入', '串流数据', waitMs)
    await waitForText(client, '账号数据', waitMs)
    await waitForText(client, '当前数据库记录数', waitMs)
    await waitForText(client, '导入 Spotify 账号数据包', waitMs)
    await waitForAnyText(client, ['未导入', '已导入'], waitMs)
    await assertClickableTextCount(client, ['开始导入', '重新导入', '导入中...'], 2, waitMs)
  },

  'theme-toggle': async ({ client, baseUrl, waitMs }) => {
    await navigate(client, baseUrl, '/', waitMs)
    await clickText(client, '夜晚', waitMs)
    const dark = await pageState(client)
    if (!dark.isDark || dark.theme !== 'dark') throw new Error('Dark theme did not activate')
    await clickText(client, '白日', waitMs)
    const light = await pageState(client)
    if (light.isDark || light.theme !== 'light') throw new Error('Light theme did not activate')
  },

  'mobile-bottom-navigation': async ({ client, baseUrl, waitMs, viewportName }) => {
    if (viewportName !== 'mobile') throw new Error('mobile-bottom-navigation requires --viewport mobile')
    await navigate(client, baseUrl, '/', waitMs)
    await waitForSelector(client, '[data-mobile-shell="bottom-nav"]', waitMs)
    await clickTextWithin(client, '[data-mobile-shell="bottom-nav"]', '播放', waitMs)
    await waitForPath(client, '/analysis/stats', waitMs)
    await waitForCondition(
      async () => evaluate(client, `(() => {
        const link = Array.from(document.querySelectorAll('[data-mobile-shell="bottom-nav"] a'))
          .find((item) => (item.innerText || item.textContent || '').trim() === '播放');
        return link?.getAttribute('aria-current') === 'page' ? { path: location.pathname } : null;
      })()`),
      waitMs,
      'Mobile 播放 navigation item did not become current',
    )
    await clickTextWithin(client, '[data-mobile-shell="bottom-nav"]', '榜单', waitMs)
    await waitForPath(client, '/billboard', waitMs)
  },

  'mobile-section-sheet': async ({ client, baseUrl, waitMs, viewportName }) => {
    if (viewportName !== 'mobile') throw new Error('mobile-section-sheet requires --viewport mobile')
    await navigate(client, baseUrl, '/analysis/stats?period=year&period_value=2025', waitMs)
    await waitForText(client, '播放统计', waitMs)
    await clickByAriaLabel(client, '切换播放分析栏目，当前播放统计', waitMs)
    await waitForSelector(client, '[data-mobile-sheet="section-switcher"]', waitMs)
    await clickTextWithin(client, '[data-mobile-sheet="section-switcher"]', '播放排行', waitMs)
    await waitForPath(client, '/analysis/charts', waitMs)
    await waitForSearchParam(client, 'period', 'year', waitMs)
    await waitForSearchParam(client, 'period_value', '2025', waitMs)
  },

  'mobile-time-filter': async ({ client, baseUrl, waitMs, viewportName }) => {
    if (viewportName !== 'mobile') throw new Error('mobile-time-filter requires --viewport mobile')
    const dataWaitMs = Math.max(waitMs, MOBILE_DATA_WAIT_MS)
    await navigate(client, baseUrl, '/analysis/stats?period=lifetime', waitMs)
    await waitForText(client, '播放统计', dataWaitMs)
    await clickByAriaLabel(client, '选择时间范围，当前全部时间', dataWaitMs)
    await waitForSelector(client, '[data-mobile-sheet="time-range"]', waitMs)
    await clickTextWithin(client, '[data-mobile-sheet="time-range"]', '近 4 周', waitMs)
    await clickTextWithin(client, '[data-mobile-sheet="time-range"]', '应用时间范围', waitMs)
    await waitForSearchParam(client, 'period', 'last_4_weeks', waitMs)
  },
}

async function runScenario({ port, baseUrl, apiBaseUrl, scenario, waitMs, viewportName }) {
  const client = await makeClient(port)
  const { consoleEntries, pageErrors } = collectConsole(client)

  try {
    await setupPage(client, baseUrl, apiBaseUrl, VIEWPORTS[viewportName])
    await SCENARIOS[scenario]({ client, baseUrl, waitMs, viewportName })
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
      consoleErrors: consoleErrors.slice(0, 5),
      pageErrors: pageErrors.slice(0, 5),
    }
  } catch (error) {
    return {
      scenario,
      viewport: viewportName,
      ok: false,
      failures: [error instanceof Error ? error.message : String(error)],
      finalPath: null,
      consoleErrorCount: 0,
      consoleWarningCount: 0,
      pageErrorCount: pageErrors.length,
      scrollOverflow: null,
      consoleErrors: [],
      pageErrors: pageErrors.slice(0, 5),
    }
  } finally {
    client.close()
    await fetch(`http://127.0.0.1:${port}/json/close/${client.targetId}`).catch(() => {})
  }
}

function renderMarkdown(results) {
  const lines = [
    '# Frontend Interaction Smoke',
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
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-stats-interaction-smoke-'))

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
    const results = []
    for (const scenario of args.scenarios) {
      process.stderr.write(`Running ${scenario} ... `)
      const result = await runScenario({
        port,
        baseUrl: args.baseUrl,
        apiBaseUrl: args.apiBaseUrl,
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
