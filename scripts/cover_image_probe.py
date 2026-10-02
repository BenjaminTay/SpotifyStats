#!/usr/bin/env python3
"""Read-only image coverage/HTTP-cache probe against an existing web deployment.

Cold means a fresh Chromium browser context, not a cold server or CDN. Warm is
an ordinary reload in the same context after scrolling the cold page. Each pair
uses the same route and viewport. DOM observations include virtualized images
seen during scrolling. Timing is measured through this machine's network path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

VIEWPORTS = {
    "desktop": {"width": 1280, "height": 900, "device_scale_factor": 1},
    "desktop2": {"width": 1280, "height": 900, "device_scale_factor": 2},
    "compact": {"width": 768, "height": 1024, "device_scale_factor": 2},
    "phone": {"width": 390, "height": 844, "device_scale_factor": 3},
}
DEFAULT_ROUTES = [
    "/",
    "/analysis/stats",
    "/analysis/charts",
    "/analysis/records",
    "/account",
    "/yearly-review",
    "/billboard",
    "/billboard/number-ones",
    "/billboard/all-time",
    "/billboard/year-end",
    "/billboard/records",
    "/billboard/versus",
    "/music/search?q=Taylor",
    "/community",
]
DOM = """() => {
 const root = document.querySelector('main') || document.body;
 const images = [...document.images].map(img => {
   const r=img.getBoundingClientRect(), style=getComputedStyle(img);
   const section=img.closest('section[id], [id^="phone-yearly"], [id^="yearly-v2"]');
   return {src:img.getAttribute('src'), current_src:img.currentSrc, srcset:img.srcset,
    sizes:img.sizes, alt:img.alt, loading:img.loading, priority:img.fetchPriority,
    natural_width:img.naturalWidth, natural_height:img.naturalHeight, complete:img.complete,
    width:r.width, height:r.height, top:r.top, left:r.left, section:section?.id || null,
    visible:style.display!=='none' && style.visibility!=='hidden' && r.width>0 && r.height>0,
    in_viewport:r.bottom>0 && r.top<innerHeight && r.right>0 && r.left<innerWidth};
 });
 const resources=performance.getEntriesByType('resource').filter(e=> e.initiatorType==='img' || /\\/covers\\//.test(e.name)).map(e=>({url:e.name, initiator:e.initiatorType, start_ms:e.startTime, finish_ms:e.responseEnd, duration_ms:e.duration, encoded_bytes:e.encodedBodySize, decoded_bytes:e.decodedBodySize, transfer_bytes:e.transferSize}));
 const backgrounds=[...document.querySelectorAll('[style*="background"]')].map(el=>({background:getComputedStyle(el).backgroundImage, width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})).filter(x=>x.background.includes('url('));
 return {path:location.pathname+location.search, title:document.title, text:(root?.innerText||'').slice(0,4000), images, backgrounds, resources, dpr:devicePixelRatio,
   scroll_y:scrollY, scroll_height:document.documentElement.scrollHeight, viewport_height:innerHeight,
   sections:[...document.querySelectorAll('section[id],[id^="phone-yearly"],[id^="yearly-v2"]')].map(x=>({id:x.id, images:x.querySelectorAll('img').length})),
   loading:[...document.querySelectorAll('[aria-busy="true"],.animate-pulse')].filter(x=>x.getBoundingClientRect().height>0).length};
}"""
ERROR = re.compile(
    r"页面渲染错误|加载失败|请求失败|404 Not Found|Access denied|Just a moment|请先登录|没有权限|找不到页面",
    re.I,
)
EMPTY = re.compile(r"暂无|还没有|没有.*记录|尚未生成|未就绪|尚未发布|没有可用|没有数据")
COVER = re.compile(r"/covers/(albums|artists)/\d+(?:\.(?:thumb|\d+)\.webp|\.jpg)(?:\?|$)")


def summary(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in samples:
        groups.setdefault((item["route"], item["viewport"], item["cache"]), []).append(item)
    result = []
    for (route, viewport, cache), items in groups.items():
        row: dict[str, Any] = {
            "route": route,
            "viewport": viewport,
            "cache": cache,
            "samples": len(items),
            "states": [x["state"] for x in items],
        }
        for metric in (
            "first_viewport_ms",
            "full_ms",
            "image_finish_ms",
            "local_encoded_bytes",
            "local_transfer_bytes",
            "local_original_unique",
            "local_variant_unique",
            "broken_count",
            "observed_images",
        ):
            values = [
                x.get(metric)
                for x in items
                if x.get(metric) is not None and x.get("state") == "images_observed"
            ]
            row[metric + "_median"] = round(statistics.median(values), 2) if values else None
        result.append(row)
    return result


def save(report: dict[str, Any], path: Path) -> None:
    report["summary"] = summary(report["samples"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


async def visit(
    page: Any, base: str, route: str, viewport: str, run: int, cache: str, args: Any
) -> dict[str, Any]:
    started = time.monotonic()
    api_pending: set[str] = set()
    responses: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def request(req: Any) -> None:
        if "/api/" in req.url:
            api_pending.add(req.url)

    def finished(req: Any) -> None:
        api_pending.discard(req.url)

    def failed(req: Any) -> None:
        api_pending.discard(req.url)
        failures.append(
            {"url": req.url, "resource_type": req.resource_type, "failure": req.failure}
        )

    def response(res: Any) -> None:
        if "/api/" in res.url or res.request.resource_type == "image":
            responses.append(
                {
                    "url": res.url,
                    "status": res.status,
                    "method": res.request.method,
                    "type": res.request.resource_type,
                    "content_type": res.headers.get("content-type"),
                    "content_length": res.headers.get("content-length"),
                    "cache_control": res.headers.get("cache-control"),
                }
            )

    page.on("request", request)
    page.on("requestfinished", finished)
    page.on("requestfailed", failed)
    page.on("response", response)
    result: dict[str, Any] = {
        "route": route,
        "viewport": viewport,
        "run": run,
        "cache": cache,
        "state": "unknown",
    }
    observations: dict[str, dict[str, Any]] = {}
    resources: dict[str, dict[str, Any]] = {}

    def collect(state: dict[str, Any]) -> None:
        for img in state["images"]:
            if img["visible"]:
                key = "|".join(
                    str(img.get(x)) for x in ("src", "alt", "section", "width", "height")
                )
                observations[key] = img
        for item in state["resources"]:
            resources[item["url"]] = item

    try:
        if cache == "cold":
            await page.goto(
                urljoin(base + "/", route.lstrip("/")),
                wait_until="domcontentloaded",
                timeout=args.wait_ms,
            )
        else:
            await page.evaluate(
                "() => { history.scrollRestoration='manual'; window.scrollTo(0,0); }"
            )
            await page.reload(wait_until="domcontentloaded", timeout=args.wait_ms)
        deadline = time.monotonic() + args.wait_ms / 1000
        settled = None
        while time.monotonic() < deadline:
            state = await page.evaluate(DOM)
            if any(
                r["status"] >= 400 and re.search(r"/api/yearly-review/\d+\?", r["url"])
                for r in responses
            ):
                break
            first = [x for x in state["images"] if x["visible"] and x["in_viewport"]]
            ready = (
                bool(first or len(state["text"]) > 100)
                and not state["loading"]
                and "ASSEMBLING ISSUE" not in state["text"]
                and not api_pending
                and all(x["complete"] for x in first)
            )
            if ready:
                settled = settled or time.monotonic()
                if time.monotonic() - settled > 0.5:
                    break
            else:
                settled = None
            await page.wait_for_timeout(150)
        state = await page.evaluate(DOM)
        collect(state)
        result["first_viewport_ms"] = round((time.monotonic() - started) * 1000, 2)
        result["first_viewport"] = state
        first_urls = {
            x["current_src"] for x in state["images"] if x["visible"] and x["in_viewport"]
        }
        result["first_viewport_image_finish_ms"] = max(
            (x["finish_ms"] for x in state["resources"] if x["url"] in first_urls), default=None
        )
        # Preserve first viewport screenshot before scroll/lazy loading.
        if (
            run == 1
            and cache == "cold"
            and urlparse(route).path in ("/", "/analysis/records", "/account", "/yearly-review")
        ):
            shot = (
                args.output.parent
                / "screenshots"
                / f"{viewport}-{re.sub(r'[^A-Za-z0-9_-]', '-', route.strip('/')) or 'home'}.png"
            )
            shot.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(shot), full_page=False)
            result["screenshot"] = str(shot)
        scroll_steps = 0
        for scroll_steps in range(args.max_scrolls):
            before = await page.evaluate(
                "() => ({y:scrollY,h:innerHeight,total:document.documentElement.scrollHeight})"
            )
            await page.evaluate("() => window.scrollBy(0, innerHeight * .8)")
            await page.wait_for_timeout(250)
            state = await page.evaluate(DOM)
            collect(state)
            # Allow visible lazy images to settle with a bounded wait.
            if any(
                x["visible"] and x["in_viewport"] and not x["complete"] for x in state["images"]
            ):
                await page.wait_for_timeout(500)
                state = await page.evaluate(DOM)
                collect(state)
            if before["y"] + before["h"] >= before["total"] - 2:
                break
        final_deadline = time.monotonic() + args.wait_ms / 1000
        while time.monotonic() < final_deadline:
            state = await page.evaluate(DOM)
            collect(state)
            if (
                not api_pending
                and not state["loading"]
                and all(x["complete"] for x in state["images"] if x["visible"])
            ):
                break
            await page.wait_for_timeout(200)
        state = await page.evaluate(DOM)
        collect(state)
        result["full_ms"] = round((time.monotonic() - started) * 1000, 2)
        result["full"] = state
        result["scroll_steps"] = scroll_steps + 1
        result["scroll_complete"] = (
            state["scroll_y"] + state["viewport_height"] >= state["scroll_height"] - 2
        )
        result["scroll_end_reached"] = result["scroll_complete"]
        text = state["text"]
        primary_unavailable = [
            r
            for r in responses
            if r["status"] >= 400 and re.search(r"/api/yearly-review/\d+\?", r["url"])
        ]
        result["primary_api_errors"] = primary_unavailable
        if primary_unavailable:
            result["state"] = "primary_api_unavailable"
        elif ERROR.search(text):
            result["state"] = "error_or_access_boundary"
        elif observations:
            result["state"] = "images_observed"
        elif state["loading"] or api_pending:
            result["state"] = "not_ready"
        elif EMPTY.search(text):
            result["state"] = "explicit_empty"
        else:
            result["state"] = "no_images_requires_review"
        result["images"] = list(observations.values())
        result["resources"] = list(resources.values())
        local = [x for x in resources.values() if COVER.search(urlparse(x["url"]).path)]
        result["local_encoded_bytes"] = sum(x["encoded_bytes"] for x in local)
        result["local_transfer_bytes"] = sum(x["transfer_bytes"] for x in local)
        result["local_original_unique"] = sum(
            urlparse(x["url"]).path.endswith(".jpg") for x in local
        )
        result["local_variant_unique"] = len(local) - result["local_original_unique"]
        result["observed_images"] = len(observations)
        result["broken_count"] = sum(
            x["complete"] and x["natural_width"] == 0 for x in observations.values()
        )
        result["pending_count"] = sum(not x["complete"] for x in observations.values())
        result["image_finish_ms"] = max((x["finish_ms"] for x in resources.values()), default=None)
        result["external_timing_unavailable"] = [
            x["url"]
            for x in resources.values()
            if urlparse(x["url"]).netloc != urlparse(base).netloc and x["encoded_bytes"] == 0
        ]
        result["resolution_review"] = [
            {
                "src": x["current_src"],
                "display_width": round(x["width"], 2),
                "natural_width": x["natural_width"],
                "dpr": state["dpr"],
                "requested_pixels": round(x["width"] * state["dpr"], 2),
                "section": x["section"],
            }
            for x in observations.values()
            if x["natural_width"] and x["natural_width"] + 1 < x["width"] * state["dpr"]
        ]
    except Exception as exc:
        result["state"] = "exception"
        result["exception"] = str(exc)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
    finally:
        result["responses"] = responses
        result["request_failures"] = failures
        result["pending_api"] = sorted(api_pending)
        page.remove_listener("request", request)
        page.remove_listener("requestfinished", finished)
        page.remove_listener("requestfailed", failed)
        page.remove_listener("response", response)
    return result


async def run(args: Any) -> None:
    from playwright.async_api import async_playwright

    routes = args.routes.split(",") if args.routes else DEFAULT_ROUTES
    viewports = args.viewports.split(",")
    report = {
        "version": "cover_image_probe_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "browser_cache_contract": "fresh_context_cold_then_normal_reload_warm",
        "server_cache": "unknown",
        "network_path": "executing_machine_to_base_url",
        "routes": routes,
        "viewports": {x: VIEWPORTS[x] for x in viewports},
        "samples": [],
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=args.chrome or None)
        try:
            for viewport in viewports:
                for route in routes:
                    for number in range(1, args.runs + 1):
                        context = await browser.new_context(
                            viewport={key: VIEWPORTS[viewport][key] for key in ("width", "height")},
                            device_scale_factor=VIEWPORTS[viewport]["device_scale_factor"],
                            is_mobile=viewport == "phone",
                            has_touch=viewport == "phone",
                            service_workers="block",
                        )
                        page = await context.new_page()
                        try:
                            for cache in ("cold", "warm"):
                                item = await visit(
                                    page,
                                    args.base_url.rstrip("/"),
                                    route,
                                    viewport,
                                    number,
                                    cache,
                                    args,
                                )
                                report["samples"].append(item)
                                save(report, args.output)
                                print(
                                    json.dumps(
                                        {
                                            k: item.get(k)
                                            for k in (
                                                "route",
                                                "viewport",
                                                "run",
                                                "cache",
                                                "state",
                                                "local_encoded_bytes",
                                                "local_transfer_bytes",
                                                "local_original_unique",
                                                "local_variant_unique",
                                                "first_viewport_ms",
                                                "broken_count",
                                            )
                                        },
                                        ensure_ascii=False,
                                    ),
                                    flush=True,
                                )
                        finally:
                            await context.close()
        finally:
            await browser.close()
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    save(report, args.output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--routes", help="Comma-separated paths, query strings allowed")
    parser.add_argument(
        "--viewports",
        default="desktop,phone,compact,desktop2",
        help="Comma-separated named viewport presets",
    )
    parser.add_argument("--wait-ms", type=int, default=25000)
    parser.add_argument("--max-scrolls", type=int, default=80)
    parser.add_argument("--chrome")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    if any(x not in VIEWPORTS for x in args.viewports.split(",")):
        parser.error("Unknown viewport preset")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
