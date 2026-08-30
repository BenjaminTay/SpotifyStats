"""Shared sequence calculations for Billboard record families."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def consecutive_chart_streaks(
    frame: pd.DataFrame,
    *,
    group_columns: Sequence[str],
    identity_columns: Sequence[str],
) -> pd.DataFrame:
    """Return each entity's longest run of adjacent Billboard weeks."""
    rows: list[dict[str, object]] = []
    sort_columns = [*group_columns, "billboard_week"]
    group_key: str | list[str]
    group_key = group_columns[0] if len(group_columns) == 1 else list(group_columns)
    for _, group in frame.sort_values(sort_columns).groupby(group_key):
        weeks = group["billboard_week"].tolist()
        max_run = current_run = 1
        run_start = run_end = weeks[0]
        best_start = best_end = weeks[0]
        for index in range(1, len(weeks)):
            if (weeks[index] - weeks[index - 1]).days <= 8:
                current_run += 1
                run_end = weeks[index]
                continue
            if current_run > max_run:
                max_run = current_run
                best_start, best_end = run_start, run_end
            current_run = 1
            run_start = run_end = weeks[index]
        if current_run > max_run:
            max_run = current_run
            best_start, best_end = run_start, run_end
        rows.append(
            {
                **{column: group.iloc[0][column] for column in identity_columns},
                "连续周数": max_run,
                "起始周": best_start,
                "结束周": best_end,
            }
        )
    return pd.DataFrame(rows)
