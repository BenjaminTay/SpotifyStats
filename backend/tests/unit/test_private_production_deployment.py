from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "deploy" / "production"


def test_docker_build_context_excludes_all_personal_data() -> None:
    source = (ROOT / ".dockerignore").read_text()
    lines = {line.strip() for line in source.splitlines() if line.strip()}

    assert "data" in lines
    assert "backups" in lines
    assert ".env" in lines

    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY data/" not in dockerfile


def test_production_compose_exposes_only_two_loopback_web_ports() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text())
    services = compose["services"]

    assert "ports" not in services["backend"]
    assert services["web"]["ports"] == ["127.0.0.1:${APP_GATEWAY_PORT:-3001}:3000"]
    assert services["public-web"]["ports"] == ["127.0.0.1:${PUBLIC_GATEWAY_PORT:-3002}:3000"]
    assert services["web"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert services["public-web"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert (
        "./public-nginx.conf:/etc/nginx/conf.d/default.conf:ro" in services["public-web"]["volumes"]
    )


def test_production_data_is_a_host_persistent_mount() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text())
    backend = compose["services"]["backend"]

    assert "./data:/app/data" in backend["volumes"]
    assert "./backups:/var/backups/spotify-stats" in backend["volumes"]
    assert backend["environment"]["FRONTEND_ORIGIN"].startswith("${APP_PUBLIC_URL")
    assert backend["environment"]["SPOTIFY_REDIRECT_URI"].endswith("/api/spotify/auth/callback")


def test_production_web_image_uses_the_hardened_nginx_config() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text()
    nginx = (PRODUCTION / "nginx.conf").read_text()

    assert "NGINX_CONFIG=deploy/production/nginx.conf" in workflow
    assert 'X-Frame-Options "DENY"' in nginx
    assert "location = /sw.js" in nginx
    assert "default_type application/manifest+json" in nginx
    assert "proxy_pass http://backend:8000/api/;" in nginx
    assert "X-SpotifyStats-Surface private-admin" in nginx

    public_nginx = (PRODUCTION / "public-nginx.conf").read_text()
    assert "X-SpotifyStats-Surface public-readonly" in public_nginx
    assert 'X-Robots-Tag "noindex, nofollow, noarchive"' in public_nginx
    assert "client_max_body_size 1m" in public_nginx
    assert "ai-insights" in public_nginx
    assert "versus/(track|album|artist)|release-cycle/compare" in public_nginx
    assert "limit_except GET HEAD OPTIONS {" in public_nginx


def test_deployment_scripts_keep_release_and_restore_guardrails() -> None:
    deploy = (PRODUCTION / "deploy.sh").read_text()
    restore = (PRODUCTION / "restore.sh").read_text()
    backup = (PRODUCTION / "backup.sh").read_text()
    tailscale = (PRODUCTION / "configure-tailscale.sh").read_text()
    public_funnel = (PRODUCTION / "configure-public-funnel.sh").read_text()

    assert "backup.sh" in deploy
    assert "127.0.0.1:$gateway_port" in deploy
    assert "previous-image-tag" in deploy
    assert "ALLOW_PRIVATE_ONLY_RELEASE=1" in deploy
    assert "tailscale funnel reset" in deploy
    assert "ALLOW_PRIVATE_ONLY_RELEASE=1" in (PRODUCTION / "rollback.sh").read_text()
    assert "--confirm" in restore
    assert "PRAGMA integrity_check" in restore
    assert "source.backup(target)" in backup
    assert "tailscale serve --bg" in tailscale
    assert "funnel" not in tailscale.lower()
    assert "tailscale funnel --bg --https=8443" in public_funnel
    assert '"surface":"public-readonly"' in public_funnel
    assert "HTTP $status" in public_funnel

    timer = (PRODUCTION / "install-backup-timer.sh").read_text()
    assert "Persistent=true" in timer
    assert "spotify-stats-backup.timer" in timer


def test_production_environment_template_contains_no_real_secret() -> None:
    template = (PRODUCTION / ".env.example").read_text()

    assert "SPOTIFY_STATS_TOKEN_KEY=replace-with" in template
    assert re.search(r"SPOTIFY_CLIENT_ID=\s*$", template, re.MULTILINE)
    assert re.search(r"SPOTIFY_CLIENT_SECRET=\s*$", template, re.MULTILINE)
