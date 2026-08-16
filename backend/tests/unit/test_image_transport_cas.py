from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "deploy" / "production" / "image_transport.py"
SPEC = importlib.util.spec_from_file_location("image_transport", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
image_transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image_transport)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_blob(layout: Path, payload: bytes) -> tuple[str, int]:
    digest = hashlib.sha256(payload).hexdigest()
    path = layout / "blobs" / "sha256" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, len(payload)


def _docker_save_archive(
    temporary_path: Path,
    revision: str,
    *,
    api_ref: str | None = None,
    web_ref: str | None = None,
    extra_tag: bool = False,
    divergent_oci_config: bool = False,
    docker_hub_qualified_annotations: bool = False,
) -> Path:
    layout = temporary_path / "source-layout"
    layout.mkdir(parents=True)
    api_ref = api_ref or f"spotify-stats-api:transport-{revision}"
    web_ref = web_ref or f"spotify-stats-web:transport-{revision}"
    shared_layer, shared_size = _write_blob(layout, b"shared-layer")
    entries = []
    descriptors = []
    repositories: dict[str, dict[str, str]] = {}
    for role, image_ref in (("api", api_ref), ("web", web_ref)):
        unique_layer, unique_size = _write_blob(layout, f"{role}-layer-{revision}".encode())
        config = {
            "architecture": "amd64",
            "os": "linux",
            "config": {"Labels": {"org.opencontainers.image.revision": revision}},
            "rootfs": {"type": "layers", "diff_ids": []},
        }
        config_digest, config_size = _write_blob(layout, _canonical(config))
        oci_config_digest = config_digest
        oci_config_size = config_size
        if divergent_oci_config:
            oci_config = {**config, "history": [{"created_by": f"oci-{role}"}]}
            oci_config_digest, oci_config_size = _write_blob(layout, _canonical(oci_config))
        repo_tags = [image_ref]
        if role == "api" and extra_tag:
            repo_tags.append("spotify-stats-api:main")
        entry = {
            "Config": f"blobs/sha256/{config_digest}",
            "RepoTags": repo_tags,
            "Layers": [
                f"blobs/sha256/{shared_layer}",
                f"blobs/sha256/{unique_layer}",
            ],
        }
        entries.append(entry)
        oci_manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": f"sha256:{oci_config_digest}",
                "size": oci_config_size,
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar",
                    "digest": f"sha256:{shared_layer}",
                    "size": shared_size,
                },
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar",
                    "digest": f"sha256:{unique_layer}",
                    "size": unique_size,
                },
            ],
        }
        descriptor_digest, descriptor_size = _write_blob(layout, _canonical(oci_manifest))
        repository, tag = image_ref.rsplit(":", 1)
        repositories[repository] = {tag: unique_layer}
        descriptors.append(
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": f"sha256:{descriptor_digest}",
                "size": descriptor_size,
                "annotations": {
                    "io.containerd.image.name": (
                        f"docker.io/library/{image_ref}"
                        if docker_hub_qualified_annotations and "/" not in image_ref
                        else image_ref
                    ),
                    "org.opencontainers.image.ref.name": tag,
                },
            }
        )
    (layout / "manifest.json").write_bytes(_canonical(entries))
    (layout / "index.json").write_bytes(
        _canonical(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": descriptors,
            }
        )
    )
    (layout / "oci-layout").write_bytes(_canonical({"imageLayoutVersion": "1.0.0"}))
    (layout / "repositories").write_bytes(_canonical(repositories))
    archive = temporary_path / "docker-save.tar"
    with tarfile.open(archive, "w") as output:
        for child in sorted(layout.iterdir(), key=lambda path: path.name):
            output.add(child, arcname=child.name)
    return archive


def _stage_metadata(artifact: Path, staging: Path) -> None:
    (staging / "layout").mkdir(parents=True)
    shutil.copyfile(artifact / "transport-manifest.json", staging / "transport-manifest.json")
    for name in image_transport.LAYOUT_FILES:
        shutil.copyfile(artifact / "layout" / name, staging / "layout" / name)


