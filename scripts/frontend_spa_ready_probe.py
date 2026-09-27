#!/usr/bin/env python3
"""Measure first and same-document revisit readiness for the core home page."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page, Response, sync_playwright

ROUTES: dict[str, dict[str, Any]] = {
    "/": {
        "markers": ("YOUR LISTENING HEADLINE", "YOUR LISTENING ARCHIVE"),
        "api": re.compile(r"/api/home/overview$"),
    },
    "/analysis/stats": {
        "markers": ("PLAYBACK STATS", "独特歌曲"),
        "api": re.compile(r"/api/analysis/stats$"),
    },
    "/settings": {
        "markers": ("设置",),
        "api": None,
    },
}
ERROR_TEXT = re.compile(
    r"加载失败|请求失败|页面不存在|找不到页面|当前筛选的数据尚未发布|404 Not Found|Something went wrong",
    re.IGNORECASE,
)


def _snapshot_state(payload: object, headers: dict[str, str]) -> str:
    body = payload if isinstance(payload, dict) else {}
    snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else {}
    freshness = snapshot.get("freshness") or headers.get("x-snapshot-freshness")
    if freshness == "current":
        return "exact"
    if freshness == "last_known_good":
        return "LKG"
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
    if detail.get("error") == "snapshot_unavailable":
        return "missing"
    return "unknown"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wait-ms", type=int, default=30000)
    parser.add_argument("--chrome")
    return parser.parse_args()


def _loopback(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}


def _dom_state(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const root = document.querySelector('main') || document.body;
          return {
            path: location.pathname + location.search,
            text: root?.innerText || '',
            alerts: [...document.querySelectorAll('[role="alert"]')]
              .filter((node) => node.getBoundingClientRect().height > 0)
              .map((node) => node.textContent || ''),
            errorSkeleton: Boolean(root?.querySelector('[data-state="error"],.error-skeleton')),
            timeOrigin: performance.timeOrigin,
            navigationEntries: performance.getEntriesByType('navigation').length,
          };
        }"""
    )


def _dom_ready(route: str, state: dict[str, Any]) -> bool:
    """Require content unique to the destination, not only the updated URL."""
    spec = ROUTES[route]
    text = str(state.get("text") or "")
    return bool(
        state.get("path") == route
        and all(marker in text for marker in spec["markers"])
        and re.search(r"[0-9][0-9,.]*", text)
        and not state.get("alerts")
        and not state.get("errorSkeleton")
        and not ERROR_TEXT.search(text)
    )


def _visit(
    page: Page,
    base_url: str,
    route: str,
    phase: str,
    requests: list[dict[str, Any]],
    proven_api: dict[str, dict[str, Any]],
    wait_ms: int,
    *,
    document_navigation: bool = False,
) -> dict[str, Any]:
    spec = ROUTES[route]
    started = time.perf_counter()
    started_wall = time.time()
    request_start = len(requests)
    destination = base_url.rstrip("/") + route
    if document_navigation:
        page.goto(destination, wait_until="domcontentloaded", timeout=wait_ms)
    else:
        page.evaluate(
            """destination => {
              history.pushState({}, '', destination);
              window.dispatchEvent(new PopStateEvent('popstate', {state: history.state}));
              window.scrollTo(0, 0);
            }""",
            destination,
        )

    deadline = started + wait_ms / 1000
    ready_ms = None
    ready_monotonic = None
    ready_at_epoch = None
    api_source = None
    state: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        state = _dom_state(page)
        current = requests[request_start:]
        expected = (
            [item for item in current if spec["api"].search(str(item["path"]))]
            if spec["api"] is not None
            else []
        )
        successful = next(
            (
                item
                for item in reversed(expected)
                if item.get("finished")
                and item.get("status") == 200
                and item.get("valid_json") is True
                and not item.get("application_error")
            ),
            None,
        )
        cached = proven_api.get(route)
        api_evidence = (
            True if spec["api"] is None else successful or (cached if phase == "revisit" else None)
        )
        dom_ready = _dom_ready(route, state)
        failed = [
            item
            for item in current
            if item.get("failed")
            or (item.get("status") is not None and int(item["status"]) >= 400)
            or item.get("application_error")
        ]
        if dom_ready and api_evidence and not failed:
            ready_monotonic = time.perf_counter()
            ready_at_epoch = time.time()
            ready_ms = round((ready_monotonic - started) * 1000, 3)
            api_source = (
                "not_required_for_transition"
                if spec["api"] is None
                else "current_visit"
                if successful
                else "same_spa_prior_terminal"
            )
            if successful:
                proven_api[route] = successful
            break
        time.sleep(0.025)
    if ready_ms is None:
        raise RuntimeError(
            f"{phase} {route} did not become DOM/API ready: {json.dumps(state, ensure_ascii=False)}"
        )

    # Preserve core-ready latency, then wait only for APIs already initiated by
    # this visit to reach a terminal state within the original deadline.
    settled_since = None
    while time.perf_counter() < deadline:
        current = requests[request_start:]
        pending = [item for item in current if not item.get("finished") and not item.get("failed")]
        if not pending:
            settled_since = settled_since or time.perf_counter()
            if time.perf_counter() - settled_since >= 0.2:
                break
        else:
            settled_since = None
        time.sleep(0.025)
    current = requests[request_start:]
    pending = [item for item in current if not item.get("finished") and not item.get("failed")]
    failed = [
        item
        for item in current
        if item.get("failed")
        or (item.get("status") is not None and int(item["status"]) >= 400)
        or item.get("application_error")
    ]
    if pending or failed:
        raise RuntimeError(
            f"{phase} {route} API terminal failure: pending={len(pending)} failed={len(failed)}"
        )
    evidence = proven_api.get(route, {})
    snapshot_state = str(evidence.get("snapshot_state") or "unknown")
    if route == "/" and snapshot_state not in {"exact", "LKG"}:
        raise RuntimeError(f"{phase} home snapshot is not ready: {snapshot_state}")
    return {
        "phase": phase,
        "route": route,
        "started_at": started_wall,
        "ready_monotonic": ready_monotonic,
        "ready_at_epoch": ready_at_epoch,
        "core_ready_ms": ready_ms,
        "api_source": api_source,
        "api_terminal": {"complete": True, "success": True, "request_count": len(current)},
        "snapshot_state": snapshot_state,
        "dom": state,
        "request_indexes": list(range(request_start, len(requests))),
    }


