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


def test_production_compose_exposes_only_profile_selected_loopback_ports() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text())
    services = compose["services"]

    assert "ports" not in services["backend"]
    assert services["web"]["profiles"] == ["full", "dual"]
    assert services["public-web"]["profiles"] == ["showcase", "dual"]
    assert services["web"]["ports"] == ["127.0.0.1:${APP_GATEWAY_PORT:-3001}:3000"]
    assert services["public-web"]["ports"] == ["127.0.0.1:${PUBLIC_GATEWAY_PORT:-3002}:3000"]
    assert services["web"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert services["public-web"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert (
        "./private-nginx.conf.template:/etc/nginx/templates/default.conf.template:ro"
        in services["web"]["volumes"]
    )
    assert (
        "./public-nginx.conf.template:/etc/nginx/templates/default.conf.template:ro"
        in services["public-web"]["volumes"]
    )


def test_production_data_is_one_host_persistent_mount_and_one_backend() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text())
    services = compose["services"]
    backend = services["backend"]

    assert "./data:/app/data" in backend["volumes"]
    assert "./backups:/var/backups/spotify-stats" in backend["volumes"]
    assert backend["environment"]["FRONTEND_ORIGIN"].startswith("${APP_PUBLIC_URL")
    assert backend["environment"]["SPOTIFY_REDIRECT_URI"].endswith("/api/spotify/auth/callback")
    assert backend["environment"]["SPOTIFY_STATS_RELEASE_SHA"].startswith("${IMAGE_TAG")
    assert all("/app/data" not in volume for volume in services["web"]["volumes"])
    assert all("/app/data" not in volume for volume in services["public-web"]["volumes"])


def test_production_gateways_use_runtime_secret_templates() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text())
    backend = compose["services"]["backend"]

    assert backend["environment"]["SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED"] == (
        "${SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED:-1}"
    )
    assert "SPOTIFY_STATS_GATEWAY_TOKEN" in backend["environment"]

    for service in ("web", "public-web"):
        environment = compose["services"][service]["environment"]
        assert environment["NGINX_ENVSUBST_FILTER"] == "^SPOTIFY_STATS_GATEWAY_TOKEN$"
        assert "SPOTIFY_STATS_GATEWAY_TOKEN" in environment

    private_nginx = (PRODUCTION / "private-nginx.conf.template").read_text()
    public_nginx = (PRODUCTION / "public-nginx.conf.template").read_text()
    for nginx in (private_nginx, public_nginx):
        assert 'X-SpotifyStats-Gateway-Token "${SPOTIFY_STATS_GATEWAY_TOKEN}"' in nginx
        assert "replace-with" not in nginx
    assert "X-SpotifyStats-Surface private-admin" in private_nginx
    assert "X-SpotifyStats-Surface public-readonly" in public_nginx


def test_public_gateway_keeps_defence_in_depth_rules() -> None:
    public_nginx = (PRODUCTION / "public-nginx.conf.template").read_text()

    assert 'X-Robots-Tag "noindex, nofollow, noarchive"' in public_nginx
    assert "client_max_body_size 1m" in public_nginx
    assert "ai-insights" in public_nginx
    assert "versus/(track|album|artist)|release-cycle/compare" in public_nginx
    assert "limit_except GET HEAD OPTIONS {" in public_nginx
    assert "location = /docs" in public_nginx
    assert "location = /openapi.json" in public_nginx


def test_deployment_scripts_manage_modes_without_external_ingress() -> None:
    deploy = (PRODUCTION / "deploy.sh").read_text()
    verify = (PRODUCTION / "verify.sh").read_text()
    rollback = (PRODUCTION / "rollback.sh").read_text()
    switch = (PRODUCTION / "set-deployment-mode.sh").read_text()

    assert "full|showcase|dual" in deploy
    assert "SPOTIFY_STATS_GATEWAY_TOKEN" in deploy
    assert "openssl rand -hex 32" in deploy
    assert "previous-image-tag" in deploy
    assert "previous-deployment-mode" in deploy
    assert 'deploy.sh" "$target_tag" --mode "$target_mode"' in rollback
    assert 'exec "$DEPLOY_DIR/deploy.sh" "$image_tag" --mode "$mode"' in switch
    assert "public-readonly" in deploy
    assert "private-admin" in deploy
    assert "PRAGMA integrity_check" in deploy
    assert "HTTP $write_status，预期 403" in deploy

    for source in (deploy, verify, rollback, switch):
        assert "tailscale " not in source.lower()
        assert " funnel " not in source.lower()


def test_release_restore_and_backup_guardrails_remain() -> None:
    deploy = (PRODUCTION / "deploy.sh").read_text()
    restore = (PRODUCTION / "restore.sh").read_text()
    backup = (PRODUCTION / "backup.sh").read_text()
    tailscale = (PRODUCTION / "configure-tailscale.sh").read_text()
    public_funnel = (PRODUCTION / "configure-public-funnel.sh").read_text()

    assert "backup.sh" in deploy
    assert '"http://127.0.0.1:$port/api/health"' in deploy
    assert "--confirm" in restore
    assert "PRAGMA integrity_check" in restore
    assert "DEPLOYMENT_MODE" in restore
    assert "source.backup(target)" in backup
    assert "tailscale serve --bg" in tailscale
    assert "funnel" not in tailscale.lower()
    assert "tailscale funnel --bg --https=8443" in public_funnel
    assert '"surface":"public-readonly"' in public_funnel
    assert "HTTP $status" in public_funnel

    timer = (PRODUCTION / "install-backup-timer.sh").read_text()
    assert "Persistent=true" in timer
    assert "spotify-stats-backup.timer" in timer


def test_workflow_builds_one_sha_and_uploads_profile_runtime_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text()

    assert "NGINX_CONFIG=deploy/production/nginx.conf" in workflow
    assert "deployment-profile-matrix:" in workflow
    assert "mode: [full, showcase, dual]" in workflow
    assert "private-nginx.conf.template" in workflow
    assert "public-nginx.conf.template" in workflow
    assert "set-deployment-mode.sh" in workflow
    assert "validate-deployment-config.sh" in workflow
    assert "./deploy.sh '${{ github.sha }}'" in workflow
    assert "--mode" not in workflow.split("Deploy commit", 1)[1]


def test_production_environment_template_contains_no_real_secret() -> None:
    template = (PRODUCTION / ".env.example").read_text()

    assert "DEPLOYMENT_MODE=full" in template
    assert "SPOTIFY_STATS_TOKEN_KEY=replace-with" in template
    assert "SPOTIFY_STATS_GATEWAY_TOKEN=replace-with" in template
    assert "SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED=1" in template
    assert re.search(r"SPOTIFY_CLIENT_ID=\s*$", template, re.MULTILINE)
    assert re.search(r"SPOTIFY_CLIENT_SECRET=\s*$", template, re.MULTILINE)