def _upload_missing(artifact: Path, staging: Path) -> None:
    for relative in (staging / "missing-blobs.txt").read_text().splitlines():
        source = artifact / relative
        target = staging / "upload" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _artifact(tmp_path: Path, revision: str, mode: str = "smoke") -> tuple[Path, str]:
    archive = _docker_save_archive(tmp_path, revision)
    artifact = tmp_path / "artifact"
    image_transport.build_artifact(archive, artifact, revision, mode)
    digest = image_transport.sha256_path(artifact / "transport-manifest.json")
    return artifact, digest


def test_build_artifact_rejects_path_traversal_and_extra_tags(tmp_path: Path) -> None:
    revision = "a" * 40
    traversal = tmp_path / "traversal.tar"
    payload = tmp_path / "payload"
    payload.write_text("unsafe")
    with tarfile.open(traversal, "w") as output:
        output.add(payload, arcname="../unsafe")
    with pytest.raises(image_transport.TransportError, match="不安全路径"):
        image_transport.build_artifact(traversal, tmp_path / "bad-artifact", revision, "smoke")

    archive = _docker_save_archive(tmp_path / "extra", revision, extra_tag=True)
    with pytest.raises(image_transport.TransportError, match="RepoTags"):
        image_transport.build_artifact(archive, tmp_path / "extra-artifact", revision, "smoke")


def test_build_artifact_uses_oci_config_digest_for_loaded_image_identity(
    tmp_path: Path,
) -> None:
    revision = "1" * 40
    archive = _docker_save_archive(tmp_path / "divergent", revision, divergent_oci_config=True)
    artifact = tmp_path / "artifact"
    manifest = image_transport.build_artifact(archive, artifact, revision, "smoke")
    layout = artifact / "layout"
    legacy_entries = json.loads((layout / "manifest.json").read_text())
    legacy_configs = {
        entry["RepoTags"][0]: f"sha256:{Path(entry['Config']).name}" for entry in legacy_entries
    }
    index = json.loads((layout / "index.json").read_text())
    oci_configs = {}
    oci_manifests = {}
    for descriptor in index["manifests"]:
        descriptor_name = descriptor["digest"].removeprefix("sha256:")
        oci_manifest = json.loads((layout / "blobs" / "sha256" / descriptor_name).read_text())
        ref = descriptor["annotations"]["io.containerd.image.name"]
        oci_configs[ref] = oci_manifest["config"]["digest"]
        oci_manifests[ref] = descriptor["digest"]

    for image in manifest["images"]:
        ref = image["archive_ref"]
        assert image["image_id"] == oci_configs[ref]
        assert image["config_digest"] == oci_configs[ref]
        assert image["manifest_digest"] == oci_manifests[ref]
        assert set(image["accepted_image_ids"]) == {
            oci_configs[ref],
            oci_manifests[ref],
        }
        assert image["image_id"] != legacy_configs[ref]


def test_build_artifact_accepts_only_standard_docker_hub_short_name_expansion(
    tmp_path: Path,
) -> None:
    revision = "2" * 40
    archive = _docker_save_archive(
        tmp_path / "qualified", revision, docker_hub_qualified_annotations=True
    )
    manifest = image_transport.build_artifact(archive, tmp_path / "artifact", revision, "smoke")
    assert [image["role"] for image in manifest["images"]] == ["api", "web"]


