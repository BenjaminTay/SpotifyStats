#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const DEFAULT_BASE_URL = 'http://localhost:5173'
const DEFAULT_PYTHON = process.env.PYTHON_PLAYWRIGHT || 'python'
const DEFAULT_BROWSERS = ['chromium', 'firefox', 'webkit']
const DEFAULT_SCENARIOS = ['route-markers', 'core-interactions']
const DEFAULT_WAIT_MS = 12000
const DYNAMIC_ROUTE_WAIT_MS = 20000
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
  { path: '/', markers: ['播放次数'] },
  { path: '/analysis/stats', markers: ['播放统计'] },
  { path: '/analysis/charts', markers: ['播放排行'] },
  { path: '/billboard/records', markers: ['冠军圣殿'] },
  { path: '/ai-insights', markers: ['AI 洞察'] },
  { path: '/settings', markers: ['Spotify 连接'] },
]

const VIEWPORTS = {
  desktop: { width: 1280, height: 900 },
  mobile: { width: 390, height: 844 },
}

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBaseUrl: null,
    browsers: DEFAULT_BROWSERS,
    scenarios: DEFAULT_SCENARIOS,
    viewports: ['desktop', 'mobile'],
    waitMs: DEFAULT_WAIT_MS,
    maxScrollOverflow: DEFAULT_MAX_SCROLL_OVERFLOW,
    output: null,
    python: DEFAULT_PYTHON,
    headed: false,
    includeDetailRoutes: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
    else if (arg === '--api-base-url') args.apiBaseUrl = argv[++i]
    else if (arg === '--browser' || arg === '--browsers') {
      args.browsers = argv[++i].split(',').map((browser) => browser.trim()).filter(Boolean)
    } else if (arg === '--scenario' || arg === '--scenarios') {
      args.scenarios = argv[++i].split(',').map((scenario) => scenario.trim()).filter(Boolean)
    } else if (arg === '--viewport') {
      const value = argv[++i]
      args.viewports = value === 'both' ? ['desktop', 'mobile'] : [value]
    } else if (arg === '--wait-ms') args.waitMs = Number(argv[++i])
    else if (arg === '--max-scroll-overflow') args.maxScrollOverflow = Number(argv[++i])
    else if (arg === '--output') args.output = argv[++i]
    else if (arg === '--python') args.python = argv[++i]
    else if (arg === '--headed') args.headed = true
    else if (arg === '--include-detail-routes') args.includeDetailRoutes = true
    else if (arg === '--help' || arg === '-h') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (args.browsers.length === 0) throw new Error('--browser must include at least one browser')
  if (args.scenarios.length === 0) throw new Error('--scenario must include at least one scenario')
  if (!Number.isFinite(args.waitMs) || args.waitMs < 500) throw new Error('--wait-ms must be at least 500')
  if (!Number.isFinite(args.maxScrollOverflow) || args.maxScrollOverflow < 0) {
    throw new Error('--max-scroll-overflow must be a non-negative number')
  }
  for (const browser of args.browsers) {
    if (!DEFAULT_BROWSERS.includes(browser)) {
      throw new Error(`Unsupported browser: ${browser}. Use chromium, firefox, or webkit.`)
    }
  }
  for (const scenario of args.scenarios) {
    if (!DEFAULT_SCENARIOS.includes(scenario)) {
      throw new Error(`Unsupported scenario: ${scenario}. Use route-markers or core-interactions.`)
    }
  }
  for (const viewport of args.viewports) {
    if (!VIEWPORTS[viewport]) throw new Error(`Unsupported viewport: ${viewport}`)
  }

  return args
}

