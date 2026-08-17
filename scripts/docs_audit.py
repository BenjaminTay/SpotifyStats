#!/usr/bin/env python3
"""只读检查项目文档链接、入口同步和当前目录中的旧路径。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HTML_SRC_RE = re.compile(r"<(?:img|source)\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
STALE_PATHS = (
    "docs/playback-stats/",
    "docs/productization/",
    "docs/verification/",
    "docs/superpowers/",
    "docs/archive/06-productization/",
)
REQUIRED_ENTRIES = (
    "reports/README.md",
    "archive/README.md",
    "reference/artist-language-statistics.md",
    "archive/06-productization-closeout/",
)
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "dist", ".pytest_cache"}
ROOT_PATH_PREFIXES = ("backend/", "data/", "deploy/", "docs/", "frontend/", "scripts/")
INLINE_DOC_PATH_PREFIXES = ("docs/",)
ROOT_FILES = {"README.md", "AGENTS.md", "CLAUDE.md", "LICENSE"}
TRAILING_PATH_PUNCTUATION = ".,;:!?)]}，。；：！？）》」』"


def markdown_files(include_archive: bool) -> list[Path]:
    files = []
    for path in ROOT.rglob("*.md"):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if not include_archive and "archive" in path.relative_to(ROOT).parts:
            continue
        files.append(path)
    return sorted(files)


def _iter_document_lines(path: Path):
    in_fence = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line_number, line


def _is_external_target(target: str) -> bool:
    return not target or target.startswith(("#", "data:", "mailto:")) or "://" in target


def _resolve_target(path: Path, target: str) -> Path:
    target = target.strip("<>").split("#", 1)[0].split("?", 1)[0]
    if target.startswith("/"):
        return ROOT / target.lstrip("/")
    if target.startswith(ROOT_PATH_PREFIXES) or target in ROOT_FILES:
        return ROOT / target
    return path.parent / target


def check_links(files: list[Path]) -> list[str]:
    issues = []
    for path in files:
        relative = path.relative_to(ROOT)
        for line_number, line in _iter_document_lines(path):
            for raw_target in LINK_RE.findall(line):
                if _is_external_target(raw_target):
                    continue
                resolved = _resolve_target(path, raw_target).resolve()
                if not resolved.exists():
                    issues.append(f"{relative}:{line_number}: broken local link -> {raw_target}")
    return issues


def check_html_sources(files: list[Path]) -> list[str]:
    issues = []
    for path in files:
        relative = path.relative_to(ROOT)
        for line_number, line in _iter_document_lines(path):
            for raw_target in HTML_SRC_RE.findall(line):
                if _is_external_target(raw_target):
                    continue
                resolved = _resolve_target(path, raw_target).resolve()
                if not resolved.exists():
                    issues.append(f"{relative}:{line_number}: broken local HTML source -> {raw_target}")
    return issues


def check_inline_paths(files: list[Path]) -> list[str]:
    issues = []
    for path in files:
        relative = path.relative_to(ROOT)
        for line_number, line in _iter_document_lines(path):
            for raw_value in INLINE_CODE_RE.findall(line):
                value = raw_value.strip().split()[0].rstrip(TRAILING_PATH_PUNCTUATION)
                if not value.startswith(INLINE_DOC_PATH_PREFIXES) and value not in ROOT_FILES:
                    continue
                resolved = _resolve_target(path, value).resolve()
                if not resolved.exists():
                    issues.append(f"{relative}:{line_number}: broken inline local path -> {value}")
    return issues


def check_stale_paths(files: list[Path]) -> list[str]:
    issues = []
    for path in files:
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for stale in STALE_PATHS:
            if stale in text:
                issues.append(f"{relative}: stale path -> {stale}")
    return issues


def check_guidance_parity() -> list[str]:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    if agents != claude:
        return ["AGENTS.md and CLAUDE.md are not byte-identical"]
    return []


def check_doc_map() -> list[str]:
    path = ROOT / "docs/README.md"
    text = path.read_text(encoding="utf-8")
    return [f"docs/README.md: missing required entry -> {entry}" for entry in REQUIRED_ENTRIES if entry not in text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="同时检查历史归档中的链接；默认只检查当前文档入口",
    )
    args = parser.parse_args()

    files = markdown_files(args.include_archive)
    current_files = [path for path in files if "archive" not in path.relative_to(ROOT).parts]
    issues = []
    issues.extend(check_links(files))
    issues.extend(check_html_sources(files))
    issues.extend(check_stale_paths(current_files))
    issues.extend(check_inline_paths(current_files))
    issues.extend(check_guidance_parity())
    issues.extend(check_doc_map())

    scope = "全部 Markdown" if args.include_archive else "当前 Markdown（不含 archive）"
    print(f"文档文件：{len(files)} ({scope})")
    print(f"检查结果：{'PASS' if not issues else 'FAIL'}")
    for issue in issues:
        print(f"- {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
