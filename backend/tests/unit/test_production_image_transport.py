import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "deploy" / "production"
SMOKE_WORKFLOW = ROOT / ".github" / "workflows" / "smoke-production-image-transport.yml"
PRODUCTION_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-production.yml"


def test_smoke_workflow_uses_private_cas_artifact_without_production_mutation() -> None:
    workflow = SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "build_archive_upload:" in workflow
    assert "needs: build_archive_upload" in workflow
    assert "environment: production" in workflow
    assert workflow.count("platforms: linux/amd64") == 2
    assert workflow.count("org.opencontainers.image.revision=${{ github.sha }}") == 2
    assert "spotify-stats-api:transport-${{ github.sha }}" in workflow
    assert "spotify-stats-web:transport-${{ github.sha }}" in workflow
    assert "build-artifact" in workflow
    assert "transport-manifest.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "retention-days: 1" in workflow
    assert "resume_revision:" in workflow
    assert "resume_manifest_sha256:" in workflow
    assert "Verify current production image identity read-only" in workflow
    assert "Optionally recover a digest-bound completed upload into CAS" in workflow
    assert "--manifest-sha256 '$RESUME_MANIFEST_SHA256'" in workflow
    assert "transfer-image-artifact.sh" in workflow
    assert "missing_bytes" in workflow
    assert "transferred_wire_bytes" in workflow
    assert "publish-release-images.sh' '$GITHUB_SHA' smoke" in workflow
    assert "cmp --silent" in workflow
    assert "sudo rmdir --ignore-fail-on-non-empty" in workflow

    for forbidden in (
        "deploy.sh",
        "backup.sh",
        "preflight-music-search.sh",
        "docker compose",
        "docker stop",
        "systemctl stop",
        "rm -rf",
    ):
        assert forbidden not in workflow


def test_shared_transfer_only_sends_deterministic_missing_blob_shards() -> None:
    transfer = (PRODUCTION / "transfer-image-artifact.sh").read_text(encoding="utf-8")

    assert "missing-blobs.$shard.txt" in transfer
    assert "for shard in 0 1 2 3" in transfer
    assert 'pids+=("$!")' in transfer
    assert 'wait "$pid"' in transfer
    assert '--files-from="$list"' in transfer
    assert "--checksum --compress" in transfer
    assert '--partial-dir=".rsync-partial-$shard"' in transfer
    assert "--delay-updates" in transfer
    assert "--checksum" in transfer
    assert "--ignore-existing" not in transfer
    assert "--inplace" not in transfer
    assert "layout/blobs/sha256/[0-9a-f]{64}" in transfer
    assert "transferred_wire_bytes" in transfer
    assert "for tool in rsync docker sha256sum gzip df timeout python3 tar" in transfer
    assert '"$releases_root/locks"' in transfer
    assert '"$releases_root/blobs/sha256"' in transfer
    assert 'revision_dir="$releases_root/incoming/$revision"' in transfer


def test_release_workflow_bootstraps_old_current_then_activates_only_after_deploy() -> None:
    workflow = PRODUCTION_WORKFLOW.read_text(encoding="utf-8")

    assert "build-artifact" in workflow
    assert "--mode release" in workflow
    assert "bootstrap-current-release-images.sh" in workflow
    assert "--allow-registry-only-legacy" in workflow
    assert 'bootstrap_status" -eq 3' in workflow
    assert "seed-verified-smoke-images.sh" not in workflow
    assert "transfer-image-artifact.sh" in workflow
    assert "prepare-local-release-images.sh" in workflow
    assert "publish-release-images.sh' '$GITHUB_SHA' release" in workflow
    assert "./deploy.sh '${{ github.sha }}' --image-source registry" in workflow
    assert "activate-release-images.sh" in workflow
    deploy_job = workflow.split("\n  deploy:\n", 1)[1]
    assert deploy_job.index("Bootstrap current production images") < deploy_job.index(
        "Transfer only missing CAS blobs"
    )
    assert deploy_job.index("Prepare exact registry-style local") < deploy_job.index(
        "Deploy commit"
    )
    assert workflow.index(
        "./deploy.sh '${{ github.sha }}' --image-source registry"
    ) < workflow.index("Activate CAS current and previous retention after successful deploy")
    assert "sudo rmdir --ignore-fail-on-non-empty" in workflow


def test_loader_and_publishers_bind_platform_revision_digest_and_retention() -> None:
    loader = (PRODUCTION / "load-release-images.sh").read_text(encoding="utf-8")
    publisher = (PRODUCTION / "publish-release-images.sh").read_text(encoding="utf-8")
    prepare_local = (PRODUCTION / "prepare-local-release-images.sh").read_text(encoding="utf-8")
    bootstrap = (PRODUCTION / "bootstrap-current-release-images.sh").read_text(encoding="utf-8")

    assert "materialize" in loader
    assert "record-load" in loader
    assert "transport-$REVISION" in loader
    assert "DockerRootDir" in loader
    assert "org.opencontainers.image.revision" in loader
    assert "docker load --input" in loader

    assert "for attempt in 1 2" in publisher
    assert "5m docker push" in publisher
    assert "docker manifest inspect --verbose" in publisher
    assert 'digest_ref="$repository@$manifest_digest"' in publisher
    assert 'docker pull --platform linux/amd64 "$digest_ref"' in publisher
    assert "transport-smoke-$REVISION" in publisher
    assert 'IMAGE_TAG="$REVISION"' in publisher

    assert "docker tag" in prepare_local
    assert "未登录或访问 registry" in prepare_local
    assert "image ID 不同，拒绝覆盖" in prepare_local
    assert "docker image save" in bootstrap
    assert "seed-bootstrap" in bootstrap
    assert "has-current" in bootstrap
    assert "sudo install -d -m 700" in bootstrap
    assert "sudo rmdir --ignore-fail-on-non-empty" in bootstrap
    assert "当前旧镜像缺少 revision label；保留 registry 回滚" in bootstrap
    assert "exit 3" in bootstrap


def test_all_image_transport_shell_scripts_have_valid_syntax_and_reject_bad_input() -> None:
    scripts = (
        "load-release-images.sh",
        "publish-release-images.sh",
        "transfer-image-artifact.sh",
        "prepare-local-release-images.sh",
        "bootstrap-current-release-images.sh",
        "activate-release-images.sh",
    )
    for name in scripts:
        script = PRODUCTION / name
        assert script.stat().st_mode & stat.S_IXUSR
        subprocess.run(["bash", "-n", str(script)], check=True, cwd=ROOT)

    for name in ("load-release-images.sh", "publish-release-images.sh"):
        result = subprocess.run(
            ["bash", str(PRODUCTION / name), "main"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "40-char-git-commit-sha" in result.stderr

    publisher = subprocess.run(
        ["bash", str(PRODUCTION / "publish-release-images.sh"), "a" * 40, "invalid"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert publisher.returncode == 2
    assert "40-char-git-commit-sha" in publisher.stderr
    assert "command not found" not in publisher.stderr
