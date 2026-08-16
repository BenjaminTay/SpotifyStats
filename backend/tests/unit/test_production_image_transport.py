import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "smoke-production-image-transport.yml"
PRODUCTION_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-production.yml"
LOAD = ROOT / "deploy" / "production" / "load-release-images.sh"
PUBLISH = ROOT / "deploy" / "production" / "publish-release-images.sh"


def test_smoke_workflow_is_manual_bounded_and_non_production() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    production_workflow = PRODUCTION_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "build_archive_upload:" in workflow
    assert "transfer:" in workflow
    assert "needs: build_archive_upload" in workflow
    assert "timeout-minutes: 30" in workflow
    assert "timeout-minutes: 35" in workflow
    assert "environment: production" in workflow
    assert workflow.count("platforms: linux/amd64") == 2
    assert workflow.count("org.opencontainers.image.revision=${{ github.sha }}") == 2
    assert "docker image save" in workflow
    assert "gzip -1" in workflow
    assert "retention-days: 1" in workflow
    assert "compression-level: 0" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert workflow.index("actions/upload-artifact@v4") < workflow.index(
        "actions/download-artifact@v4"
    )
    assert "rsync --archive --partial --append-verify" in workflow
    assert "/opt/spotify-stats/releases/incoming/$revision" in workflow
    assert "/opt/spotify-stats/releases/incoming/$GITHUB_SHA" not in workflow
    assert "LOCAL_API_IMAGE: spotify-stats-api:transport-smoke-${{ github.sha }}" in workflow
    assert "LOCAL_WEB_IMAGE: spotify-stats-web:transport-smoke-${{ github.sha }}" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "Archive bytes" in workflow
    assert "Build job total" in workflow
    assert "Transfer job total" in workflow
    assert "for tool in rsync docker sha256sum gzip df timeout" in workflow
    assert workflow.index("for tool in rsync docker sha256sum gzip df timeout") < workflow.index(
        "sudo install -d"
    )
    assert "docker ps --no-trunc --format '{{.ID}}\\t{{.Image}}\\t{{.Names}}'" in workflow
    assert "live-containers.before" in workflow
    assert "live-containers.after" in workflow
    assert "cmp --silent" in workflow
    assert 'find "$staging_dir" -depth -mindepth 1 -delete' in workflow
    assert 'rmdir -- "$staging_dir"' in workflow
    assert "rm -rf" not in workflow

    forbidden = (
        "deploy.sh",
        "backup.sh",
        "preflight-music-search.sh",
        "docker compose",
        "docker stop",
        "systemctl stop",
    )
    for command in forbidden:
        assert command not in workflow

    for bootstrap_path in (
        ".github/workflows/deploy-production.yml",
        ".github/workflows/smoke-production-image-transport.yml",
        "deploy/production/load-release-images.sh",
        "deploy/production/publish-release-images.sh",
        "backend/tests/unit/test_production_image_transport.py",
    ):
        assert f'- "{bootstrap_path}"' in production_workflow


def test_loader_locks_archive_integrity_capacity_platform_and_revision() -> None:
    loader = LOAD.read_text(encoding="utf-8")

    assert 'RELEASES_ROOT="/opt/spotify-stats/releases/incoming"' in loader
    assert "spotify-stats-images-$REVISION.tar.gz" in loader
    assert "sha256sum" in loader
    assert "archive_bytes" in loader
    assert "DockerRootDir" in loader
    assert "gzip --test" in loader
    assert "docker load" in loader
    assert "linux" in loader and "amd64" in loader
    assert "org.opencontainers.image.revision" in loader
    assert "transport-smoke-$REVISION" in loader
    assert ':$REVISION"' not in loader
    assert "rm -f" not in loader


def test_publisher_only_uses_smoke_tags_and_verifies_tcr_round_trip() -> None:
    publisher = PUBLISH.read_text(encoding="utf-8")

    assert 'SMOKE_TAG="transport-smoke-$REVISION"' in publisher
    assert "docker push" in publisher
    assert "timeout --signal=TERM --kill-after=30s 5m docker push" in publisher
    assert "for attempt in 1 2" in publisher
    assert "attempt $attempt/2" in publisher
    assert "attempt $attempt/3" not in publisher
    assert "docker manifest inspect" in publisher
    assert "docker pull --platform linux/amd64" in publisher
    assert "org.opencontainers.image.revision" in publisher
    assert "linux/amd64" in publisher
    assert 'image_ref" == *":main"' in publisher
    assert 'image_ref" == *":latest"' in publisher
    assert "deploy.sh" not in publisher
    assert "docker compose" not in publisher
    assert "docker stop" not in publisher


def test_transport_scripts_have_valid_bash_syntax_and_reject_bad_revision() -> None:
    for script in (LOAD, PUBLISH):
        subprocess.run(["bash", "-n", str(script)], check=True, cwd=ROOT)
        result = subprocess.run(
            ["bash", str(script), "main"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "40-char-git-commit-sha" in result.stderr
