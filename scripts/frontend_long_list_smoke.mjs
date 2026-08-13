#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 8000
const DEFAULT_SCENARIOS = [
  'records-mini-rank',
  'all-time-table',
  'year-end-table',
  'community-feed',
  'recent-plays',
  'saved-tracks',
  'personal-rank-table',
]
const REWRITE_PATH_PREFIXES = ['/api', '/covers']

const VIEWPORT = {
  width: 1280,
  height: 900,
  deviceScaleFactor: 1,
  mobile: false,
  userAgent:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
}

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBaseUrl: null,
    scenarios: DEFAULT_SCENARIOS,
    waitMs: DEFAULT_WAIT_MS,
    output: null,
    chrome: null,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
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
  if (!Number.isFinite(args.waitMs) || args.waitMs < 500) throw new Error('--wait-ms must be at least 500')
  for (const scenario of args.scenarios) {
    if (!SCENARIOS[scenario]) throw new Error(`Unsupported scenario: ${scenario}`)
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_long_list_smoke.mjs [options]

Options:
  --base-url <url>        Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>    Rewrite same-origin /api and /covers requests to this API URL
  --scenario <a,b,c>      Comma-separated scenarios, default ${DEFAULT_SCENARIOS.join(',')}
  --wait-ms <ms>          Max wait for route/text/list assertions, default ${DEFAULT_WAIT_MS}
  --output <path>         Write JSON results to a file
  --chrome <path>         Chrome/Chromium executable path

Scenarios:
  records-mini-rank       Click a paginated Billboard Records mini-rank table
  all-time-table          Click Billboard All-Time table pagination
  year-end-table          Click Billboard Year-End pagination, or verify the capped table when only one page exists
  community-feed          Scroll Community Feed to trigger infinite loading
  recent-plays            Click Analysis Recent Plays pagination
  saved-tracks            Click Account Archive library pagination
  personal-rank-table     Click Analysis Personal Rank pagination
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

async function setupPage(client) {
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Log.enable')
  await client.send('Network.enable')
  await client.send('Emulation.setDeviceMetricsOverride', VIEWPORT)
  await client.send('Emulation.setUserAgentOverride', { userAgent: VIEWPORT.userAgent })
}

function rewriteRequestUrl(requestUrl, frontendBaseUrl, apiBaseUrl) {
  if (!apiBaseUrl) return null
  const frontendOrigin = new URL(frontendBaseUrl).origin
  const apiOrigin = new URL(apiBaseUrl).origin
  if (frontendOrigin === apiOrigin) return null

  const url = new URL(requestUrl)
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
      hasFatalText: /Internal Server Error|Failed to fetch dynamically imported module|ReferenceError|TypeError|Unhandled Runtime Error/.test(document.body ? document.body.innerText : ''),
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

async function scrollTextIntoView(client, text) {
  await evaluate(client, `
    (() => {
      const targetText = ${JSON.stringify(text)};
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const candidates = Array.from(document.querySelectorAll('h1,h2,h3,p,span,div'))
        .filter((el) => normalize(el.innerText || el.textContent || '').includes(targetText))
        .sort((a, b) => normalize(a.innerText || a.textContent || '').length - normalize(b.innerText || b.textContent || '').length);
      const el = candidates[0];
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'nearest' });
      return true;
    })();
  `)
  await sleep(200)
}

async function detectPageText(client, patternSource, timeoutMs, focusText = null) {
  return waitForCondition(
    async () => {
      const result = await evaluate(client, `
        (() => {
          const pattern = new RegExp(${JSON.stringify(patternSource)}, 'u');
          const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
          const textMatches = (el, value) => normalize(el.innerText || el.textContent || '').includes(value);
          const findScope = () => {
            const focusText = ${JSON.stringify(focusText)};
            if (!focusText) return document.body;
            const candidates = Array.from(document.querySelectorAll('h1,h2,h3,p,span,div'))
              .filter((el) => textMatches(el, focusText))
              .sort((a, b) => normalize(a.innerText || a.textContent || '').length - normalize(b.innerText || b.textContent || '').length);
            for (const candidate of candidates) {
              let current = candidate;
              for (let i = 0; current && i < 10; i += 1) {
                if (current.querySelectorAll('tbody tr, article').length > 0) return current;
                current = current.parentElement;
              }
            }
            return document.body;
          };
          const scope = findScope();
          let candidates = Array.from(scope.querySelectorAll('span,p,div'))
            .map((el) => normalize(el.innerText || el.textContent || ''))
            .filter((text) => text.length > 0 && text.length < 140 && pattern.test(text))
            .sort((a, b) => a.length - b.length);
          if (candidates.length === 0 && scope !== document.body) {
            candidates = Array.from(document.querySelectorAll('span,p,div'))
              .map((el) => normalize(el.innerText || el.textContent || ''))
              .filter((text) => text.length > 0 && text.length < 140 && pattern.test(text))
              .sort((a, b) => a.length - b.length);
          }
          const text = candidates[0] || '';
          return text ? { text, path: location.pathname } : null;
        })();
      `)
      return result || null
    },
    timeoutMs,
    `Expected pagination text matching /${patternSource}/`,
  )
}

async function getRowWindow(
  client,
  { rowSelector = 'tbody tr', focusText = null, pagePattern = null } = {},
) {
  return evaluate(client, `
    (() => {
      const rowSelector = ${JSON.stringify(rowSelector)};
      const focusText = ${JSON.stringify(focusText)};
      const pagePattern = ${JSON.stringify(pagePattern)};
      const pattern = pagePattern ? new RegExp(pagePattern, 'u') : null;
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const matchesFocus = (el) => !focusText || normalize(el.innerText || el.textContent || '').includes(focusText);
      const scopeFromFocus = () => {
        if (!focusText) return document.body;
        const candidates = Array.from(document.querySelectorAll('h1,h2,h3,p,span,div'))
          .filter(matchesFocus)
          .sort((a, b) => normalize(a.innerText || a.textContent || '').length - normalize(b.innerText || b.textContent || '').length);
        for (const candidate of candidates) {
          let current = candidate;
          for (let i = 0; current && i < 10; i += 1) {
            if (current.querySelectorAll(rowSelector).length > 0) return current;
            current = current.parentElement;
          }
        }
        return document.body;
      };
      let scope = document.body;
      if (focusText) scope = scopeFromFocus();
      if (pattern) {
        const searchRoot = scope === document.body ? document : scope;
        const textElements = Array.from(searchRoot.querySelectorAll('span,p,div'))
          .filter((el) => {
            const text = normalize(el.innerText || el.textContent || '');
            return text.length > 0 && text.length < 140 && pattern.test(text);
          })
          .sort((a, b) => normalize(a.innerText || a.textContent || '').length - normalize(b.innerText || b.textContent || '').length);
        for (const textEl of textElements) {
          let current = textEl;
          for (let i = 0; current && i < 10; i += 1) {
            if (current.querySelectorAll(rowSelector).length > 0) {
              scope = current;
              break;
            }
            if (searchRoot !== document && current === searchRoot) break;
            current = current.parentElement;
          }
          if (scope !== document.body || searchRoot !== document) break;
        }
      }
      if (scope === document.body && focusText) {
        scope = scopeFromFocus();
      }
      const rows = Array.from(scope.querySelectorAll(rowSelector));
      const sample = rows.slice(0, 8).map((row) => normalize(row.innerText || row.textContent || '').slice(0, 180));
      return {
        count: rows.length,
        sample,
        signature: sample.join(' || '),
      };
    })();
  `)
}

function assertRowWindowChange(beforeRows, afterRows) {
  if (beforeRows.count === 0) throw new Error('Before row window was empty')
  if (afterRows.count === 0) throw new Error('After row window was empty')
  if (beforeRows.signature === afterRows.signature) {
    throw new Error('Visible row window did not change after pagination')
  }
}

async function clickFirstEnabledPaginationButtonNearText(client, patternSource, focusText = null) {
  const result = await evaluate(client, `
    (() => {
      const pattern = new RegExp(${JSON.stringify(patternSource)}, 'u');
      const focusText = ${JSON.stringify(focusText)};
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const parseCurrentPage = (text) => {
        const patterns = [
          /第\\s*(\\d+)\\s*\\/\\s*(\\d+)\\s*页/,
          /(?:^|\\s)(\\d+)\\s*\\/\\s*(\\d+)(?:\\s|$)/,
          /显示\\s*(\\d+)\\s*-\\s*(\\d+)\\s*\\/\\s*总数\\s*(\\d+)\\s*条/,
          /(\\d+)\\s*—\\s*(\\d+)\\s*\\/\\s*(\\d+)/,
        ];
        for (const item of patterns) {
          const match = text.match(item);
          if (!match) continue;
          if (item.source.startsWith('显示') || item.source.includes('—')) {
            const start = Number(match[1]);
            const end = Number(match[2]);
            const total = Number(match[3]);
            const pageSize = Math.max(1, end - start + 1);
            return {
              current: Math.max(1, Math.ceil(start / pageSize)),
              totalPages: Math.max(1, Math.ceil(total / pageSize)),
            };
          }
          return { current: Number(match[1]), totalPages: Number(match[2]) };
        }
        return null;
      };
      const focusScope = () => {
        if (!focusText) return document.body;
        const candidates = Array.from(document.querySelectorAll('h1,h2,h3,p,span,div'))
          .filter((el) => normalize(el.innerText || el.textContent || '').includes(focusText))
          .sort((a, b) => normalize(a.innerText || a.textContent || '').length - normalize(b.innerText || b.textContent || '').length);
        let buttonOnlyScope = null;
        for (const candidate of candidates) {
          let current = candidate;
          for (let i = 0; current && i < 10; i += 1) {
            const hasButtons = current.querySelectorAll('button').length > 0;
            const hasPaginationText = Array.from(current.querySelectorAll('span,p,div'))
              .some((el) => {
                const text = normalize(el.innerText || el.textContent || '');
                return text.length > 0 && text.length < 140 && pattern.test(text);
              });
            if (hasButtons && hasPaginationText) return current;
            if (hasButtons && !buttonOnlyScope) buttonOnlyScope = current;
            current = current.parentElement;
          }
        }
        return buttonOnlyScope || document.body;
      };
      const scope = focusScope();
      let textElements = Array.from(scope.querySelectorAll('span,p,div'))
        .filter((el) => {
          const text = normalize(el.innerText || el.textContent || '');
          return text.length > 0 && text.length < 140 && pattern.test(text);
        })
        .sort((a, b) => normalize(a.innerText).length - normalize(b.innerText));
      if (textElements.length === 0 && scope !== document.body) {
        textElements = Array.from(document.querySelectorAll('span,p,div'))
          .filter((el) => {
            const text = normalize(el.innerText || el.textContent || '');
            return text.length > 0 && text.length < 140 && pattern.test(text);
          })
          .sort((a, b) => normalize(a.innerText).length - normalize(b.innerText));
      }
      const textEl = textElements[0];
      if (!textEl) return { ok: false, reason: 'pagination text not found' };
      const pageText = normalize(textEl.innerText || textEl.textContent || '');
      const pageInfo = parseCurrentPage(pageText);
      let container = textEl;
      for (let i = 0; container && i < 8; i += 1) {
        const buttons = Array.from(container.querySelectorAll('button'))
          .filter((button) => !button.disabled && button.getAttribute('aria-disabled') !== 'true');
        if (buttons.length > 0) {
          const buttonName = (button) => normalize(
            button.getAttribute('aria-label') || button.getAttribute('title') || button.innerText || button.textContent || '',
          );
          const nextTextButton = buttons.find((button) => buttonName(button).includes('下一页'));
          const numericNextButton = pageInfo
            ? buttons.find((button) => {
                const text = normalize(button.innerText || button.textContent || '');
                return /^\\d+$/.test(text) && Number(text) > pageInfo.current;
              })
            : null;
          const iconNextButton = buttons.find((button) => normalize(button.innerText || button.textContent || '') === '');
          const fallbackButton = buttons.find((button) => {
            const text = normalize(button.innerText || button.textContent || '');
            return !pageInfo || text !== String(pageInfo.current);
          }) || buttons[0];
          const button = nextTextButton || numericNextButton || iconNextButton || fallbackButton;
          button.scrollIntoView({ block: 'center', inline: 'center' });
          const rect = button.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          const pointEl = document.elementFromPoint(x, y);
          return {
            ok: true,
            pageText,
            buttonText: buttonName(button),
            x,
            y,
            pointText: pointEl ? normalize(pointEl.innerText || pointEl.textContent || pointEl.getAttribute('aria-label') || '') : '',
            pointTag: pointEl ? pointEl.tagName : '',
            clicked: true,
          };
        }
        container = container.parentElement;
      }
      return { ok: false, reason: 'enabled pagination button not found', pageText };
    })();
  `)
  if (!result.ok) throw new Error(result.reason || 'Could not click pagination button')
  await sleep(250)
  await client.send('Page.bringToFront')
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x: result.x,
    y: result.y,
    button: 'none',
    buttons: 0,
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: result.x,
    y: result.y,
    button: 'left',
    buttons: 1,
    clickCount: 1,
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: result.x,
    y: result.y,
    button: 'left',
    buttons: 0,
    clickCount: 1,
  })
  await sleep(350)
  return result
}

