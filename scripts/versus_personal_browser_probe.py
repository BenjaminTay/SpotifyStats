#!/usr/bin/env python3
"""Real-browser Versus personal-statistics acceptance; no API response mocks.

Each engine/viewport/kind gets a fresh browser context. Measurements use actual
selector clicks, current DOM rows and real HTTP responses. --api-base-url routes
API/covers to the supplied real backend for a static production preview.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

VIEWPORTS = {
    360: 800,
    390: 844,
    430: 932,
    768: 1024,
    1280: 800,
}
KIND_LABELS = {"track": "单曲", "album": "专辑", "artist": "艺人"}
BASE_LABELS = [
    "个人总播放",
    "总时长 (小时)",
    "日均播放",
    "日均时长 (小时)",
    "单天最多播放",
    "活跃天数",
]
RANK_LABELS = ["全时段排名", "近6个月排名", "近4周排名"]
PENDING = re.compile(r"加载中|更新中|待更新|暂不可用")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--api-base-url")
    parser.add_argument("--browsers", default="chromium,firefox,webkit")
    parser.add_argument("--widths", default="360,390,430,768,1280")
    parser.add_argument("--kinds", default="track,album,artist")
    parser.add_argument("--counts", default="2,4")
    parser.add_argument(
        "--entities-json", type=Path, help="Optional real picker items by tracks/albums/artists"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/playwright/versus-personal/result.json")
    )
    parser.add_argument("--wait-ms", type=int, default=90000)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--enforce-performance", action="store_true")
    return parser.parse_args()


async def rows(page, labels):
    result = {}
    for label in labels:
        locator = page.get_by_role("row").filter(has=page.get_by_text(label, exact=True))
        if await locator.count() != 1:
            return None
        result[label] = await locator.get_by_role("cell").all_text_contents()
    return result


def ready(values, count):
    return values is not None and all(
        len(cells) == count and not any(PENDING.search(cell) for cell in cells)
        for cells in values.values()
    )


async def settle(page, count, started, timeout_ms, result):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        base = await rows(page, BASE_LABELS)
        ranks = await rows(page, RANK_LABELS)
        elapsed = (time.monotonic() - started) * 1000
        if ranks is not None and any(
            "暂不可用" in cell or "待更新" in cell for cells in ranks.values() for cell in cells
        ):
            raise RuntimeError("Real rank snapshot unavailable; ready-rank acceptance cannot pass")
        if base is not None and any(
            "暂不可用" in cell for cells in base.values() for cell in cells
        ):
            raise RuntimeError("Real personal statistics unavailable")
        if ready(base, count) and result.get("base_visible_ms") is None:
            result["base_visible_ms"] = round(elapsed, 2)
            result["base_values"] = base
        if ready(ranks, count) and result.get("ranks_visible_ms") is None:
            result["ranks_visible_ms"] = round(elapsed, 2)
            result["rank_values"] = ranks
        if result.get("base_visible_ms") is not None and result.get("ranks_visible_ms") is not None:
            result["personal_visible_ms"] = round(elapsed, 2)
            return
        await page.wait_for_timeout(25)
    result["base_values"] = await rows(page, BASE_LABELS)
    result["rank_values"] = await rows(page, RANK_LABELS)
    raise TimeoutError("Personal rows did not settle within the configured timeout")


def request_count(entry):
    body = entry.get("body", {})
    return len(body.get("track_ids", body.get("albums", body.get("artist_names", []))))


async def verify_response_values(requests, kind, objects, measured, page):
    count = measured["count"]
    responses = {}
    for group in ("stats", "ranks"):
        candidates = [
            entry
            for entry in requests
            if entry["url"].split("?")[0].endswith(f"/{kind}/personal-{group}")
            and request_count(entry) == count
            and entry.get("status") == 200
            and "result" in entry
        ]
        if not candidates:
            raise AssertionError(f"Missing real {group} response for {count} objects")
        responses[group] = candidates[-1]["result"]
    snapshot = responses["ranks"]["snapshot"]
    if (
        snapshot["status"] != "ready"
        or snapshot["freshness"] != "current"
        or snapshot["source_revision"] != responses["ranks"]["source_revision"]
        or snapshot["target_revision"] != responses["ranks"]["source_revision"]
    ):
        raise AssertionError("Rank publication is not exact-ready for the current source")
    measured["snapshot"] = snapshot
    fields = ("filter_fingerprint", "source_revision", "statistics_contract_version")
    if any(responses["stats"][field] != responses["ranks"][field] for field in fields):
        raise AssertionError("Personal statistics and ranks source contexts differ")
    measured["context"] = {field: responses["stats"][field] for field in fields}
    definitions = [
        ("个人总播放", "total_plays", None),
        ("总时长 (小时)", "total_hours", 1),
        ("日均播放", "avg_daily_plays", 1),
        ("日均时长 (小时)", "avg_daily_hours", 2),
        ("单天最多播放", "max_daily_plays", None),
        ("活跃天数", "active_days", None),
    ]
    rank_periods = list(zip(RANK_LABELS, ("lifetime", "last_6_months", "last_4_weeks")))
    complete = True
    for index, item in enumerate(objects[:count]):
        identity = (
            ["track", item["track_id"]]
            if kind == "track"
            else ["album", item["artist_name"], item["album_name"]]
            if kind == "album"
            else ["artist", item["artist_name"]]
        )
        key = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
        stats_entity = next(
            entity for entity in responses["stats"]["entities"] if entity["requested_key"] == key
        )
        rank_entity = next(
            entity for entity in responses["ranks"]["entities"] if entity["requested_key"] == key
        )
        for label, metric, digits in definitions:
            value = stats_entity["metrics"][metric]
            expected = await page.evaluate(
                "({ value, digits }) => digits == null ? String(value) : Number(value).toFixed(digits)",
                {"value": value, "digits": digits},
            )
            if measured["base_values"][label][index] != expected:
                raise AssertionError(f"Displayed {label} differs from real API response for {key}")
        for label, period in rank_periods:
            value = rank_entity["ranks"][period]
            complete = complete and value is not None
            if measured["rank_values"][label][index] != (f"#{value}" if value is not None else "—"):
                raise AssertionError(f"Displayed {label} differs from real API response for {key}")
    if not complete and measured["final_score_visible"]:
        raise AssertionError("Final winner shown while a current personal rank is missing")
    measured["real_response_values_match"] = True


async def scenario(browser, engine, width, kind, args, explicit_items):
    context = await browser.new_context(viewport={"width": width, "height": VIEWPORTS[width]})
    page = await context.new_page()
    page.set_default_timeout(args.wait_ms)
    requests = []
    pending = {}
    tasks = set()
    route_tasks = set()
    errors = []
    result = {
        "engine": engine,
        "width": width,
        "height": VIEWPORTS[width],
        "kind": kind,
        "counts": [],
        "requests": requests,
        "console": errors,
        "status": "FAIL",
    }
    lists = {}

    def requested(request):
        if not urlsplit(request.url).path.startswith("/api/"):
            return
        entry = {
            "url": request.url,
            "method": request.method,
            "started_at": time.monotonic(),
            "status": None,
        }
        if "/versus/" in request.url and request.post_data:
            entry["body"] = json.loads(request.post_data)
        requests.append(entry)
        pending[id(request)] = entry

    async def responded(response):
        request = response.request
        entry = pending.get(id(request))
        if entry is not None:
            entry.update(
                status=response.status,
                duration_ms=round((time.monotonic() - entry["started_at"]) * 1000, 2),
                server_timing=response.headers.get("server-timing"),
            )
        if "/billboard/entity-lists" in response.url or "/versus/" in response.url:
            try:
                body = await response.json()
                if "/billboard/entity-lists" in response.url and response.ok:
                    lists.update(body)
                if entry is not None:
                    entry["result"] = body
            except Exception as error:
                if entry is not None:
                    entry["read_error"] = str(error)

    def response_event(response):
        task = asyncio.create_task(responded(response))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def failed(request):
        entry = pending.get(id(request))
        if entry is not None:
            entry["failure"] = request.failure

    if args.api_base_url:

        async def forward(route):
            task = asyncio.current_task()
            route_tasks.add(task)
            parsed = urlsplit(route.request.url)
            target = (
                args.api_base_url.rstrip("/")
                + parsed.path
                + ("?" + parsed.query if parsed.query else "")
            )
            try:
                response = await route.fetch(url=target, timeout=args.wait_ms)
                # APIRequestContext returns a decoded body. Forward its actual bytes
                # without the wire encoding/length, which Firefox would decode again.
                body = await response.body()
                headers = {
                    name: value
                    for name, value in response.headers.items()
                    if name.lower() not in {"content-encoding", "content-length"}
                }
                await route.fulfill(status=response.status, headers=headers, body=body)
            except PlaywrightError as error:
                if "closed" not in str(error).lower():
                    raise
            finally:
                route_tasks.discard(task)

        await page.route(re.compile(r"^https?://[^/]+/(?:api|covers)(?:/|$).*"), forward)
    page.on("request", requested)
    page.on("response", response_event)
    page.on("requestfailed", failed)
    page.on(
        "console",
        lambda message: (
            errors.append({"type": message.type, "text": message.text})
            if message.type in {"error", "warning"}
            else None
        ),
    )
    page.on("pageerror", lambda error: errors.append({"type": "pageerror", "text": str(error)}))
    try:
        await page.goto(
            args.base_url.rstrip("/") + "/billboard/versus", wait_until="domcontentloaded"
        )
        await page.evaluate("""() => {
          window.__versusProbeSelections = [];
          document.addEventListener('click', event => {
            const button = event.target.closest('button');
            if (button && button.textContent.includes('+ 添加'))
              window.__versusProbeSelections.push({at_ms: performance.now(), label: button.textContent.trim()});
          }, true);
        }""")
        await page.get_by_role("button", name=KIND_LABELS[kind], exact=True).click()
        deadline = time.monotonic() + args.wait_ms / 1000
        while not lists and time.monotonic() < deadline:
            await page.wait_for_timeout(25)
        source = explicit_items or lists
        items = source.get({"track": "tracks", "album": "albums", "artist": "artists"}[kind], [])[
            :4
        ]
        if len(items) < 4:
            raise RuntimeError(f"Only {len(items)} real picker candidates available; require four")
        result["objects"] = items
        await page.get_by_role(
            "button", name=f"搜索{KIND_LABELS[kind]}以添加...", exact=False
        ).click()
        count_targets = sorted(int(count) for count in args.counts.split(","))
        for count in range(1, max(count_targets) + 1):
            item = items[count - 1]
            search = page.get_by_placeholder("输入关键词搜索...")
            if not await search.is_visible():
                await page.get_by_role(
                    "button", name=f"搜索{KIND_LABELS[kind]}以添加...", exact=False
                ).click()
            await search.fill(item["display"])
            item_button = page.get_by_role("button", name=item["display"] + " + 添加", exact=True)
            # The real UI may display names through the user's Chinese preference.
            if not await item_button.count():
                item_button = (
                    page.locator(".mobile-versus-search button").filter(has_text="+ 添加").first
                )
            started = time.monotonic()
            await item_button.click()
            if count not in count_targets:
                continue
            measured = {"count": count, "base_visible_ms": None, "ranks_visible_ms": None}
            result["counts"].append(measured)
            await settle(page, count, started, args.wait_ms, measured)
            # Billboard is independently allowed to settle after the personal rows.
            await page.wait_for_function(
                """() => ![...document.querySelectorAll('tr')].some(row => row.textContent.includes('走势点数') && row.textContent.includes('加载中'))""",
                timeout=args.wait_ms,
            )
            measured["chart_settled_ms"] = round((time.monotonic() - started) * 1000, 2)
            measured["full_visible_ms"] = measured["chart_settled_ms"]
            measured["final_score_visible"] = bool(
                await page.get_by_text("总分 (胜出指标数)", exact=True).count()
                or await page.get_by_text("对决结果", exact=True).count()
            )
            measured["partial_score_visible"] = bool(
                await page.get_by_text("已完成指标得分", exact=True).count()
            )
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await verify_response_values(requests, kind, items, measured, page)
            measured["overflow_px"] = await page.evaluate(
                "Math.max(0, document.documentElement.scrollWidth - innerWidth)"
            )
            screenshot = args.output.parent / f"{engine}-{width}-{kind}-{count}.png"
            await page.screenshot(path=str(screenshot), full_page=True)
            measured["screenshot"] = str(screenshot.resolve())
            personal_before = sum("/personal-" in item["url"] for item in requests)
            before_order = await rows(page, BASE_LABELS)
            await page.locator('button[title="上移"]').nth(count - 1).click()
            await page.wait_for_timeout(350)
            after_order = await rows(page, BASE_LABELS)
            measured["reorder_personal_requests"] = (
                sum("/personal-" in item["url"] for item in requests) - personal_before
            )
            measured["reorder_values_correct"] = all(
                after_order[label]
                == before_order[label][: count - 2]
                + [before_order[label][-1], before_order[label][-2]]
                for label in BASE_LABELS
            )
            # Restore display order before adding the third/fourth objects.
            await page.locator('button[title="下移"]').nth(count - 2).click()
            await page.wait_for_timeout(100)
            if (
                measured["overflow_px"]
                or measured["reorder_personal_requests"]
                or not measured["reorder_values_correct"]
            ):
                raise AssertionError("Overflow or reorder acceptance failed")
            if args.enforce_performance:
                limit = 2000 if kind == "artist" else 1500
                if measured["base_visible_ms"] > limit or measured["personal_visible_ms"] > 2000:
                    raise AssertionError(
                        "User-visible personal performance exceeded the planned budget"
                    )
        result["selection_events"] = await page.evaluate("window.__versusProbeSelections || []")
        if len(result["selection_events"]) >= 4:
            result["third_fourth_gap_ms"] = round(
                result["selection_events"][3]["at_ms"] - result["selection_events"][2]["at_ms"], 2
            )
        result["legacy_detail_stats_requests"] = sum(
            "/api/music/" in entry["url"] and "/stats" in entry["url"] for entry in requests
        )
        if result["legacy_detail_stats_requests"]:
            raise AssertionError("Versus requested heavy complete detail statistics")
        if errors:
            raise AssertionError("Browser console errors/warnings or page errors occurred")
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = str(error)
        screenshot = args.output.parent / f"{engine}-{width}-{kind}-failed.png"
        await page.screenshot(path=str(screenshot), full_page=True)
        result["failure_screenshot"] = str(screenshot.resolve())
    finally:
        try:
            result["selection_events"] = await page.evaluate("window.__versusProbeSelections || []")
            if len(result["selection_events"]) >= 4:
                result["third_fourth_gap_ms"] = round(
                    result["selection_events"][3]["at_ms"] - result["selection_events"][2]["at_ms"],
                    2,
                )
        except PlaywrightError:
            pass
        await context.close()
        if tasks or route_tasks:
            await asyncio.gather(*tasks, *route_tasks, return_exceptions=True)
        for entry in requests:
            entry.pop("started_at", None)
    return result


async def main(args):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    explicit_items = json.loads(args.entities_json.read_text()) if args.entities_json else None
    report = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "evidence": "real_api_real_browser",
        "base_url": args.base_url,
        "api_base_url": args.api_base_url,
        "scenarios": [],
        "python": {"path": sys.executable, "version": sys.version.split()[0]},
        "browser_versions": {},
    }
    async with async_playwright() as playwright:
        for engine in args.browsers.split(","):
            browser = await getattr(playwright, engine).launch(headless=not args.headed)
            report["browser_versions"][engine] = browser.version
            try:
                for width in map(int, args.widths.split(",")):
                    for kind in args.kinds.split(","):
                        result = await scenario(browser, engine, width, kind, args, explicit_items)
                        report["scenarios"].append(result)
                        args.output.write_text(
                            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                        )
                        print(f"{engine} {width} {kind}: {result['status']}", flush=True)
            finally:
                await browser.close()
    report["summary"] = {}
    for kind in args.kinds.split(","):
        samples = [
            sample
            for result in report["scenarios"]
            if result["kind"] == kind
            for sample in result["counts"]
        ]
        report["summary"][kind] = {
            "samples": len(samples),
            **{
                f"max_{metric}": max(
                    (sample[metric] for sample in samples if sample.get(metric) is not None),
                    default=None,
                )
                for metric in (
                    "base_visible_ms",
                    "ranks_visible_ms",
                    "personal_visible_ms",
                    "full_visible_ms",
                    "overflow_px",
                    "reorder_personal_requests",
                )
            },
        }
    report["status"] = (
        "PASS" if all(result["status"] == "PASS" for result in report["scenarios"]) else "FAIL"
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(arguments())))
