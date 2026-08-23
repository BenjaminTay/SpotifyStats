"""Resolve a proven import relationship into a safe Phase B action."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.domains.imports.incremental import ImportPlan, ImportRelation


class ImportExecutionAction(str, Enum):
    """Phase B actions; derived maintenance remains full for every write."""

    NOOP = "noop"
    APPEND = "append"
    REPLACE = "replace"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ImportExecutionDecision:
    action: ImportExecutionAction
    message: str

    @property
    def writes_playback(self) -> bool:
        return self.action in {
            ImportExecutionAction.APPEND,
            ImportExecutionAction.REPLACE,
        }


def resolve_import_execution(
    plan: ImportPlan,
    *,
    requested_mode: str = "auto",
    confirm_plan: bool = False,
) -> ImportExecutionDecision:
    """Choose only actions whose safety is proven by Phase B evidence.

    Explicit ``replace`` may resolve a risky relationship after confirmation.
    Explicit ``append`` never weakens the account/baseline/tail proof: Phase B
    does not use a confirmation checkbox as permission to guess.
    """

    if requested_mode not in {"auto", "append", "replace"}:
        raise ValueError(f"unsupported import mode: {requested_mode}")

    relation = plan.relation

    if requested_mode == "replace":
        if plan.requires_confirmation and not confirm_plan:
            return ImportExecutionDecision(
                ImportExecutionAction.NEEDS_CONFIRMATION,
                "完整替换需要确认当前输入关系和数据库快照边界",
            )
        return ImportExecutionDecision(
            ImportExecutionAction.REPLACE,
            "按明确选择执行完整替换并建立新的指纹基线",
        )

    if relation is ImportRelation.IDENTICAL:
        return ImportExecutionDecision(
            ImportExecutionAction.NOOP,
            "输入与活动数据集完全相同，无需写入或重建派生数据",
        )

    if relation in {ImportRelation.SNAPSHOT_SUPERSET, ImportRelation.DELTA_TAIL}:
        return ImportExecutionDecision(
            ImportExecutionAction.APPEND,
            "只追加已证明不存在于活动数据集的新播放记录",
        )

    if requested_mode == "append":
        if relation is ImportRelation.BASELINE_REQUIRED:
            message = "当前数据库没有完整指纹基线，必须先执行完整替换"
        elif relation is ImportRelation.DIFFERENT_ACCOUNT:
            message = "账号身份不同，Phase B 禁止追加到当前数据库"
        else:
            message = "Phase B 不能证明该输入适合安全追加，请使用完整替换或补齐证据"
        return ImportExecutionDecision(ImportExecutionAction.BLOCKED, message)

    if relation is ImportRelation.BASELINE_REQUIRED:
        if plan.existing_count > 0 and not confirm_plan:
            return ImportExecutionDecision(
                ImportExecutionAction.NEEDS_CONFIRMATION,
                "旧库尚无指纹基线，无法证明输入包覆盖全部历史；完整替换前需要确认",
            )
        return ImportExecutionDecision(
            ImportExecutionAction.REPLACE,
            "旧库需要一次完整导入建立源记录指纹基线",
        )

    return ImportExecutionDecision(
        ImportExecutionAction.NEEDS_CONFIRMATION,
        "自动模式无法安全判定追加或替换，请明确选择完整替换",
    )
