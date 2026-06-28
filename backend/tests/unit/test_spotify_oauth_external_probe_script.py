from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_header_value_is_case_insensitive():
    from scripts.spotify_oauth_external_probe import header_value

    headers = {"x-request-id": "rid-1", "Location": "https://example.test/settings"}

    assert header_value(headers, "X-Request-ID") == "rid-1"
    assert header_value(headers, "location") == "https://example.test/settings"
    assert header_value(headers, "missing") is None


def test_evaluate_ngrok_tunnel_requires_expected_public_url_and_addr():
    from scripts.spotify_oauth_external_probe import evaluate_ngrok_tunnel

    check = evaluate_ngrok_tunnel(
        base_url="https://stuffing-nebula-tamer.ngrok-free.dev",
        status=200,
        body={
            "tunnels": [
                {
                    "public_url": "https://stuffing-nebula-tamer.ngrok-free.dev",
                    "config": {"addr": "http://localhost:5173"},
                }
            ]
        },
        expected_addr="http://localhost:5173",
    )

    assert check.ok is True
    assert check.name == "ngrok_tunnel"


def test_evaluate_login_url_requires_ngrok_redirect_state_and_pkce():
    from scripts.spotify_oauth_external_probe import evaluate_login_url

    params = {
        "redirect_uri": "https://stuffing-nebula-tamer.ngrok-free.dev/api/spotify/auth/callback",
        "state": "state-ok",
        "code_challenge": "challenge-ok",
    }
    auth_url = "https://accounts.spotify.com/authorize?" + "&".join(
        f"{key}={value}" for key, value in params.items()
    )

    check = evaluate_login_url(
        base_url="https://stuffing-nebula-tamer.ngrok-free.dev",
        status=200,
        body={"auth_url": auth_url},
        headers={"X-Request-ID": "rid-2"},
    )

    assert check.ok is True
    assert "state_present=True" in check.detail
    assert "challenge_present=True" in check.detail


def test_evaluate_invalid_state_callback_requires_ngrok_settings_location_and_request_id():
    from scripts.spotify_oauth_external_probe import evaluate_invalid_state_callback

    check = evaluate_invalid_state_callback(
        base_url="https://stuffing-nebula-tamer.ngrok-free.dev",
        status=307,
        headers={
            "location": "https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state",
            "x-request-id": "rid-3",
        },
    )

    assert check.ok is True


def test_report_rendering_and_json_shape(tmp_path):
    from scripts.spotify_oauth_external_probe import (
        ProbeCheck,
        ProbeReport,
        render_report,
        report_to_dict,
        write_json_report,
    )

    report = ProbeReport(
        base_url="https://stuffing-nebula-tamer.ngrok-free.dev",
        checks=(ProbeCheck("external_health", True, "status=200"),),
    )

    assert report.ok is True
    assert "PASS external_health" in render_report(report)
    assert report_to_dict(report)["checks"][0]["name"] == "external_health"

    output = tmp_path / "oauth_probe.json"
    write_json_report(report, output)
    parsed = json.loads(output.read_text())
    assert parsed["ok"] is True
    assert parsed["base_url"] == "https://stuffing-nebula-tamer.ngrok-free.dev"
