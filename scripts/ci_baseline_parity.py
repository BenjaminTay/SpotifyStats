from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = ROOT / ".github/workflows/phase5-baseline.yml"
DEFAULT_LOCAL_SCRIPT = ROOT / "scripts/phase5_check.sh"

CHECK_PREFIXES = (
    "pytest ",
    "ruff ",
    "npm test",
    "npm run build",
)

IGNORED_PREFIXES = (
    "python -m pip ",
    "pip install ",
    "npm ci ",
)


def _unique(commands: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    result = []
    for command in commands:
        if command not in seen:
            seen.add(command)
            result.append(command)
    return tuple(result)


def normalize_check_command(command: str) -> Optional[str]:
    command = command.strip()
    if not command or command.startswith("#"):
        return None

    for prefix in (
        "source .venv/bin/activate && ",
        ". .venv/bin/activate && ",
        "cd frontend && ",
    ):
        if command.startswith(prefix):
            command = command[len(prefix) :].strip()

    command = command.replace(".venv/bin/pytest", "pytest")
    command = command.replace(".venv/bin/ruff", "ruff")

    if command in {"cd frontend", "cd \"$ROOT_DIR\""}:
        return None
    if any(command.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return None
    if any(command == prefix.rstrip() or command.startswith(prefix) for prefix in CHECK_PREFIXES):
        return command
    return None


def _extract_workflow_run_lines(workflow_path: Path) -> Tuple[str, ...]:
    lines = workflow_path.read_text(encoding="utf-8").splitlines()
    commands = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped == "run: |":
            block_indent = len(line) - len(line.lstrip())
            index += 1
            while index < len(lines):
                block_line = lines[index]
                if block_line.strip():
                    indent = len(block_line) - len(block_line.lstrip())
                    if indent <= block_indent:
                        break
                    commands.append(block_line.strip())
                index += 1
            continue
        if stripped.startswith("run: ") and stripped != "run: |":
            commands.append(stripped.removeprefix("run: ").strip())
        index += 1
    return tuple(commands)


def get_workflow_check_commands(workflow_path: Path = DEFAULT_WORKFLOW) -> Tuple[str, ...]:
    return _unique(
        command
        for command in (
            normalize_check_command(line) for line in _extract_workflow_run_lines(workflow_path)
        )
        if command is not None
    )


def get_local_check_commands(script_path: Path = DEFAULT_LOCAL_SCRIPT) -> Tuple[str, ...]:
    lines = script_path.read_text(encoding="utf-8").splitlines()
    return _unique(
        command
        for command in (normalize_check_command(line) for line in lines)
        if command is not None
    )


def get_missing_local_commands(
    workflow_commands: Sequence[str], local_commands: Sequence[str]
) -> Tuple[str, ...]:
    local_command_set = set(local_commands)
    return tuple(command for command in workflow_commands if command not in local_command_set)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify local Phase 5 checks cover GitHub Actions baseline commands."
    )
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--local-script", type=Path, default=DEFAULT_LOCAL_SCRIPT)
    args = parser.parse_args()

    workflow_commands = get_workflow_check_commands(args.workflow)
    local_commands = get_local_check_commands(args.local_script)
    missing = get_missing_local_commands(workflow_commands, local_commands)

    print("Workflow checks:")
    for command in workflow_commands:
        print(f"- {command}")
    print("Local checks:")
    for command in local_commands:
        print(f"- {command}")

    if missing:
        print("Missing local checks:")
        for command in missing:
            print(f"- {command}")
        return 1

    print("Local Phase 5 script covers GitHub Actions baseline checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