async function exercisePaginatedList({
  client,
  baseUrl,
  waitMs,
  route,
  readyText,
  pagePattern,
  focusText,
  rowSelector = 'tbody tr',
  nextButtonSelector = null,
}) {
  await navigate(client, baseUrl, route)
  await waitForText(client, readyText, waitMs)
  if (focusText) await scrollTextIntoView(client, focusText)
  const beforePage = await detectPageText(client, pagePattern, waitMs, focusText)
  const beforeRows = await waitForCondition(
    async () => {
      const rows = await getRowWindow(client, { rowSelector, focusText, pagePattern })
      return rows.count > 0 ? rows : null
    },
    waitMs,
    'Before row window was empty',
  )
  const clickResult = nextButtonSelector
    ? await evaluate(client, `(() => {
        const button = document.querySelector(${JSON.stringify(nextButtonSelector)});
        if (!(button instanceof HTMLButtonElement) || button.disabled) {
          return { ok: false, reason: 'configured next-page button was not ready' };
        }
        button.scrollIntoView({ block: 'center', inline: 'center' });
        button.click();
        return { ok: true, buttonText: button.getAttribute('aria-label') || button.innerText || '' };
      })()`)
    : await clickFirstEnabledPaginationButtonNearText(client, pagePattern, focusText)
  if (!clickResult.ok) throw new Error(clickResult.reason || 'Could not click pagination button')
  let afterRows
  try {
    afterRows = await waitForCondition(
      async () => {
        const rows = await getRowWindow(client, { rowSelector, focusText, pagePattern })
        return rows.count > 0 && rows.signature !== beforeRows.signature ? rows : null
      },
      waitMs,
      'Visible row window did not change after pagination click',
    )
  } catch (error) {
    const currentPage = await detectPageText(client, pagePattern, Math.min(1500, waitMs), focusText).catch(() => null)
    const currentRows = await getRowWindow(client, { rowSelector, focusText, pagePattern }).catch(() => null)
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(
      `${message}; clicked=${clickResult.buttonText || '[icon]'}; point=${clickResult.pointTag}:${clickResult.pointText || '-'}@${Math.round(clickResult.x)},${Math.round(clickResult.y)}; beforePage=${beforePage.text}; currentPage=${currentPage?.text || '-'}; beforeSample=${beforeRows.sample[0] || '-'}; currentSample=${currentRows?.sample?.[0] || '-'}`,
    )
  }
  const afterPage = await detectPageText(client, pagePattern, waitMs, focusText)
  assertRowWindowChange(beforeRows, afterRows)

  return {
    beforePage: beforePage.text,
    afterPage: afterPage.text,
    beforeRows: beforeRows.count,
    afterRows: afterRows.count,
    beforeSample: beforeRows.sample[0] || '',
    afterSample: afterRows.sample[0] || '',
  }
}