def main() -> int:
    args = _parse_args()
    if not _loopback(args.base_url):
        raise ValueError("--base-url must be loopback")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    requests: list[dict[str, Any]] = []
    console_errors: list[str] = []
    proven_api: dict[str, dict[str, Any]] = {}
    probe_started = time.perf_counter()
    with sync_playwright() as playwright:
        launch = {"headless": True}
        if args.chrome:
            launch["executable_path"] = args.chrome
        browser = playwright.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def route_request(route) -> None:
            request = route.request
            if _loopback(request.url) and request.method in {"GET", "HEAD"}:
                route.continue_()
            else:
                route.abort("blockedbyclient")

        def request_started(request) -> None:
            if urlparse(request.url).path.startswith("/api/"):
                requests.append(
                    {
                        "url": request.url,
                        "path": urlparse(request.url).path,
                        "method": request.method,
                        "started_at_epoch": time.time(),
                        "status": None,
                        "finished": False,
                        "failed": None,
                    }
                )

        def response_received(response: Response) -> None:
            for item in reversed(requests):
                if item["url"] == response.url and item.get("status") is None:
                    item["status"] = response.status
                    item["response"] = response
                    break

        def request_finished(request) -> None:
            for item in reversed(requests):
                if (
                    item["url"] == request.url
                    and not item.get("finished")
                    and not item.get("failed")
                ):
                    response = item.pop("response", None)
                    payload: object = None
                    headers: dict[str, str] = {}
                    if response is not None:
                        try:
                            headers = {
                                str(k).lower(): str(v) for k, v in response.all_headers().items()
                            }
                            payload = response.json()
                        except Exception:
                            payload = None
                    item["valid_json"] = isinstance(payload, (dict, list))
                    item["application_error"] = bool(
                        isinstance(payload, dict)
                        and (
                            payload.get("error")
                            or payload.get("status") in {"error", "unavailable"}
                            or payload.get("snapshot_status") in {"unavailable", "missing", "error"}
                        )
                    )
                    item["snapshot_state"] = _snapshot_state(payload, headers)
                    item["finished_at_epoch"] = time.time()
                    item["finished"] = True
                    break

        def request_failed(request) -> None:
            for item in reversed(requests):
                if item["url"] == request.url and not item.get("finished"):
                    item["failed"] = request.failure or "request_failed"
                    item["finished_at_epoch"] = time.time()
                    break

        page.route("**/*", route_request)
        page.on("request", request_started)
        page.on("response", response_received)
        page.on("requestfinished", request_finished)
        page.on("requestfailed", request_failed)
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        samples = [
            _visit(
                page,
                args.base_url,
                "/",
                "first",
                requests,
                proven_api,
                args.wait_ms,
                document_navigation=True,
            ),
            _visit(
                page,
                args.base_url,
                "/analysis/stats",
                "transition",
                requests,
                proven_api,
                args.wait_ms,
            ),
            _visit(
                page,
                args.base_url,
                "/",
                "revisit",
                requests,
                proven_api,
                args.wait_ms,
            ),
        ]
        time_origins = {sample["dom"]["timeOrigin"] for sample in samples}
        navigation_entries = {sample["dom"]["navigationEntries"] for sample in samples}
        ignored_console_errors = [
            message
            for message in console_errors
            if message.startswith("Failed to load resource:") and "404" in message
        ]
        actionable_console_errors = [
            message for message in console_errors if message not in ignored_console_errors
        ]
        success = (
            len(time_origins) == 1 and navigation_entries == {1} and not actionable_console_errors
        )
        report = {
            "schema_version": 1,
            "tool": "frontend_spa_ready_probe",
            "generated_at": time.time(),
            "probe_started_monotonic": probe_started,
            "browser": {"engine": "chromium", "single_context": True, "single_page": True},
            "sequence": ["/", "/analysis/stats", "/"],
            "samples": samples,
            "requests": [{k: v for k, v in item.items() if k != "response"} for item in requests],
            "console_errors": actionable_console_errors,
            "ignored_isolated_cover_404_console_errors": ignored_console_errors,
            "same_document": len(time_origins) == 1 and navigation_entries == {1},
            "success": success,
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        context.close()
        browser.close()
    print(json.dumps({"success": success, "samples": samples}, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
