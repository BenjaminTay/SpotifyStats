import test from 'node:test'
import assert from 'node:assert/strict'
import { coreReady, routeContract, summarizeAttempts, apiTerminalState } from '../lib/performance_browser_contract.mjs'

test('core-ready requires route + fact + completed successful JSON API, never error skeleton',()=>{
  const spec=routeContract('/analysis/stats')
  const dom={url:'http://localhost/analysis/stats',text:'独特歌曲 123 次',errors:[],error_skeleton:false}
  const api={url:'http://localhost/api/analysis/stats',status:200,valid_json:true,finished:true}
  assert.equal(coreReady(spec,dom,[api]).ready,true)
  assert.equal(coreReady(spec,{...dom,url:'http://localhost/404'},[api]).ready,false)
  assert.equal(coreReady(spec,{...dom,text:'加载中'},[api]).ready,false)
  assert.equal(coreReady(spec,dom,[{...api,status:404}]).ready,false)
  assert.equal(coreReady(spec,dom,[{...api,valid_json:false}]).ready,false)
  assert.equal(coreReady(spec,dom,[{...api,finished:false}]).ready,false)
  assert.equal(coreReady(spec,{...dom,error_skeleton:true},[api]).ready,false)
  assert.equal(coreReady(spec,{...dom,errors:['请求失败']},[api]).ready,false)
  assert.equal(coreReady(spec,dom,[{...api,error_type:'Cancelled'}]).ready,false)
})
test('success retry cannot erase first failed attempt and insufficient samples cannot yield P95',()=>{
  const samples=[{success:false,timing:{total_ms:5000},process:{state:'unknown'}},{success:true,timing:{total_ms:20},process:{state:'warm'}}]
  const summary=summarizeAttempts(samples)
  assert.equal(summary.failure_count,1);assert.equal(summary.success_count,1);assert.equal(summary.p95_ms,null)
})
test('all supported primary pages have distinct readiness contracts',()=>{
  for(const route of ['/','/analysis/stats','/analysis/charts','/analysis/records','/billboard','/billboard/all-time','/billboard/year-end','/billboard/records','/music/search?q=love','/music/tracks/1','/music/album-projects/2','/music/artists/Test','/yearly-review','/account','/community','/settings'])assert.ok(routeContract(route).apis.length)
})

test('pending or cancelled APIs cannot pass after core-ready',()=>{
  const request={request_id:'r1',url:'http://localhost/api/music/album-projects/1/plays',status:200,finished:false}
  assert.equal(apiTerminalState([request]).success,false)
  assert.equal(apiTerminalState([{...request,finished:true,error_type:'Cancelled'}]).success,false)
  assert.equal(apiTerminalState([{...request,finished:true,valid_json:true}]).success,true)
})