def test_cas_first_plan_misses_then_second_plan_hits_and_rebuilds_archive(tmp_path: Path) -> None:
    revision = "b" * 40
    artifact, digest = _artifact(tmp_path / "source", revision)
    releases = tmp_path / "releases"
    staging = releases / "incoming" / revision / "smoke"
    _stage_metadata(artifact, staging)

    first = image_transport.plan_transfer(staging, releases, revision, "smoke", digest)
    manifest = json.loads((artifact / "transport-manifest.json").read_text())
    assert first["cache_hits"] == 0
    assert first["missing_count"] == len(manifest["blobs"])
    assert sum(first["shard_bytes"]) == first["missing_bytes"]
    assert len(list(staging.glob("missing-blobs.*.txt"))) == 4
    _upload_missing(artifact, staging)
    image_transport.materialize(staging, releases, revision, "smoke", digest)

    with tarfile.open(staging / "docker-save.tar", "r:") as rebuilt:
        names = set(rebuilt.getnames())
    assert set(image_transport.LAYOUT_FILES).issubset(names)
    assert any(name.startswith("blobs/sha256/") for name in names)
    for record in manifest["blobs"]:
        name = record["digest"].removeprefix("sha256:")
        assert image_transport.sha256_path(releases / "blobs" / "sha256" / name) == name

    second_staging = releases / "incoming" / revision / "release"
    release_manifest = dict(manifest)
    release_manifest["mode"] = "release"
    (second_staging / "layout").mkdir(parents=True)
    (second_staging / "transport-manifest.json").write_bytes(
        image_transport.canonical_json_bytes(release_manifest)
    )
    for name in image_transport.LAYOUT_FILES:
        shutil.copyfile(artifact / "layout" / name, second_staging / "layout" / name)
    release_digest = image_transport.sha256_path(second_staging / "transport-manifest.json")
    second = image_transport.plan_transfer(
        second_staging, releases, revision, "release", release_digest
    )
    assert second["missing_count"] == 0
    assert second["missing_bytes"] == 0


def test_corrupt_cache_and_partial_file_are_never_treated_as_hits(tmp_path: Path) -> None:
    revision = "c" * 40
    artifact, digest = _artifact(tmp_path / "source", revision)
    releases = tmp_path / "releases"
    staging = releases / "incoming" / revision / "smoke"
    _stage_metadata(artifact, staging)
    manifest = json.loads((artifact / "transport-manifest.json").read_text())
    record = manifest["blobs"][0]
    name = record["digest"].removeprefix("sha256:")
    cache = releases / "blobs" / "sha256" / name
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"corrupt")
    partial = staging / "upload" / "layout" / "blobs" / "sha256" / ".rsync-partial-0" / name
    partial.parent.mkdir(parents=True)
    partial.write_bytes((artifact / "layout" / "blobs" / "sha256" / name).read_bytes())

    result = image_transport.plan_transfer(staging, releases, revision, "smoke", digest)
    assert result["missing_count"] == len(manifest["blobs"])
    _upload_missing(artifact, staging)
    image_transport.materialize(staging, releases, revision, "smoke", digest)
    assert image_transport.sha256_path(cache) == name
    assert any((releases / "blobs" / "quarantine").iterdir())


def test_release_activation_keeps_loadable_current_and_previous(tmp_path: Path) -> None:
    releases = tmp_path / "releases"
    activated = []
    for revision in ("d" * 40, "e" * 40):
        artifact, digest = _artifact(tmp_path / revision, revision, "release")
        staging = releases / "incoming" / revision / "release"
        _stage_metadata(artifact, staging)
        image_transport.plan_transfer(staging, releases, revision, "release", digest)
        _upload_missing(artifact, staging)
        manifest = image_transport.materialize(staging, releases, revision, "release", digest)
        id_field = "config_digest" if revision.startswith("d") else "manifest_digest"
        ids = {image["role"]: image[id_field] for image in manifest["images"]}
        if revision.startswith("d"):
            with pytest.raises(image_transport.TransportError, match="不属于 OCI"):
                image_transport.record_load(
                    staging,
                    releases,
                    revision,
                    "release",
                    digest,
                    "sha256:" + "0" * 64,
                    ids["web"],
                )
        image_transport.record_load(
            staging, releases, revision, "release", digest, ids["api"], ids["web"]
        )
        state = image_transport.activate_release(releases, revision, digest)
        activated.append((revision, digest, state))

    state = activated[-1][2]
    assert state["current"]["revision"] == "e" * 40
    assert state["previous"]["revision"] == "d" * 40
    assert Path(state["current"]["archive_path"]).is_file()
    assert Path(state["previous"]["archive_path"]).is_file()
    assert len(list((releases / "records").iterdir())) == 2
