import { createHash } from 'node:crypto'

export const SCHEMA_VERSION = 'spotify-performance/1'
export const DEFAULT_ROUTES = ['/', '/analysis/stats', '/analysis/charts', '/analysis/records', '/billboard', '/billboard/all-time', '/billboard/year-end', '/billboard/records', '/music/search?q=love', '/music/tracks/{track_id}', '/music/album-projects/{project_id}', '/music/artists/{artist}', '/yearly-review', '/account', '/community', '/settings']
export function fingerprint(value) {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}
export function routeContract(route) {
  const path = new URL(route, 'http://localhost').pathname
  const routes = {
    '/': { markers: ['最近'], apis: ['/api/home/overview'], fact: '[0-9][0-9,.]*' },
    '/analysis/stats': { markers: ['独特歌曲'], apis: ['/api/analysis/stats'], fact: '[0-9][0-9,.]*' },
    '/analysis/charts': { markers: ['播放排行'], apis: ['/api/analysis/charts'], fact: '[0-9][0-9,.]*' },
    '/analysis/records': { markers: ['高光时刻'], apis: ['/api/analysis/records'], fact: '[0-9][0-9,.]*' },
    '/billboard': { markers: ['新入榜'], apis: ['/api/billboard/weekly'], fact: '[0-9][0-9,.]*' },
    '/billboard/number-ones': { markers: ['每周榜首'], apis: ['/api/billboard/all-time'], fact: '[0-9][0-9,.]*' },
    '/billboard/all-time': { markers: ['总榜'], apis: ['/api/billboard/all-time'], fact: '[0-9][0-9,.]*' },
    '/billboard/year-end': { markers: ['阶段领先'], apis: ['/api/billboard/year-end'], fact: '[0-9][0-9,.]*' },
    '/billboard/records': { markers: ['冠军圣殿'], apis: ['/api/billboard/records'], fact: '[0-9][0-9,.]*' },
    '/music/search': { markers: ['音乐查找'], apis: ['/api/music/search'], fact: '[0-9][0-9,.]*' },
    '/yearly-review': { markers: ['年度总结'], apis: ['/api/yearly-review/[0-9]+$'], fact: '[0-9][0-9,.]*' },
    '/account': { markers: ['音乐档案', '收藏'], apis: ['/api/account/archive-overview'], fact: '[0-9][0-9,.]*' },
    '/community': { markers: ['精选'], apis: ['/api/community/feed'], fact: '[0-9][0-9,.]*' },
    '/settings': { markers: ['设置'], apis: ['/api/settings'], fact: '[0-9][0-9,.]*' },
  }
  if (routes[path]) return { path, query:[...new URL(route,'http://localhost').searchParams], ...routes[path] }
  const kinds = [
    [/^\/music\/tracks\/([^/]+)$/, 'track/canonical', 'tracks/l1'],
    [/^\/music\/album-projects\/([^/]+)$/, 'album-project', 'album-projects'],
    [/^\/music\/artists\/([^/]+)$/, 'artist', 'artists'],
  ]
  for (const [pattern, billboard, music] of kinds) {
    const match = path.match(pattern)
    if (match) return { path, query:[...new URL(route,'http://localhost').searchParams], selector:'.entity-stats-kpi-grid', markers: ['总播放次数'], fact: '[0-9][0-9,.]*',
      apis: [`/api/billboard/${billboard}/${match[1]}$`, `/api/music/${music}/${match[1]}/stats$`] }
  }
  throw new Error(`No core-ready contract for route: ${route}`)
}

export function coreReady(spec, dom, requests) {
  const relevant = requests.filter(r => r.url && new URL(r.url).pathname.startsWith('/api/'))
  const failure = relevant.find(r => r.error_type || r.application_error || (r.status != null && (r.status < 200 || r.status >= 300)))
  const errors = dom.errors || []
  const apiReady = spec.apis.every(pattern => relevant.some(r =>
    new RegExp(pattern).test(new URL(r.url).pathname) && r.finished && r.status >= 200 && r.status < 300 && r.valid_json && !r.application_error))
  const actualUrl=new URL(dom.url,'http://localhost')
  const routeReady = actualUrl.pathname === spec.path && (spec.query||[]).every(([k,v])=>actualUrl.searchParams.get(k)===v)
  const domReady = (!spec.selector || dom.core_selector_present) && spec.markers.every(marker => dom.text.includes(marker)) && new RegExp(spec.fact).test(dom.text)
  return { ready: routeReady && domReady && apiReady && !failure && !errors.length && !dom.error_skeleton,
    route_ready: routeReady, dom_ready: domReady, api_ready: apiReady,
    failure: failure ? failure.error_type || (failure.application_error?'ApplicationError':`HTTP${failure.status}`) : errors.length ? 'ErrorDOM' : dom.error_skeleton ? 'ErrorSkeleton' : null }
}

export function summarizeAttempts(samples) {
  const values = samples.filter(s => s.success).map(s => s.timing.total_ms).sort((a,b)=>a-b)
  const warm = samples.filter(s=>s.success).every(s=>s.process.state==='warm')
  return { sample_count:samples.length, success_count:values.length, failure_count:samples.length-values.length,
    min_ms:values[0]??null, median_ms:values.length ? (values[Math.floor((values.length-1)/2)]+values[Math.floor(values.length/2)])/2 : null,
    p95_ms:warm && values.length>=20 ? values[Math.ceil(.95*values.length)-1] : null, max_ms:values.at(-1)??null,
    observed_values_ms:values, statistics_scope:warm && values.length>=20 ? 'warm_p95':'observed_values_only' }
}

export function snapshotState(payload, headers={}) {
  const source=payload?.snapshot||{}
  const lower=Object.fromEntries(Object.entries(headers).map(([k,v])=>[k.toLowerCase(),v]))
  const freshness=source.freshness||lower['x-snapshot-freshness']
  return {state:freshness==='current'?'exact':freshness==='last_known_good'?'LKG':payload?.detail?.error==='snapshot_unavailable'?'missing':'unknown',
    source_revision:source.source_revision??null,target_revision:source.target_revision??lower['x-snapshot-target-revision']??null,
    builder_version:source.builder_version??null,request_key:source.request_key??null,cache_key:source.cache_key??null,
    evidence:freshness?'response_metadata':'not_exposed'}
}

export function apiTerminalState(requests) {
  const api=requests.filter(r=>r.url && new URL(r.url).pathname.startsWith('/api/'))
  const pending=api.filter(r=>!r.finished || (r.status>=200 && r.status<300 && r.valid_json==null))
  const failed=api.filter(r=>r.error_type || r.application_error || (r.status!=null && (r.status<200 || r.status>=300)))
  return {complete:pending.length===0,success:pending.length===0 && failed.length===0,pending:pending.map(r=>r.request_id),failed:failed.map(r=>r.request_id)}
}