function printHelp() {
  console.log(`Usage:
  node scripts/frontend_cross_browser_smoke.mjs [options]

Options:
  --base-url <url>              Frontend URL, default ${DEFAULT_BASE_URL}
  --api-base-url <url>          Rewrite same-origin /api and /covers requests to this API URL
  --browser <a,b,c>             Browser engines: chromium,firefox,webkit; default ${DEFAULT_BROWSERS.join(',')}
  --scenario <a,b>              Scenarios: route-markers,core-interactions; default ${DEFAULT_SCENARIOS.join(',')}
  --viewport <mode>             desktop, mobile, or both, default both
  --wait-ms <ms>                Max wait for route/text assertions, default ${DEFAULT_WAIT_MS}; dynamic detail routes use at least ${DYNAMIC_ROUTE_WAIT_MS}
  --max-scroll-overflow <px>    Allowed horizontal overflow over viewport width, default ${DEFAULT_MAX_SCROLL_OVERFLOW}
  --include-detail-routes       Resolve and append music/community detail routes from local API data
  --output <path>               Write JSON results to a file
  --python <path>               Python executable with playwright.sync_api, default ${DEFAULT_PYTHON}
  --headed                      Run headed browsers

Notes:
  Set PYTHON_PLAYWRIGHT=/path/to/python when the default python cannot import playwright.sync_api.
  webkit is Playwright WebKit, a Safari-family engine smoke test, not the user's Safari.app session.
`)
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
  if (track) {
    routes.push({
      path: `/music/tracks/${encodeURIComponent(String(track.track_id))}`,
      markers: ['单曲详情'],
      dynamic: true,
    })
  }
  if (album) {
    routes.push({
      path: `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
      markers: ['专辑详情'],
      dynamic: true,
    })
  }
  if (artist) {
    routes.push({
      path: `/music/artists/${encodeURIComponent(artist.artist_name)}`,
      markers: ['艺人详情'],
      dynamic: true,
    })
  }
  if (post) {
    routes.push({
      path: `/community/post/${encodeURIComponent(post.id)}`,
      markers: ['回复'],
      dynamic: true,
    })
    if (post.account_handle) {
      routes.push({
        path: `/community/account/${encodeURIComponent(post.account_handle)}`,
        markers: ['Posts'],
        dynamic: true,
      })
    }
  }

  if (routes.length < 5) {
    throw new Error(
      `Could not resolve all detail routes from /api/billboard/entity-lists and /api/community/feed; got ${routes.length}`,
    )
  }
  return routes
}

function createPythonSource() {
  return `#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("FRONTEND_BASE_URL", ${JSON.stringify(DEFAULT_BASE_URL)})
API_BASE_URL = os.environ.get("FRONTEND_API_BASE_URL", "")
ROUTES = json.loads(os.environ["FRONTEND_ROUTES_JSON"])
SCENARIOS = set(json.loads(os.environ["FRONTEND_SCENARIOS_JSON"]))
VIEWPORTS = json.loads(os.environ["FRONTEND_VIEWPORTS_JSON"])
WAIT_MS = int(os.environ["FRONTEND_WAIT_MS"])
DYNAMIC_ROUTE_WAIT_MS = int(os.environ["FRONTEND_DYNAMIC_ROUTE_WAIT_MS"])
SLOW_PAGE_WAIT_MS = max(WAIT_MS, 20000)
MAX_SCROLL_OVERFLOW = int(os.environ["FRONTEND_MAX_SCROLL_OVERFLOW"])
HEADED = os.environ.get("FRONTEND_HEADED") == "1"
BROWSER_NAME = sys.argv[1]
REWRITE_PATH_PREFIXES = ${JSON.stringify(REWRITE_PATH_PREFIXES)}
IGNORED_CONSOLE_PATTERNS = [
    "preloaded using link preload but not used within a few seconds",
]


class SmokeFailure(AssertionError):
    pass


def absolute_url(path: str) -> str:
    return urljoin(BASE_URL.rstrip("/") + "/", path.lstrip("/"))


def wait_ms_for_route(route) -> int:
    return max(WAIT_MS, DYNAMIC_ROUTE_WAIT_MS) if route.get("dynamic") else WAIT_MS


def rewrite_request_url(request_url):
    if not API_BASE_URL:
        return None

    frontend = urlparse(BASE_URL)
    api = urlparse(API_BASE_URL)
    request = urlparse(request_url)
    if (frontend.scheme, frontend.netloc) == (api.scheme, api.netloc):
        return None
    if (request.scheme, request.netloc) != (frontend.scheme, frontend.netloc):
        return None
    if not any(request.path == prefix or request.path.startswith(prefix + "/") for prefix in REWRITE_PATH_PREFIXES):
        return None

    return urlunparse((api.scheme, api.netloc, request.path, "", request.query, request.fragment))


def install_request_rewrite(page):
    if not API_BASE_URL:
        return

    def route_request(route):
        rewritten = rewrite_request_url(route.request.url)
        try:
            if rewritten:
                response = route.fetch(url=rewritten)
                route.fulfill(response=response)
            else:
                route.continue_()
        except Exception:
            try:
                route.abort()
            except Exception:
                pass

    page.route("**/*", route_request)


def install_guards(page):
    console_messages = []
    page_errors = []

    def is_ignored_console_message(text: str) -> bool:
        return any(pattern in text for pattern in IGNORED_CONSOLE_PATTERNS)

    def on_console(message):
        if message.type in ("error", "warning") and not is_ignored_console_message(message.text):
            console_messages.append(f"{message.type}: {message.text}")

    def on_page_error(error):
        page_errors.append(str(error))

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    return console_messages, page_errors


def body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=1000)
    except Exception:
        return ""


def wait_for_text(page, text: str, timeout_ms: int | None = None) -> str:
    wait_ms = WAIT_MS if timeout_ms is None else timeout_ms
    deadline = time.monotonic() + wait_ms / 1000
    last = ""
    while time.monotonic() < deadline:
        last = body_text(page)
        if text in last:
            return last
        time.sleep(0.15)
    raise SmokeFailure(f"Expected page text not found: {text}; sample={last[:240]!r}")


def has_text(page, text: str) -> bool:
    return text in body_text(page)


def expand_section_for_text(page, section_title: str, target_text: str) -> None:
    wait_for_text(page, section_title)
    if not has_text(page, target_text):
        try:
            button = page.get_by_role("button", name=re.compile(re.escape(section_title))).first
            button.scroll_into_view_if_needed(timeout=WAIT_MS)
            button.click(timeout=WAIT_MS)
        except Exception:
            click_text(page, section_title)
    wait_for_text(page, target_text)


def wait_for_any_text(page, texts) -> str:
    deadline = time.monotonic() + WAIT_MS / 1000
    last = ""
    while time.monotonic() < deadline:
        last = body_text(page)
        if any(text in last for text in texts):
            return last
        time.sleep(0.15)
    raise SmokeFailure(f"Expected one of page texts not found: {texts}; sample={last[:240]!r}")


def click_text(page, text: str) -> None:
    target = page.get_by_text(text, exact=False).first
    try:
        target.scroll_into_view_if_needed(timeout=WAIT_MS)
    except Exception:
        pass
    target.click(timeout=WAIT_MS)


def wait_for_condition(check, failure_message: str):
    deadline = time.monotonic() + WAIT_MS / 1000
    last = None
    while time.monotonic() < deadline:
        last = check()
        if last:
            return last
        time.sleep(0.15)
    raise SmokeFailure(f"{failure_message}; last={last!r}")


def click_switch_by_label(page, label: str):
    target = page.get_by_role("switch", name=re.compile(label)).first
    before = target.get_attribute("aria-checked", timeout=WAIT_MS)
    target.scroll_into_view_if_needed(timeout=WAIT_MS)
    target.click(timeout=WAIT_MS)

    def changed():
        after = target.get_attribute("aria-checked", timeout=1000)
        return {"before": before, "after": after} if after != before else None

    return wait_for_condition(changed, f"Switch did not toggle: {label}")


def assert_clickable_text_count(page, texts, minimum: int):
    def enough():
        return page.evaluate(
            """({ texts, minimum }) => {
                const isVisible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                };
                const count = Array.from(document.querySelectorAll('button, a, [role="button"], [role="tab"], [role="option"]'))
                    .filter((el) => isVisible(el))
                    .filter((el) => {
                        const text = (el.innerText || el.textContent || '').trim();
                        return texts.some((targetText) => text.includes(targetText));
                    }).length;
                return count >= minimum ? { count } : null;
            }""",
            {"texts": texts, "minimum": minimum},
        )

    return wait_for_condition(enough, f"Expected at least {minimum} clickable control(s): {texts}")


def fetch_llm_availability(page):
    return page.evaluate(
        """async () => {
            try {
                const response = await fetch('/api/settings', { headers: { Accept: 'application/json' } });
                if (!response.ok) return null;
                const settings = await response.json();
                return Boolean(settings.llm_enabled && settings.has_llm_key);
            } catch {
                return null;
            }
        }"""
    )


def page_state(page):
    return page.evaluate(
        """() => {
            const bodyText = document.body ? document.body.innerText : '';
            const root = document.querySelector('#root');
            const bodyScrollWidth = document.body ? document.body.scrollWidth : 0;
            const documentScrollWidth = document.documentElement ? document.documentElement.scrollWidth : 0;
            const viewportWidth = window.innerWidth;
            const elementLabel = (el) => {
                const tag = el.tagName ? el.tagName.toLowerCase() : 'node';
                const classes = typeof el.className === 'string'
                    ? el.className.trim().split(/\\\\s+/).slice(0, 4).join('.')
                    : '';
                const text = (el.innerText || el.textContent || '').trim().replace(/\\\\s+/g, ' ').slice(0, 80);
                return [tag, classes ? '.' + classes : '', text ? ' :: ' + text : ''].join('');
            };
            const overflowElements = Array.from(document.querySelectorAll('body *'))
                .map((el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const overflowRight = rect.right - viewportWidth;
                    const scrollOverflow = el.scrollWidth - el.clientWidth;
                    return {
                        label: elementLabel(el),
                        left: Math.round(rect.left),
                        right: Math.round(rect.right),
                        width: Math.round(rect.width),
                        overflowRight: Math.round(overflowRight),
                        scrollOverflow: Math.round(scrollOverflow),
                        display: style.display,
                    };
                })
                .filter((item) => item.width > 0 && (item.overflowRight > 1 || item.scrollOverflow > 1))
                .sort((a, b) => Math.max(b.overflowRight, b.scrollOverflow) - Math.max(a.overflowRight, a.scrollOverflow))
                .slice(0, 5);
            return {
                bodyText,
                rootTextLength: root ? (root.textContent || '').trim().length : 0,
                scrollOverflow: Math.max(bodyScrollWidth, documentScrollWidth) - viewportWidth,
                overflowElements,
                hasFatalText: /Internal Server Error|Failed to fetch dynamically imported module|ReferenceError|TypeError|Unhandled Runtime Error/.test(bodyText),
                theme: localStorage.getItem('theme'),
                chineseStyle: localStorage.getItem('chineseStyle'),
                isDark: document.documentElement.classList.contains('dark'),
                path: location.pathname,
                viewportMode: document.querySelector('main[data-viewport-mode]')?.getAttribute('data-viewport-mode') || null,
                hasMobileTopBar: Boolean(document.querySelector('[data-mobile-shell="top-bar"]')),
                hasMobileBottomNav: Boolean(document.querySelector('[data-mobile-shell="bottom-nav"]')),
                hasDesktopMasthead: Boolean(document.querySelector('nav[aria-label="主导航"]')),
            };
        }"""
    )


def route_should_have_mobile_bottom_nav(path: str) -> bool:
    normalized = urlparse(path).path.rstrip("/") or "/"
    if normalized in ("/", "/yearly-review", "/account", "/community", "/ai-insights"):
        return True
    return normalized.startswith("/analysis/") or normalized == "/analysis" or normalized.startswith("/billboard/") or normalized == "/billboard"


def assert_page_health(page, console_messages, page_errors, viewport_name=None, route_path=None):
    state = page_state(page)
    if state["rootTextLength"] <= 20:
        raise SmokeFailure(f"Root text too short: {state['rootTextLength']}")
    if state["hasFatalText"]:
        raise SmokeFailure("Fatal text found in page body")
    overflow = max(0, state["scrollOverflow"])
    if overflow > MAX_SCROLL_OVERFLOW:
        raise SmokeFailure(f"Horizontal overflow {overflow}px; offenders={state.get('overflowElements')}")
    if page_errors:
        raise SmokeFailure("Page errors: " + " | ".join(page_errors[:5]))
    if console_messages:
        raise SmokeFailure("Console errors/warnings: " + " | ".join(console_messages[:5]))
    if viewport_name == "mobile":
        if not state["hasMobileTopBar"]:
            raise SmokeFailure("Mobile top bar missing")
        if state["hasDesktopMasthead"]:
            raise SmokeFailure("Desktop masthead mounted in mobile viewport")
        if state["viewportMode"] != "phone":
            raise SmokeFailure(f"Viewport mode {state['viewportMode']!r} != 'phone'")
        expected_bottom_nav = route_should_have_mobile_bottom_nav(route_path or state["path"])
        if state["hasMobileBottomNav"] != expected_bottom_nav:
            raise SmokeFailure(f"Mobile bottom nav state {state['hasMobileBottomNav']} != expected {expected_bottom_nav}")
    elif viewport_name == "desktop":
        if not state["hasDesktopMasthead"]:
            raise SmokeFailure("Desktop masthead missing")
        if state["hasMobileTopBar"] or state["hasMobileBottomNav"]:
            raise SmokeFailure("Mobile shell mounted in desktop viewport")
        if state["viewportMode"] != "desktop":
            raise SmokeFailure(f"Viewport mode {state['viewportMode']!r} != 'desktop'")
    return state


def new_page(browser, viewport_name: str):
    page = browser.new_page(viewport=VIEWPORTS[viewport_name])
    install_request_rewrite(page)
    console_messages, page_errors = install_guards(page)
    return page, console_messages, page_errors


def close_page(page):
    try:
        page.wait_for_load_state("networkidle", timeout=min(WAIT_MS, 3000))
    except Exception:
        pass
    try:
        page.close()
    except Exception:
        pass


def run_route_markers(browser):
    for viewport_name in VIEWPORTS:
        for route in ROUTES:
            page, console_messages, page_errors = new_page(browser, viewport_name)
            try:
                route_wait_ms = wait_ms_for_route(route)
                last_error = None
                for attempt in range(2):
                    try:
                        page.goto(absolute_url(route["path"]), wait_until="domcontentloaded", timeout=route_wait_ms + 10000)
                        for marker in route["markers"]:
                            wait_for_text(page, marker, timeout_ms=route_wait_ms)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error
                        if attempt == 0:
                            page.wait_for_timeout(250)
                if last_error:
                    raise last_error
                wait_for_condition(
                    lambda: page_state(page) if page_state(page)["rootTextLength"] > 20 else None,
                    f"Route body did not become ready: {route['path']}",
                )
                assert_page_health(page, console_messages, page_errors, viewport_name, route["path"])
                print(f"PASS route-markers {viewport_name} {route['path']}")
            finally:
                close_page(page)


def expect_url(page, pattern: str):
    deadline = time.monotonic() + WAIT_MS / 1000
    while time.monotonic() < deadline:
        if re.search(pattern, page.url):
            return
        time.sleep(0.15)
    raise SmokeFailure(f"Expected URL pattern {pattern}, got {page.url}")


def run_analysis_tabs(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/analysis/stats"), wait_until="domcontentloaded", timeout=SLOW_PAGE_WAIT_MS + 10000)
        wait_for_text(page, "播放统计", timeout_ms=SLOW_PAGE_WAIT_MS)
        click_text(page, "播放排行")
        expect_url(page, r"/analysis/charts$")
        wait_for_text(page, "PLAYBACK RANKING", timeout_ms=SLOW_PAGE_WAIT_MS)
        click_text(page, "播放统计")
        expect_url(page, r"/analysis/stats$")
        wait_for_text(page, "播放统计", timeout_ms=SLOW_PAGE_WAIT_MS)
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions analysis-tabs")
    finally:
        close_page(page)


def run_billboard_routing(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/billboard"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "Billboard 周榜")
        click_text(page, "每周榜首")
        expect_url(page, r"/billboard/number-ones$")
        wait_for_text(page, "每周冠军歌曲")
        click_text(page, "总榜")
        expect_url(page, r"/billboard/all-time$")
        wait_for_text(page, "Billboard 总榜")
        click_text(page, "榜单记录")
        expect_url(page, r"/billboard/records$")
        wait_for_text(page, "冠军圣殿")
        page.go_back(wait_until="domcontentloaded")
        expect_url(page, r"/billboard/all-time$")
        page.go_forward(wait_until="domcontentloaded")
        expect_url(page, r"/billboard/records$")
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions billboard-routing")
    finally:
        close_page(page)


def run_ai_insights_tabs(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/ai-insights"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "AI 洞察")
        llm_available = fetch_llm_availability(page)
        if llm_available is False:
            wait_for_text(page, "AI 功能尚未配置")
            click_text(page, "问答")
            wait_for_text(page, "AI 功能尚未配置")
            click_text(page, "报告")
            wait_for_text(page, "AI 功能尚未配置")
        else:
            wait_for_text(page, "月报")
            click_text(page, "月报")
            wait_for_text(page, "月报")
            click_text(page, "年度叙事")
            wait_for_text(page, "年度叙事")
            click_text(page, "问答")
            wait_for_text(page, "对话历史")
            click_text(page, "报告")
            wait_for_text(page, "AI 洞察")
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions ai-insights-tabs")
    finally:
        close_page(page)


def run_settings_controls(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/settings"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "参数与配置")
        wait_for_text(page, "SPOTIFY 连接")
        wait_for_text(page, "数据与显示")
        wait_for_text(page, "榜单参数")
        wait_for_text(page, "归并与版本")
        wait_for_text(page, "数据导入")

        click_switch_by_label(page, "动态阈值")
        click_switch_by_label(page, "动态阈值")
        click_switch_by_label(page, "仅音乐")
        wait_for_text(page, "过滤参数已更新")
        click_switch_by_label(page, "仅音乐")
        wait_for_text(page, "过滤参数已更新")

        click_text(page, "原样显示")
        click_text(page, "简体中文")
        wait_for_condition(
            lambda: page_state(page) if page_state(page)["chineseStyle"] == "simplified" else None,
            "Chinese display preference did not update to simplified",
        )
        click_text(page, "简体中文")
        click_text(page, "原样显示")
        wait_for_condition(
            lambda: page_state(page) if page_state(page)["chineseStyle"] == "original" else None,
            "Chinese display preference did not reset to original",
        )

        wait_for_any_text(page, ["连接 Spotify", "同步收藏时间"])
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions settings-controls")
    finally:
        close_page(page)


def run_settings_data_import(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/settings"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "参数与配置")
        expand_section_for_text(page, "数据导入", "串流数据")
        wait_for_text(page, "账号数据")
        wait_for_text(page, "当前数据库记录数")
        wait_for_text(page, "导入 Spotify 账号数据包")
        wait_for_any_text(page, ["未导入", "已导入"])
        assert_clickable_text_count(page, ["开始导入", "重新导入", "导入中..."], 2)
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions settings-data-import")
    finally:
        close_page(page)


def run_theme_toggle(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        click_text(page, "夜晚")
        dark = page_state(page)
        if not dark["isDark"] or dark["theme"] != "dark":
            raise SmokeFailure("Dark theme did not activate")
        click_text(page, "白日")
        light = page_state(page)
        if light["isDark"] or light["theme"] != "light":
            raise SmokeFailure("Light theme did not activate")
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions theme-toggle")
    finally:
        close_page(page)


def run_core_interactions(browser):
    run_analysis_tabs(browser)
    run_billboard_routing(browser)
    run_ai_insights_tabs(browser)
    run_settings_controls(browser)
    run_settings_data_import(browser)
    run_theme_toggle(browser)


def main():
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, BROWSER_NAME)
        browser = browser_type.launch(headless=not HEADED)
        try:
            if "route-markers" in SCENARIOS:
                run_route_markers(browser)
            if "core-interactions" in SCENARIOS:
                run_core_interactions(browser)
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL {BROWSER_NAME}: {exc}", file=sys.stderr)
        raise
`
}

function runProcess(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { ...options, stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => {
      const text = chunk.toString()
      stdout += text
      process.stdout.write(text)
    })
    child.stderr.on('data', (chunk) => {
      const text = chunk.toString()
      stderr += text
      process.stderr.write(text)
    })
    child.on('error', (error) => {
      resolve({ code: 1, stdout, stderr: stderr + error.message })
    })
    child.on('close', (code) => {
      resolve({ code: code ?? 1, stdout, stderr })
    })
  })
}

function renderMarkdown(results) {
  const lines = [
    '# Frontend Cross-Browser Smoke',
    '',
    `> Generated: ${new Date().toISOString()}`,
    '',
    '| Browser | Engine Note | Status |',
    '| --- | --- | --- |',
  ]

  for (const result of results) {
    const note = result.browser === 'webkit' ? 'Playwright WebKit, Safari-family' : result.browser
    lines.push(`| ${result.browser} | ${note} | ${result.ok ? 'PASS' : 'FAIL'} |`)
  }

  const failed = results.filter((result) => !result.ok)
  if (failed.length > 0) {
    lines.push('')
    lines.push('## Failures')
    for (const result of failed) {
      lines.push('')
      lines.push(`- ${result.browser}: exit ${result.code}`)
      const tail = `${result.stderr || result.stdout}`.split('\n').slice(-20).join('\n').trim()
      if (tail) lines.push(`\n\`\`\`\n${tail}\n\`\`\``)
    }
  }

  return lines.join('\n')
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const tempDir = await mkdtemp(join(tmpdir(), 'spotify-stats-cross-browser-smoke-'))
  const scriptFileName = 'frontend-cross-browser-smoke.py'
  const scriptPath = join(tempDir, scriptFileName)
  await writeFile(scriptPath, createPythonSource())

  let routes = DEFAULT_ROUTES
  if (args.includeDetailRoutes) {
    const detailRoutes = await resolveDetailRoutes(args.baseUrl, args.apiBaseUrl)
    const seen = new Set()
    routes = [...DEFAULT_ROUTES, ...detailRoutes].filter((route) => {
      if (seen.has(route.path)) return false
      seen.add(route.path)
      return true
    })
    process.stderr.write(`Resolved cross-browser detail routes: ${detailRoutes.map((route) => route.path).join(', ')}\n`)
  }

  const routeConfig = JSON.stringify(routes)
  const viewportConfig = JSON.stringify(Object.fromEntries(args.viewports.map((name) => [name, VIEWPORTS[name]])))
  const results = []

  try {
    for (const browser of args.browsers) {
      process.stderr.write(`Running ${browser} cross-browser smoke ...\n`)
      const result = await runProcess(args.python, [scriptPath, browser], {
        cwd: process.cwd(),
        env: {
          ...process.env,
          FRONTEND_BASE_URL: args.baseUrl,
          FRONTEND_API_BASE_URL: args.apiBaseUrl || '',
          FRONTEND_ROUTES_JSON: routeConfig,
          FRONTEND_SCENARIOS_JSON: JSON.stringify(args.scenarios),
          FRONTEND_VIEWPORTS_JSON: viewportConfig,
          FRONTEND_WAIT_MS: String(args.waitMs),
          FRONTEND_DYNAMIC_ROUTE_WAIT_MS: String(Math.max(args.waitMs, DYNAMIC_ROUTE_WAIT_MS)),
          FRONTEND_MAX_SCROLL_OVERFLOW: String(args.maxScrollOverflow),
          FRONTEND_HEADED: args.headed ? '1' : '0',
        },
      })
      results.push({
        browser,
        ok: result.code === 0,
        code: result.code,
        stdout: result.stdout,
        stderr: result.stderr,
      })
    }

    const markdown = renderMarkdown(results)
    console.log(markdown)
    if (args.output) {
      await writeFile(args.output, `${JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2)}\n`)
      console.error(`JSON written to ${args.output}`)
    }
    if (results.some((result) => !result.ok)) process.exitCode = 1
  } finally {
    await rm(tempDir, { recursive: true, force: true }).catch(() => {})
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