async function exercisePaginatedOrCappedList(options) {
  const {
    client,
    waitMs,
    focusText,
    pagePattern,
    rowSelector = 'tbody tr',
    maxVisibleRows = 50,
  } = options

  try {
    return await exercisePaginatedList(options)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (!message.includes('Expected pagination text matching')) {
      throw error
    }
  }

  if (focusText) await scrollTextIntoView(client, focusText)
  const rows = await waitForCondition(
    async () => {
      const result = await getRowWindow(client, { rowSelector, focusText, pagePattern: null })
      return result.count > 0 ? result : null
    },
    waitMs,
    'Capped table did not render visible rows',
  )
  if (rows.count > maxVisibleRows) {
    throw new Error(`Capped table rendered ${rows.count} rows, expected <= ${maxVisibleRows}`)
  }

  return {
    beforePage: `capped <=${maxVisibleRows}`,
    afterPage: 'no pagination',
    beforeRows: rows.count,
    afterRows: rows.count,
    beforeSample: rows.sample[0] || '',
    afterSample: rows.sample[0] || '',
    capped: true,
  }
}

async function exerciseCommunityFeed({ client, baseUrl, waitMs }) {
  const openAllFeed = async () => {
    await navigate(client, baseUrl, '/community')
    await waitForText(client, '榜单社区', waitMs)
    const clicked = await evaluate(client, `(() => {
      const button = Array.from(document.querySelectorAll('.community-feed-toggle button'))
        .find((item) => (item.innerText || item.textContent || '').trim().startsWith('全部'));
      if (!button) return false;
      button.click();
      return true;
    })()`)
    if (!clicked) throw new Error('Community 全部 feed control was not ready')
  }

  await openAllFeed()

  // Wait for initial posts to render
  const waitForPosts = () => waitForCondition(
    async () => {
      const rows = await getRowWindow(client, { rowSelector: 'article' })
      return rows.count > 0 ? rows : null
    },
    waitMs,
    'Community feed did not render posts',
  )
  let beforeRows
  try {
    beforeRows = await waitForPosts()
  } catch {
    await openAllFeed()
    beforeRows = await waitForPosts()
  }

  // Track /api/community network responses via CDP
  const communityRequests = []
  const responseHandler = (params) => {
    const url = params.response?.url || ''
    if (url.includes('/api/community') && params.response?.status === 200) {
      communityRequests.push({ url, status: params.response.status })
    }
  }
  client.on('Network.responseReceived', responseHandler)

  // Record baseline before scrolling
  const initialCount = communityRequests.length

  // Scroll to trigger Virtuoso endReached → infinite load
  await evaluate(client, `
    (() => {
      const sentinels = Array.from(document.querySelectorAll('div')).filter((el) => el.classList.contains('h-1'));
      const target = sentinels.at(-1);
      if (target) target.scrollIntoView({ block: 'center', inline: 'nearest' });
      else window.scrollTo(0, document.body.scrollHeight);
      return true;
    })();
  `)
  await sleep(500)

  // Second scroll
  await evaluate(client, `
    (() => {
      const sentinels = Array.from(document.querySelectorAll('div')).filter((el) => el.classList.contains('h-1'));
      const target = sentinels.at(-1);
      if (target) target.scrollIntoView({ block: 'center', inline: 'nearest' });
      else window.scrollTo(0, document.body.scrollHeight);
      return true;
    })();
  `)

  // Wait for at least one new /api/community 200 response after scrolling
  await waitForCondition(
    async () => {
      return communityRequests.length > initialCount ? communityRequests : null
    },
    5000,
    'Community infinite feed did not trigger /api/community request after scrolling',
  )

  return {
    beforePostCount: beforeRows.count,
    communityRequestsTriggered: communityRequests.length,
    newRequestsAfterScroll: communityRequests.length - initialCount,
    afterScrollUrls: communityRequests.slice(initialCount).map(r => r.url),
  }
}

