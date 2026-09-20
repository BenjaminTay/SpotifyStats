#!/usr/bin/env node

import { spawn, execFileSync } from 'node:child_process'
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import net from 'node:net'
import { fileURLToPath } from 'node:url'
import { SCHEMA_VERSION, DEFAULT_ROUTES, routeContract, coreReady, fingerprint, summarizeAttempts, snapshotState, apiTerminalState } from './lib/performance_browser_contract.mjs'
import { findChrome } from './lib/chrome_executable.mjs'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_WAIT_MS = 5000
const BUDGET_RETRY_LIMIT = 1
const REWRITE_PATH_PREFIXES = ['/api', '/covers']
const BUDGET_CHECKS = [
  { key: 'lcp', label: 'LCP', budgetKey: 'maxLcpMs', unit: 'ms' },
  { key: 'cls', label: 'CLS', budgetKey: 'maxCls', unit: '' },
  { key: 'tbtApprox', label: 'TBT approx', budgetKey: 'maxTbtMs', unit: 'ms' },
  { key: 'resourceCount', label: 'Resource count', budgetKey: 'maxResourceCount', unit: ' requests' },
  { key: 'encodedResourceKB', label: 'Encoded resources', budgetKey: 'maxEncodedResourceKB', unit: 'KB' },
  { key: 'scrollOverflowPx', label: 'Scroll overflow', budgetKey: 'maxScrollOverflowPx', unit: 'px' },
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

const VITALS_OBSERVER = `
(() => {
  window.__codexVitals = { cls: 0, lcp: 0, longTasks: [] };
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
  const bodyScrollWidth = document.body ? document.body.scrollWidth : null;
  const documentScrollWidth = document.documentElement ? document.documentElement.scrollWidth : null;
  const widestScrollWidth = Math.max(bodyScrollWidth || 0, documentScrollWidth || 0);
  const tbt = (vitals.longTasks || [])
    .filter((entry) => entry.startTime >= fcp && entry.startTime <= performance.now())
    .reduce((sum, entry) => sum + Math.max(0, entry.duration - 50), 0);

  return {
    url: location.href,
    title: document.title,
    lcp: (lcpEntry && (lcpEntry.renderTime || lcpEntry.loadTime || lcpEntry.startTime)) || vitals.lcp || null,
    cls: vitals.cls || 0,
    inp: null,
    inpEvidence: "not_measured; no synthetic interaction",
    observationEnd: performance.now(),
    tbtApprox: tbt,
    fcp,
    domContentLoaded: nav ? nav.domContentLoadedEventEnd : null,
    load: nav ? nav.loadEventEnd : null,
    responseEnd: nav ? nav.responseEnd : null,
    transferKB: nav ? Math.round((nav.transferSize || 0) / 102.4) / 10 : null,
    encodedResourceKB: Math.round(resources.reduce((sum, entry) => sum + (entry.encodedBodySize || 0), 0) / 102.4) / 10,
    resourceCount: resources.length,
    bodyScrollWidth,
    documentScrollWidth,
    scrollOverflowPx: Math.max(0, widestScrollWidth - innerWidth),
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
    contextFile: null,
    dbPath: null,
    dataset: "unknown",
    routeParams: {},
    browserPidFile: null,
    surface: "public-readonly",
    maxLcpMs: null,
    maxCls: null,
    maxTbtMs: null,
    maxResourceCount: null,
    maxEncodedResourceKB: null,
    maxScrollOverflowPx: null,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
    else if (arg === '--routes') args.routes = argv[++i].split(',').map((route) => route.trim()).filter(Boolean)
    else if (arg === '--context-file') args.contextFile = argv[++i]
    else if (arg === '--db-path') args.dbPath = argv[++i]
    else if (arg === '--dataset') args.dataset = argv[++i]
    else if (arg === '--route-params') args.routeParams = JSON.parse(argv[++i])
    else if (arg === '--browser-pid-file') args.browserPidFile = argv[++i]
    else if (arg === '--surface') args.surface = argv[++i]
    else if (arg === '--wait-ms') args.waitMs = Number(argv[++i])
    else if (arg === '--viewport') {
      const value = argv[++i]
      args.viewports = value === 'both' ? ['desktop', 'mobile'] : [value === 'phone' ? 'mobile' : value]
    } else if (arg === '--output') args.output = argv[++i]
    else if (arg === '--chrome') args.chrome = argv[++i]
    else if (arg === '--max-lcp-ms') args.maxLcpMs = parseBudgetNumber(argv[++i], '--max-lcp-ms')
    else if (arg === '--max-cls') args.maxCls = parseBudgetNumber(argv[++i], '--max-cls')
    else if (arg === '--max-tbt-ms') args.maxTbtMs = parseBudgetNumber(argv[++i], '--max-tbt-ms')
    else if (arg === '--max-resource-count') args.maxResourceCount = parseBudgetNumber(argv[++i], '--max-resource-count')
    else if (arg === '--max-encoded-resource-kb') args.maxEncodedResourceKB = parseBudgetNumber(argv[++i], '--max-encoded-resource-kb')
    else if (arg === '--max-scroll-overflow-px') args.maxScrollOverflowPx = parseBudgetNumber(argv[++i], '--max-scroll-overflow-px')
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

  for (const url of [args.baseUrl, args.apiBaseUrl].filter(Boolean)) {
    if (!['localhost','127.0.0.1','[::1]'].includes(new URL(url).hostname)) throw new Error('Only loopback URLs allowed')
  }
  args.routes = args.routes.map(route => route.replace(/\{(\w+)\}/g, (_, key) => encodeURIComponent(args.routeParams[key] ?? `{${key}}`)))
  return args
}

function parseBudgetNumber(value, optionName) {
  const number = Number(value)
  if (!Number.isFinite(number) || number < 0) {
    throw new Error(`${optionName} must be a non-negative number`)
  }
  return number
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_web_vitals_probe.mjs [options]

Options:
  --context-file <path> Shared performance context JSON
  --db-path <path>       Read-only DB identity
  --dataset <label>      seed / online_backup / unknown
  --route-params <json>  track_id, project_id, artist for default detail routes
  --browser-pid-file <path> For resource sampling
  --surface <name>       public-readonly by default
  --base-url <url>       Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>   Rewrite same-origin /api and /covers requests to this API URL
  --routes <a,b,c>       Comma-separated route paths, default ${DEFAULT_ROUTES.join(',')}
  --viewport <mode>      desktop, mobile, or both, default both
  --wait-ms <ms>         Wait after load before reading metrics, default ${DEFAULT_WAIT_MS}
  --output <path>        Write JSON results to a file
  --chrome <path>        Chrome/Chromium executable path
  --max-lcp-ms <ms>      Fail when any measured LCP is above this budget
  --max-cls <score>      Fail when any measured CLS is above this budget
  --max-tbt-ms <ms>      Fail when any measured TBT approx is above this budget
  --max-resource-count <n>
                         Fail when any route loads more resources than this budget
  --max-encoded-resource-kb <kb>
                         Fail when any route loads more encoded resource KB than this budget
  --max-scroll-overflow-px <px>
                         Fail when document/body scroll width exceeds viewport by more than this budget
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
  client.on('Fetch.requestPaused', (params) => {
    const parsed = new URL(params.request.url)
    if ((['http:','https:'].includes(parsed.protocol) && !['localhost','127.0.0.1','[::1]'].includes(parsed.hostname)) || !['GET','HEAD'].includes(params.request.method)) {
      void client.send('Fetch.failRequest', {requestId:params.requestId,errorReason:'BlockedByClient'}).catch(()=>{})
      return
    }
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
      const { resolve, reject, timer } = this.pending.get(message.id)
      clearTimeout(timer)
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
      const timer = setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`CDP call timed out: ${method}`))
        }
      }, 15000)
      this.pending.set(id, { resolve, reject, timer })
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
    for (const {reject,timer} of this.pending.values()) { clearTimeout(timer);reject(new Error("CDP closed")) }
    this.pending.clear()
    this.ws.close()
  }
}

async function measureRoute({ port, baseUrl, apiBaseUrl, route, viewportName, waitMs, context, surface, attempt }) {
  const viewport = VIEWPORTS[viewportName]
  const started = Date.now()
  const sample = { ...context, schema_version:SCHEMA_VERSION, sample_id:crypto.randomUUID(), kind:'page', target:route,
    params:[...new URL(route,baseUrl).searchParams], filter_fingerprint:fingerprint([...new URL(route,baseUrl).searchParams]),
    filter_fingerprint_scope:'URL params; actual API params recorded in waterfall',
    presentation:viewportName==='mobile'?'Phone':'Desktop', viewport:{width:viewport.width,height:viewport.height},
    process:{state:'unknown',id:null,evidence:'new browser target; backend process state not observed'},
    snapshot:{state:'unknown',source_revision:null,target_revision:null,builder_version:null,request_key:null,cache_key:null,evidence:'per API response in waterfall'},
    http:{status:null,error_type:null,raw_bytes:null,compressed_bytes:null,content_encoding:null,size_evidence:'document Network response'},
    timing:{total_ms:null,phases_ms:{}}, started_at:started/1000, ended_at:null, attempt, sequence:attempt-1, concurrency_group:null,
    instrumentation:{builder_calls:null,singleflight_calls:null,evidence:'not_exposed'},success:false, route, viewportName }
  const requests=[]
  let client, target
  try {
    const spec=routeContract(route)
    if (route.includes('%7B')) throw new Error('Missing route-params for dynamic route')
    target = await createTarget(port)
    client = await new CdpClient(target.webSocketDebuggerUrl).connect()
    await client.send('Page.enable');await client.send('Runtime.enable');await client.send('Network.enable')
    await client.send('Network.setExtraHTTPHeaders',{headers:{'X-SpotifyStats-Surface':surface}})
    const pendingBodies=new Set()
    client.on('Network.requestWillBeSent', p=>{
      requests.push({request_id:p.requestId,url:p.request.url,method:p.request.method,type:p.type,
        start:p.timestamp,start_wall:p.wallTime,initiator:p.initiator,finished:false,attempt:requests.filter(r=>r.url===p.request.url).length+1})
    })
    const lookup=id=>requests.findLast(r=>r.request_id===id)
    client.on('Network.responseReceived',p=>{
      const r=lookup(p.requestId);if(!r)return
      Object.assign(r,{status:p.response.status,response_start:p.timestamp,headers:p.response.headers,
        content_encoding:p.response.headers['content-encoding']||p.response.headers['Content-Encoding']||'identity'})
      if(p.type==='Document')Object.assign(sample.http,{status:p.response.status,content_encoding:r.content_encoding,compressed_bytes:Number(p.response.headers['Content-Length']??p.response.headers['content-length'])||null})
    })
    client.on('Network.loadingFailed',p=>{
      const r=lookup(p.requestId);if(r)Object.assign(r,{error_type:p.canceled?'Cancelled':p.errorText,end:p.timestamp,finished:true})
    })
    client.on('Network.loadingFinished',p=>{
      const r=lookup(p.requestId);if(!r)return
      Object.assign(r,{end:p.timestamp,finished:true,transfer_bytes:p.encodedDataLength})
      const length=r.headers?.["Content-Length"]??r.headers?.["content-length"];if(length!=null){r.compressed_bytes=Number(length);r.size_evidence="HTTP Content-Length body bytes"}
      if(new URL(r.url).pathname.startsWith('/api/')) {
        const promise=client.send('Network.getResponseBody',{requestId:p.requestId}).then(body=>{
          const raw=Buffer.from(body.body,body.base64Encoded?'base64':'utf8');r.raw_bytes=raw.length
          try {const payload=JSON.parse(raw.toString());r.valid_json=payload!=null && typeof payload==='object' && Object.keys(payload).length>0;r.snapshot=snapshotState(payload,r.headers)
            r.application_error=Boolean(payload.error || ['error','unavailable'].includes(payload.status) || ['unavailable','missing','error'].includes(payload.snapshot_status));
          } catch {r.valid_json=false;r.error_type='InvalidJSONResponse'}
        }).catch(()=>{r.valid_json=false;r.error_type='ResponseBodyUnavailable'}).finally(()=>pendingBodies.delete(promise))
        pendingBodies.add(promise)
      }
    })
    await setupApiRequestRewrite(client, baseUrl, apiBaseUrl)
    await client.send('Emulation.setDeviceMetricsOverride',{width:viewport.width,height:viewport.height,deviceScaleFactor:viewport.deviceScaleFactor,mobile:viewport.mobile})
    await client.send('Emulation.setUserAgentOverride',{userAgent:viewport.userAgent})
    await client.send('Page.addScriptToEvaluateOnNewDocument',{source:VITALS_OBSERVER})
    const navigationStart=Date.now()
    await client.send('Page.navigate',{url:new URL(route,baseUrl).toString()})
    const deadline=navigationStart+waitMs
    let ready, dom
    do {
      const state=await client.send('Runtime.evaluate',{returnByValue:true,expression:`(() => {
        const root=document.querySelector('main')||document.body;
        const text=root?.innerText||'';
        const errors=[...(root?.querySelectorAll('[role="alert"]') || [])].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.innerText);
        if(/加载失败|请求失败|页面不存在|找不到页面|当前筛选的数据尚未发布|404 Not Found|Something went wrong/i.test(text))errors.push('error text');
        return {url:location.href,text,errors,core_selector_present:Boolean(root?.querySelector(${JSON.stringify(spec.selector||'main')})),error_skeleton:Boolean(root?.querySelector('[data-state="error"],.error-skeleton'))};
      })()`})
      dom=state.result.value || {url:"about:blank",text:"",errors:[],error_skeleton:false};ready=coreReady(spec,dom,requests)
      if(ready.ready||ready.failure)break
      await sleep(Math.min(50,Math.max(1,deadline-Date.now())))
    } while(Date.now()<deadline)
    sample.core_ready=ready;sample.core_ready_ms=Date.now()-navigationStart
    if(ready.ready) {
      while(Date.now()<deadline && !apiTerminalState(requests).complete) {
        if(apiTerminalState(requests).failed.length)break
        await sleep(Math.min(50,Math.max(1,deadline-Date.now())))
      }
    }
    sample.api_terminal=apiTerminalState(requests)
    const result=await client.send('Runtime.evaluate',{expression:METRICS_EXPRESSION,returnByValue:true})
    Object.assign(sample,roundMetrics(result.result.value))
    const resources=await client.send('Runtime.evaluate',{returnByValue:true,expression:`performance.getEntriesByType('resource').map(r=>({url:r.name,start:r.startTime,end:r.responseEnd,raw_bytes:r.decodedBodySize,compressed_bytes:r.encodedBodySize,transfer_bytes:r.transferSize}))`})
    for(const r of requests) {
      const size=resources.result.value.find(x=>x.url===r.url)
      if(size)Object.assign(r,{compressed_bytes:r.compressed_bytes??(size.compressed_bytes||null),resource_raw_bytes:size.raw_bytes,size_evidence:'ResourceTiming; zero may indicate cache or unavailable cross-origin timing'})
    }
    sample.success=Boolean(ready.ready) && sample.api_terminal.success && !requests.some(r=>r.error_type || (r.status != null && r.status>=400))
    sample.http.error_type=sample.success?null:ready.failure||(!sample.api_terminal.complete?'IncompleteAPIRequests':sample.api_terminal.failed.length?'APIError':'CoreReadyTimeout')
    sample.timing.phases_ms={core_ready:sample.core_ready_ms}
    const nav=await client.send('Runtime.evaluate',{returnByValue:true,expression:"(()=>{const n=performance.getEntriesByType('navigation')[0];return n?{raw:n.decodedBodySize,encoded:n.encodedBodySize}:null})()"})
    if(nav.result.value){sample.http.raw_bytes=nav.result.value.raw;sample.http.compressed_bytes=nav.result.value.encoded}
    sample.pending_requests=requests.filter(r=>!r.finished).map(r=>r.request_id)
  } catch(error) {sample.http.error_type=error.name+': '+error.message}
  finally {
    sample.ended_at=Date.now()/1000;sample.timing.total_ms=Date.now()-started
    sample.waterfall=requests
    if(client)client.close()
    if(target)await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`).catch(()=>{})
  }
  return sample
}

