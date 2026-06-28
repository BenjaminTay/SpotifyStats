#!/usr/bin/env python3
"""Non-destructive external Spotify OAuth/ngrok probe.

The probe assumes the backend and frontend are already running and, when
``--ngrok-api-url`` is provided, that ngrok has already established a tunnel.
It validates the externally reachable OAuth entry points without exchanging a
real authorization code or disconnecting the current Spotify account.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://stuffing-nebula-tamer.ngrok-free.dev"
DEFAULT_NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"
DEFAULT_EXPECTED_NGROK_ADDR = "http://localhost:5173"
DEFAULT_TIMEOUT_SECONDS = 20.0
AUTH_DATA_KEYS = frozenset(
    {"artists", "tracks", "recently_played", "followed_artists", "playlists"}
)


@dataclass(frozen=True)
class ProbeCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ProbeReport:
    base_url: str
    checks: tuple[ProbeCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def header_value(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_opener(*, no_proxy: bool = True, follow_redirects: bool = True):
    handlers: list[Any] = []
    if no_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    if not follow_redirects:
        handlers.append(NoRedirect)
    return urllib.request.build_opener(*handlers)


def request_json(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    no_proxy: bool = True,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    req = urllib.request.Request(
        url,
        headers={"accept": "application/json", "ngrok-skip-browser-warning": "true"},
    )
    opener = build_opener(no_proxy=no_proxy, follow_redirects=True)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body[:300]}
        return exc.code, parsed, dict(exc.headers)


def request_redirect(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    no_proxy: bool = True,
) -> tuple[int, dict[str, str]]:
    req = urllib.request.Request(url, headers={"ngrok-skip-browser-warning": "true"})
    opener = build_opener(no_proxy=no_proxy, follow_redirects=False)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers)


def evaluate_ngrok_tunnel(
    *,
    base_url: str,
    status: int,
    body: dict[str, Any],
    expected_addr: str,
) -> ProbeCheck:
    tunnels = body.get("tunnels")
    if status != 200 or not isinstance(tunnels, list):
        return ProbeCheck("ngrok_tunnel", False, f"status={status} body_keys={sorted(body.keys())}")

    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            continue
        config = tunnel.get("config")
        addr = config.get("addr") if isinstance(config, dict) else None
        public_url = tunnel.get("public_url")
        if public_url == base_url and addr == expected_addr:
            return ProbeCheck("ngrok_tunnel", True, f"public_url={public_url} addr={addr}")
    return ProbeCheck(
        "ngrok_tunnel",
        False,
        f"missing tunnel public_url={base_url} addr={expected_addr}",
    )


def evaluate_health(status: int, body: dict[str, Any], headers: dict[str, str]) -> ProbeCheck:
    request_id = header_value(headers, "x-request-id")
    ok = status == 200 and body.get("status") == "ok" and bool(request_id)
    return ProbeCheck("external_health", ok, f"status={status} request_id={request_id} body={body}")


def evaluate_spotify_status(
    status: int, body: dict[str, Any], headers: dict[str, str]
) -> ProbeCheck:
    request_id = header_value(headers, "x-request-id")
    ok = status == 200 and isinstance(body.get("connected"), bool) and bool(request_id)
    return ProbeCheck(
        "spotify_status",
        ok,
        f"status={status} connected={body.get('connected')} request_id={request_id}",
    )


def evaluate_auth_data(status: int, body: dict[str, Any], headers: dict[str, str]) -> ProbeCheck:
    request_id = header_value(headers, "x-request-id")
    missing = sorted(AUTH_DATA_KEYS - body.keys())
    ok = status == 200 and not missing and bool(request_id)
    return ProbeCheck(
        "spotify_auth_data",
        ok,
        f"status={status} keys={sorted(body.keys())} missing={missing} request_id={request_id}",
    )


def evaluate_login_url(
    *,
    base_url: str,
    status: int,
    body: dict[str, Any],
    headers: dict[str, str],
) -> ProbeCheck:
    request_id = header_value(headers, "x-request-id")
    auth_url = body.get("auth_url")
    if status != 200 or not isinstance(auth_url, str):
        return ProbeCheck(
            "spotify_login_url",
            False,
            f"status={status} auth_url_present={isinstance(auth_url, str)} request_id={request_id}",
        )

    parsed = urllib.parse.urlparse(auth_url)
    params = urllib.parse.parse_qs(parsed.query)
    redirect_uri = params.get("redirect_uri", [""])[0]
    expected_redirect_uri = f"{base_url}/api/spotify/auth/callback"
    state_present = bool(params.get("state", [""])[0])
    challenge_present = bool(params.get("code_challenge", [""])[0])
    ok = (
        parsed.netloc == "accounts.spotify.com"
        and redirect_uri == expected_redirect_uri
        and state_present
        and challenge_present
        and bool(request_id)
    )
    return ProbeCheck(
        "spotify_login_url",
        ok,
        f"status={status} host={parsed.netloc} redirect_uri={redirect_uri} "
        f"state_present={state_present} challenge_present={challenge_present} request_id={request_id}",
    )


def evaluate_invalid_state_callback(
    *,
    base_url: str,
    status: int,
    headers: dict[str, str],
) -> ProbeCheck:
    request_id = header_value(headers, "x-request-id")
    location = header_value(headers, "location") or ""
    expected_location = f"{base_url}/settings?spotify_error=invalid_state"
    ok = status in {302, 303, 307, 308} and location == expected_location and bool(request_id)
    return ProbeCheck(
        "invalid_state_callback",
        ok,
        f"status={status} location={location} request_id={request_id}",
    )


def run_probe(
    *,
    base_url: str = DEFAULT_BASE_URL,
    ngrok_api_url: str | None = DEFAULT_NGROK_API_URL,
    expected_ngrok_addr: str = DEFAULT_EXPECTED_NGROK_ADDR,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    no_proxy: bool = True,
) -> ProbeReport:
    base_url = normalize_base_url(base_url)
    checks: list[ProbeCheck] = []

    if ngrok_api_url:
        status, body, _ = request_json(ngrok_api_url, timeout=timeout, no_proxy=no_proxy)
        checks.append(
            evaluate_ngrok_tunnel(
                base_url=base_url,
                status=status,
                body=body,
                expected_addr=expected_ngrok_addr,
            )
        )

    status, body, headers = request_json(f"{base_url}/api/health", timeout=timeout, no_proxy=no_proxy)
    checks.append(evaluate_health(status, body, headers))

    status, body, headers = request_json(
        f"{base_url}/api/spotify/auth/status", timeout=timeout, no_proxy=no_proxy
    )
    checks.append(evaluate_spotify_status(status, body, headers))

    status, body, headers = request_json(
        f"{base_url}/api/spotify/auth/data", timeout=timeout, no_proxy=no_proxy
    )
    checks.append(evaluate_auth_data(status, body, headers))

    status, body, headers = request_json(
        f"{base_url}/api/spotify/auth/login", timeout=timeout, no_proxy=no_proxy
    )
    checks.append(evaluate_login_url(base_url=base_url, status=status, body=body, headers=headers))

    status, headers = request_redirect(
        f"{base_url}/api/spotify/auth/callback?code=probe-code&state=missing-state",
        timeout=timeout,
        no_proxy=no_proxy,
    )
    checks.append(evaluate_invalid_state_callback(base_url=base_url, status=status, headers=headers))

    return ProbeReport(base_url=base_url, checks=tuple(checks))


def report_to_dict(report: ProbeReport) -> dict[str, Any]:
    return {
        "base_url": report.base_url,
        "ok": report.ok,
        "checks": [asdict(check) for check in report.checks],
    }


def write_json_report(report: ProbeReport, output: Path) -> None:
    output.write_text(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2) + "\n")


def render_report(report: ProbeReport) -> str:
    lines = [
        f"Spotify OAuth external probe: {'PASS' if report.ok else 'FAIL'}",
        f"Base URL: {report.base_url}",
    ]
    for check in report.checks:
        status = "PASS" if check.ok else "FAIL"
        lines.append(f"{status} {check.name}: {check.detail}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--ngrok-api-url",
        default=DEFAULT_NGROK_API_URL,
        help="Set to an empty string to skip local ngrok 4040 verification.",
    )
    parser.add_argument("--expected-ngrok-addr", default=DEFAULT_EXPECTED_NGROK_ADDR)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--use-env-proxy",
        action="store_true",
        help="Use environment proxy variables. By default the probe bypasses proxies.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_probe(
        base_url=args.base_url,
        ngrok_api_url=args.ngrok_api_url or None,
        expected_ngrok_addr=args.expected_ngrok_addr,
        timeout=args.timeout,
        no_proxy=not args.use_env_proxy,
    )
    print(render_report(report))
    if args.json_output:
        write_json_report(report, args.json_output)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