const SCENARIOS = {
  'records-mini-rank': (ctx) => exercisePaginatedList({
    ...ctx,
    waitMs: Math.max(ctx.waitMs, 20000),
    route: '/billboard/records',
    readyText: '冠军圣殿',
    pagePattern: '\\d+\\s*—\\s*\\d+\\s*/\\s*\\d+',
    focusText: '空降冠军',
  }),
  'all-time-table': (ctx) => exercisePaginatedList({
    ...ctx,
    route: '/billboard/all-time',
    readyText: 'Billboard 总榜',
    pagePattern: '\\b\\d+\\s*/\\s*\\d+\\b',
    focusText: 'Billboard 总榜',
  }),
  'year-end-table': (ctx) => exercisePaginatedOrCappedList({
    ...ctx,
    waitMs: Math.max(ctx.waitMs, 20000),
    route: '/billboard/year-end',
    readyText: 'Billboard 年榜',
    pagePattern: '\\b\\d+\\s*/\\s*\\d+\\b',
    focusText: 'Billboard 年榜',
    maxVisibleRows: 50,
  }),
  'community-feed': (ctx) => exerciseCommunityFeed({
    ...ctx,
    waitMs: Math.max(ctx.waitMs, 20000),
  }),
  'recent-plays': (ctx) => exercisePaginatedList({
    ...ctx,
    route: '/analysis/stats',
    readyText: '最近播放记录',
    pagePattern: '共\\s*\\d+\\s*条，第\\s*\\d+\\s*/\\s*\\d+\\s*页',
    focusText: '最近播放记录',
  }),
  'saved-tracks': (ctx) => exercisePaginatedList({
    ...ctx,
    route: '/account',
    readyText: '收藏库',
    pagePattern: '第\\s*\\d+\\s*/\\s*\\d+\\s*页',
    focusText: '收藏库',
    rowSelector: '.archive-library-row',
    nextButtonSelector: '.archive-pagination button[aria-label="下一页"]',
  }),
  'personal-rank-table': (ctx) => exercisePaginatedList({
    ...ctx,
    route: '/analysis/charts',
    readyText: '播放排行',
    pagePattern: '显示\\s*\\d+\\s*-\\s*\\d+\\s*/\\s*总数\\s*\\d+\\s*条',
    focusText: '歌曲榜',
  }),
  'playback-records-mini-rank': (ctx) => exercisePaginatedList({
    ...ctx,
    route: '/analysis/records',
    readyText: '高光时刻',
    pagePattern: '\\d+\\s*—\\s*\\d+\\s*/\\s*\\d+',
    focusText: '单日爆听',
  }),
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

async function runScenario({ port, baseUrl, apiBaseUrl, scenario, waitMs }) {
  const client = await makeClient(port)
  const { consoleEntries, pageErrors } = collectConsole(client)

  try {
    await setupPage(client)
    await setupApiRequestRewrite(client, baseUrl, apiBaseUrl)
    const details = await SCENARIOS[scenario]({ client, baseUrl, waitMs })
    const consoleErrors = consoleEntries.filter((entry) => ['error', 'assert'].includes(entry.level))
    const consoleWarnings = consoleEntries.filter((entry) => ['warning', 'warn'].includes(entry.level))
    const finalState = await pageState(client)
    const scrollOverflow = Math.max(0, finalState.scrollWidth - finalState.viewportWidth)

    return {
      scenario,
      ok: !finalState.hasFatalText
        && consoleErrors.length === 0
        && consoleWarnings.length === 0
        && pageErrors.length === 0
        && scrollOverflow === 0,
      failures: [
        ...(finalState.hasFatalText ? ['fatal text found in page body'] : []),
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
      details,
      consoleErrors: consoleErrors.slice(0, 5),
      consoleWarnings: consoleWarnings.slice(0, 5),
      pageErrors: pageErrors.slice(0, 5),
    }
  } catch (error) {
    return {
      scenario,
      ok: false,
      failures: [error instanceof Error ? error.message : String(error)],
      finalPath: null,
      consoleErrorCount: 0,
      consoleWarningCount: 0,
      pageErrorCount: pageErrors.length,
      scrollOverflow: null,
      details: null,
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
    '# Frontend Long List Smoke',
    '',
    `> Generated: ${new Date().toISOString()}`,
    '',
    '| Scenario | Status | Before | After | Rows | Console errors | Warnings | Page errors | Scroll overflow |',
    '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |',
  ]

  for (const row of results) {
    const isCommunity = row.scenario === 'community-feed'
    const before = row.details?.beforePage || (isCommunity && row.details?.beforePostCount != null ? `${row.details.beforePostCount} posts` : null) || '-'
    const after = row.details?.afterPage || (isCommunity && row.details?.newRequestsAfterScroll != null ? `+${row.details.newRequestsAfterScroll} req` : null) || '-'
    const rows = row.details
      ? (isCommunity
        ? `${row.details.communityRequestsTriggered ?? '-'} total`
        : `${row.details.beforeRows}->${row.details.afterRows}`)
      : '-'
    lines.push(
      `| ${row.scenario} | ${row.ok ? 'PASS' : 'FAIL'} | \`${before}\` | \`${after}\` | ${rows} | ${row.consoleErrorCount} | ${row.consoleWarningCount} | ${row.pageErrorCount} | ${row.scrollOverflow ?? '-'}px |`,
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
      for (const warning of row.consoleWarnings) lines.push(`  - console ${warning.level}: ${warning.text}`)
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
  const profileDir = await mkdtemp(join(tmpdir(), 'spotify-stats-long-list-smoke-'))

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
      results.push(await runScenario({
        port,
        baseUrl: args.baseUrl,
        apiBaseUrl: args.apiBaseUrl,
        scenario,
        waitMs: args.waitMs,
      }))
    }

    const markdown = renderMarkdown(results)
    console.log(markdown)
    if (args.output) {
      await writeFile(args.output, JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2))
    }

    return results.every((result) => result.ok) ? 0 : 1
  } finally {
    await cleanup()
  }
}

main().then(
  (code) => process.exit(code),
  async (error) => {
    console.error(error)
    process.exit(1)
  },
)
