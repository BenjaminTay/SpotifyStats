from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_interaction_smoke_script_exposes_reusable_cli():
    script = ROOT / "scripts" / "frontend_interaction_smoke.mjs"

    result = subprocess.run(
        ["node", str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "frontend_interaction_smoke.mjs" in result.stdout
    assert "--base-url" in result.stdout
    assert "--api-base-url" in result.stdout
    assert "--scenario" in result.stdout
    assert "--output" in result.stdout


def test_frontend_interaction_smoke_script_covers_core_non_destructive_flows():
    source = (ROOT / "scripts" / "frontend_interaction_smoke.mjs").read_text(encoding="utf-8")

    assert "const DEFAULT_WAIT_MS = 5000" in source
    assert "const MOBILE_DATA_WAIT_MS = 30000" in source
    assert "async function waitForText" in source
    assert "async function waitForAnyText" in source
    assert "async function waitForPath" in source
    assert "analysis-tabs" in source
    assert "billboard-routing" in source
    assert "ai-insights-tabs" in source
    assert "settings-controls" in source
    assert "settings-data-import" in source
    assert "expandSectionForText" in source
    assert "theme-toggle" in source
    assert "assertClickableTextCount" in source
    assert "fetchLlmAvailability" in source
    assert "llm_enabled" in source
    assert "has_llm_key" in source
    assert "AI 功能尚未配置" in source
    assert "数据与显示" in source
    assert "数据导入" in source
    assert "选择 Spotify Extended Streaming History JSON" in source
    assert "榜单参数" in source
    assert "归并与版本" in source
    assert "DATA & DISPLAY" not in source
    assert "DATA IMPORT" not in source
    assert "BILLBOARD PARAMETERS" not in source
    assert "VERSION MERGE" not in source
    assert "assertSwitchAvailable" in source
    assert "clickSwitchByLabel" not in source
    assert "过滤参数已更新" not in source
    assert "现有数据库" in source
    assert "账号资料包" in source
    assert "运行历史" in source
    assert "艺人语言数据" in source
    assert "Top 未知艺人" in source
    assert "暂无高播放量未知艺人。" in source
    assert "开始审核" in source
    assert "assertArtistLanguageHealthControls" in source
    assert "openExistingArtistLanguageReview" in source
    assert "clickText(client, '开始审核'" not in source
    assert "chineseStyle" in source
    assert "Runtime.consoleAPICalled" in source
    assert "Math.max(waitMs, MOBILE_DATA_WAIT_MS)" in source


def test_frontend_interaction_smoke_script_can_rewrite_preview_api_requests():
    source = (ROOT / "scripts" / "frontend_interaction_smoke.mjs").read_text(encoding="utf-8")

    assert "apiBaseUrl" in source
    assert "setupApiRequestRewrite" in source
    assert "Fetch.requestPaused" in source
    assert "Fetch.continueRequest" in source
    assert "'/api'" in source
    assert "'/covers'" in source


def test_only_proven_analysis_network_unavailable_is_classified():
    script = r"""
import assert from 'node:assert/strict';
import { classifyAnalysisConsole, isAnalysisUnavailable } from './scripts/frontend_interaction_smoke.mjs';
const url = 'http://127.0.0.1:5173/api/analysis/stats?period=last_4_weeks';
const response = {requestId:'r1',url,status:503,complete:true,detail:{error:'snapshot_unavailable',status:'unavailable',family:'analysis_stats',message:'unpublished'}};
const state = {url:'http://127.0.0.1:5173/analysis/stats?period=last_4_weeks',alerts:['播放统计暂不可用 unpublished'],skeletonCount:0,statsKpiCount:0};
const entry = {networkRequestId:'r1',url,source:'network',level:'error',text:'Failed to load resource: the server responded with a status of 503 (Service Unavailable)'};
const classify = (e=entry,r=response,s=state,scenario='mobile-time-filter') => classifyAnalysisConsole(scenario,[e],[r],s);
assert.equal(classify().expectedUnavailable.length,1);
assert.equal(classify().consoleErrors.length,0);
for (const invalid of [
 {...response,status:500}, {...response,complete:false}, {...response,detail:{error:'ordinary_503'}},
 {...response,detail:{...response.detail,family:'analysis_records'}},
 {...response,url:url.replace('/analysis/stats','/other')},
 {...response,url:url.replace('last_4_weeks','custom')},
 {...response,requestId:'r2'},
]) assert.equal(classify(entry,invalid).consoleErrors.length,1);
for (const invalid of [
 {...state,skeletonCount:1}, {...state,statsKpiCount:1}, {...state,alerts:[]},
 {...state,alerts:['播放统计暂不可用 other message']},
 {...state,url:state.url.replace('last_4_weeks','lifetime')},
]) assert.equal(isAnalysisUnavailable(response,invalid),false);
for (const invalid of [
 {...entry,source:'console-api'}, {...entry,source:'javascript'}, {...entry,networkRequestId:undefined},
 {...entry,url:url+'/other'}, {...entry,text:'JS exception'}, {...entry,level:'assert'},
]) assert.equal(classify(invalid).consoleErrors.length,1);
assert.equal(classify(entry,response,state,'mobile-section-sheet').consoleErrors.length,1);
const extra = {...entry,networkRequestId:'other',url:url+'/other'};
assert.equal(classifyAnalysisConsole('mobile-time-filter',[entry,extra],[response],state).consoleErrors.length,1);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_mobile_analysis_filter_accepts_only_completed_ready_payload_with_visible_kpis():
    script = r"""
import assert from 'node:assert/strict';
import { isAnalysisReady } from './scripts/frontend_interaction_smoke.mjs';
const url = 'http://127.0.0.1:5173/api/analysis/stats?period=last_4_weeks';
const response = {requestId:'r1',url,status:200,complete:true};
const state = {url:'http://127.0.0.1:5173/analysis/stats?period=last_4_weeks',skeletonCount:0,statsKpiCount:1};
assert.equal(isAnalysisReady(response,state),true);
for (const invalid of [
 {...response,status:503}, {...response,complete:false},
 {...response,url:url.replace('/analysis/stats','/other')},
 {...response,url:url.replace('last_4_weeks','custom')},
]) assert.equal(isAnalysisReady(invalid,state),false);
for (const invalid of [
 {...state,statsKpiCount:0},
 {...state,url:state.url.replace('last_4_weeks','lifetime')},
]) assert.equal(isAnalysisReady(response,invalid),false);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
