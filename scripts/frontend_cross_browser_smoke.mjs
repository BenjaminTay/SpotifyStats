#!/usr/bin/env node

import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const DEFAULT_BASE_URL = 'http://127.0.0.1:5173'
const DEFAULT_PYTHON = process.env.PYTHON_PLAYWRIGHT || 'python'
const DEFAULT_BROWSERS = ['chromium', 'firefox', 'webkit']
const DEFAULT_SCENARIOS = ['route-markers', 'core-interactions']
const DEFAULT_WAIT_MS = 5000
const DEFAULT_MAX_SCROLL_OVERFLOW = 0

const DEFAULT_ROUTES = [
  { path: '/', markers: ['DASHBOARD /', '总播放次数'] },
  { path: '/analysis/stats', markers: ['PLAYBACK / ANALYSIS', '总体播放统计'] },
  { path: '/analysis/charts', markers: ['PERSONAL CHARTS', '个人排行榜'] },
  { path: '/billboard/records', markers: ['CHART / HALL OF FAME', '冠军圣殿'] },
  { path: '/ai-insights', markers: ['AI / INSIGHTS', 'AI 洞察'] },
  { path: '/settings', markers: ['SETTINGS / CONFIGURATION', '00 · SPOTIFY 连接'] },
]

const VIEWPORTS = {
  desktop: { width: 1280, height: 900 },
  mobile: { width: 390, height: 844 },
}

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    browsers: DEFAULT_BROWSERS,
    scenarios: DEFAULT_SCENARIOS,
    viewports: ['desktop', 'mobile'],
    waitMs: DEFAULT_WAIT_MS,
    maxScrollOverflow: DEFAULT_MAX_SCROLL_OVERFLOW,
    output: null,
    python: DEFAULT_PYTHON,
    headed: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--base-url') args.baseUrl = argv[++i]
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
  --browser <a,b,c>             Browser engines: chromium,firefox,webkit; default ${DEFAULT_BROWSERS.join(',')}
  --scenario <a,b>              Scenarios: route-markers,core-interactions; default ${DEFAULT_SCENARIOS.join(',')}
  --viewport <mode>             desktop, mobile, or both, default both
  --wait-ms <ms>                Max wait for route/text assertions, default ${DEFAULT_WAIT_MS}
  --max-scroll-overflow <px>    Allowed horizontal overflow over viewport width, default ${DEFAULT_MAX_SCROLL_OVERFLOW}
  --output <path>               Write JSON results to a file
  --python <path>               Python executable with playwright.sync_api, default ${DEFAULT_PYTHON}
  --headed                      Run headed browsers

Notes:
  Set PYTHON_PLAYWRIGHT=/path/to/python when the default python cannot import playwright.sync_api.
  webkit is Playwright WebKit, a Safari-family engine smoke test, not the user's Safari.app session.
`)
}

function createPythonSource() {
  return `#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("FRONTEND_BASE_URL", ${JSON.stringify(DEFAULT_BASE_URL)})
ROUTES = json.loads(os.environ["FRONTEND_ROUTES_JSON"])
SCENARIOS = set(json.loads(os.environ["FRONTEND_SCENARIOS_JSON"]))
VIEWPORTS = json.loads(os.environ["FRONTEND_VIEWPORTS_JSON"])
WAIT_MS = int(os.environ["FRONTEND_WAIT_MS"])
MAX_SCROLL_OVERFLOW = int(os.environ["FRONTEND_MAX_SCROLL_OVERFLOW"])
HEADED = os.environ.get("FRONTEND_HEADED") == "1"
BROWSER_NAME = sys.argv[1]


class SmokeFailure(AssertionError):
    pass


def absolute_url(path: str) -> str:
    return urljoin(BASE_URL.rstrip("/") + "/", path.lstrip("/"))


def install_guards(page):
    console_messages = []
    page_errors = []

    def on_console(message):
        if message.type in ("error", "warning"):
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


def wait_for_text(page, text: str) -> str:
    deadline = time.monotonic() + WAIT_MS / 1000
    last = ""
    while time.monotonic() < deadline:
        last = body_text(page)
        if text in last:
            return last
        time.sleep(0.15)
    raise SmokeFailure(f"Expected page text not found: {text}; sample={last[:240]!r}")


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