function roundMetrics(result) {
  const numeric = [
    'lcp',
    'cls',
    'tbtApprox',
    'fcp',
    'domContentLoaded',
    'load',
    'responseEnd',
  ]
  for (const key of numeric) {
    if (typeof result[key] === 'number') {
      const scale=key==='cls'?10000:10
      result[key] = Math.round(result[key] * scale) / scale
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
    '| Route | Viewport | LCP | CLS | INP (not measured) | TBT approx | FCP | DCL | Load | Resources | Encoded resources | Scroll width |',
    '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  ]

  for (const row of results) {
    const fid = row.inp == null ? 'n/a' : `${row.inp}ms`
    const scrollWidth = `${row.documentScrollWidth ?? 'n/a'} / ${row.viewportWidth ?? 'n/a'}`
    lines.push(
      `| \`${row.route}\` | ${row.presentation ?? row.viewport} | ${formatMs(row.lcp)} | ${row.cls} | ${fid} | ${formatMs(row.tbtApprox)} | ${formatMs(row.fcp)} | ${formatMs(row.domContentLoaded)} | ${formatMs(row.load)} | ${row.resourceCount} | ${row.encodedResourceKB}KB | ${scrollWidth} |`,
    )
  }

  lines.push('')
  lines.push('Notes:')
  lines.push('- LCP/CLS are collected with PerformanceObserver in headless Chrome.')
  lines.push('- INP is not measured; no random clicks or FID substitution.')
  lines.push('- TBT approx sums long tasks over 50ms from FCP through the API terminal-state observation or the original deadline; core-ready time is reported separately.')
  lines.push('- Route/viewport samples that exceed a configured budget are retried once; every attempt is retained and a later success does not erase an earlier failure.')
  return lines.join('\n')
}

function evaluateBudgets(results, budgets) {
  const failures = []

  for (const row of results) {
    for (const check of BUDGET_CHECKS) {
      const budget = budgets[check.budgetKey]
      if (budget == null) continue

      const value = row[check.key]
      const context = `${row.route} (${row.viewport})`
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        failures.push(`${context} ${check.label}=n/a is missing budget ${formatBudget(budget, check.unit)}`)
      } else if (value > budget) {
        failures.push(`${context} ${check.label}=${formatBudget(value, check.unit)} exceeds budget ${formatBudget(budget, check.unit)}`)
      }
    }
  }

  return failures
}

function formatBudget(value, unit) {
  return unit ? `${value}${unit}` : String(value)
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
  const context = args.contextFile ? JSON.parse(await readFile(args.contextFile,'utf8')) : JSON.parse(execFileSync(
    process.env.PERFORMANCE_PYTHON || fileURLToPath(new URL('../.venv/bin/python',import.meta.url)),
    [fileURLToPath(new URL('./performance_contract.py',import.meta.url)), '--dataset',args.dataset,...(args.dbPath?['--db-path',args.dbPath]:[])],{encoding:'utf8'}))
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

  if(args.browserPidFile)await writeFile(args.browserPidFile,String(chrome.pid))
  const cleanup = async () => {
    chrome.kill('SIGTERM')
    if(chrome.exitCode==null && chrome.signalCode==null)await new Promise(resolve=>chrome.once('exit',resolve))
    await rm(profileDir, { recursive: true, force: true }).catch(() => {})
    if(args.browserPidFile)await rm(args.browserPidFile,{force:true}).catch(()=>{})
  }

  const onSignal=()=>{void cleanup().finally(()=>process.exit(130))}
  process.once('SIGINT',onSignal);process.once('SIGTERM',onSignal)
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`)

    const results = []
    for (const route of args.routes) {
      for (const viewport of args.viewports) {
        process.stderr.write(`Measuring ${route} (${viewport}) ... `)
        for (let attempt=1;attempt<=BUDGET_RETRY_LIMIT+1;attempt++) {
          const result=await measureRoute({port,baseUrl:args.baseUrl,apiBaseUrl:args.apiBaseUrl,route,viewportName:viewport,waitMs:args.waitMs,context,surface:args.surface,attempt})
          result.browser_instance={pid:chrome.pid,profile:'temporary',target:'fresh target per attempt',cache_policy:'normal shared browser cache; backend state unobserved'}
          result.budget_failures=evaluateBudgets([result],args)
          if(result.budget_failures.length)result.success=false
          results.push(result)
          if(result.success)break
          process.stderr.write(`attempt ${attempt} failed: ${result.http.error_type || result.budget_failures.join('; ')}; retained. `)
        }

      }
    }

    const markdown = renderMarkdown(results)
    console.log(markdown)

    if (args.output) {
      await writeFile(args.output, `${JSON.stringify({ schema_version:SCHEMA_VERSION,tool:'frontend_web_vitals',context,generatedAt:new Date().toISOString(),results,samples:results,statistics:args.routes.flatMap(route=>args.viewports.map(viewport=>({route,viewport,...summarizeAttempts(results.filter(r=>r.route===route && r.viewportName===viewport))}))) }, null, 2)}\n`)
      console.error(`JSON written to ${args.output}`)
    }

    const budgetFailures = evaluateBudgets(results, args)
    if (budgetFailures.length > 0 || results.some(r=>!r.success)) {
      console.error('Web Vitals budget failures:')
      for (const failure of budgetFailures) {
        console.error(`- ${failure}`)
      }
      process.exitCode = 1
    }
  } finally {
    process.removeListener('SIGINT',onSignal);process.removeListener('SIGTERM',onSignal)
    await cleanup()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