def page_state(page):
    return page.evaluate(
        """() => {
            const bodyText = document.body ? document.body.innerText : '';
            const root = document.querySelector('#root');
            const bodyScrollWidth = document.body ? document.body.scrollWidth : 0;
            const documentScrollWidth = document.documentElement ? document.documentElement.scrollWidth : 0;
            const viewportWidth = window.innerWidth;
            return {
                bodyText,
                rootTextLength: root ? (root.textContent || '').trim().length : 0,
                scrollOverflow: Math.max(bodyScrollWidth, documentScrollWidth) - viewportWidth,
                hasFatalText: /Internal Server Error|Failed to fetch dynamically imported module|ReferenceError|TypeError|Unhandled Runtime Error/.test(bodyText),
                theme: localStorage.getItem('theme'),
                isDark: document.documentElement.classList.contains('dark'),
            };
        }"""
    )


def assert_page_health(page, console_messages, page_errors):
    state = page_state(page)
    if state["rootTextLength"] <= 20:
        raise SmokeFailure(f"Root text too short: {state['rootTextLength']}")
    if state["hasFatalText"]:
        raise SmokeFailure("Fatal text found in page body")
    overflow = max(0, state["scrollOverflow"])
    if overflow > MAX_SCROLL_OVERFLOW:
        raise SmokeFailure(f"Horizontal overflow {overflow}px")
    if page_errors:
        raise SmokeFailure("Page errors: " + " | ".join(page_errors[:5]))
    if console_messages:
        raise SmokeFailure("Console errors/warnings: " + " | ".join(console_messages[:5]))
    return state


def new_page(browser, viewport_name: str):
    page = browser.new_page(viewport=VIEWPORTS[viewport_name])
    console_messages, page_errors = install_guards(page)
    return page, console_messages, page_errors


def run_route_markers(browser):
    for viewport_name in VIEWPORTS:
        for route in ROUTES:
            page, console_messages, page_errors = new_page(browser, viewport_name)
            try:
                page.goto(absolute_url(route["path"]), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
                for marker in route["markers"]:
                    wait_for_text(page, marker)
                assert_page_health(page, console_messages, page_errors)
                print(f"PASS route-markers {viewport_name} {route['path']}")
            finally:
                page.close()


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
        page.goto(absolute_url("/analysis/stats"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "总体播放统计")
        click_text(page, "个人排行榜")
        expect_url(page, r"/analysis/charts$")
        wait_for_text(page, "PERSONAL CHARTS")
        click_text(page, "总体统计")
        expect_url(page, r"/analysis/stats$")
        wait_for_text(page, "总体播放统计")
        assert_page_health(page, console_messages, page_errors)
        print("PASS core-interactions analysis-tabs")
    finally:
        page.close()


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
        page.close()


def run_ai_insights_tabs(browser):
    page, console_messages, page_errors = new_page(browser, "desktop")
    try:
        page.goto(absolute_url("/ai-insights"), wait_until="domcontentloaded", timeout=WAIT_MS + 10000)
        wait_for_text(page, "AI 洞察")
        ready_text = wait_for_any_text(page, ["月报", "AI 功能尚未配置"])
        if "AI 功能尚未配置" in ready_text:
            click_text(page, "问答")
            wait_for_any_text(page, ["AI 功能尚未配置", "对话历史"])
            click_text(page, "报告")
            wait_for_any_text(page, ["AI 功能尚未配置", "AI 洞察"])
        else:
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
        page.close()


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
        page.close()


def run_core_interactions(browser):
    run_analysis_tabs(browser)
    run_billboard_routing(browser)
    run_ai_insights_tabs(browser)
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

  const routeConfig = JSON.stringify(DEFAULT_ROUTES)
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
          FRONTEND_ROUTES_JSON: routeConfig,
          FRONTEND_SCENARIOS_JSON: JSON.stringify(args.scenarios),
          FRONTEND_VIEWPORTS_JSON: viewportConfig,
          FRONTEND_WAIT_MS: String(args.waitMs),
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
