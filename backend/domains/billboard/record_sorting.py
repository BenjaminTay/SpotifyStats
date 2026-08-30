"""Deterministic ordering helpers for Billboard record tables."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from backend.domains.billboard.chart_ranking import _normalised_text_key

SortKey = tuple[str, bool]


def stable_record_sort(
    frame: pd.DataFrame,
    sort_keys: Sequence[SortKey],
    *,
    stable_columns: Sequence[str] = (),
    limit: int | None = None,
) -> pd.DataFrame:
    """Sort a record table by business keys and deterministic entity keys.

    ``sort_keys`` contains ``(column, ascending)`` pairs.  The full candidate
    frame is sorted before ``limit`` is applied, so tied rows at the cutoff do
    not depend on pandas' input order.
    """
    result = frame.copy()
    if result.empty:
        return result.head(limit) if limit is not None else result

    sort_columns: list[str] = []
    ascending: list[bool] = []
    for column, is_ascending in sort_keys:
        if column in result.columns:
            sort_columns.append(column)
            ascending.append(is_ascending)

    temporary_columns: list[str] = []
    for index, column in enumerate(stable_columns):
        if column not in result.columns:
            continue
        series = result[column]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            normalised_column = f"_record_sort_key_{index}"
            original_column = f"_record_sort_original_{index}"
            result[normalised_column] = series.map(_normalised_text_key)
            result[original_column] = series.fillna("").astype(str)
            sort_columns.extend((normalised_column, original_column))
            ascending.extend((True, True))
            temporary_columns.extend((normalised_column, original_column))
        else:
            sort_columns.append(column)
            ascending.append(True)

    if sort_columns:
        result = result.sort_values(
            sort_columns,
            ascending=ascending,
            kind="stable",
            na_position="last",
        )
    if temporary_columns:
        result = result.drop(columns=temporary_columns)
    if limit is not None:
        result = result.head(limit)
    return result.reset_index(drop=True)


def rank_records(
    frame: pd.DataFrame,
    sort_keys: Sequence[SortKey],
    stable_columns: Sequence[str],
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return one deterministic Top 20 record table with optional projection."""
    ranked = stable_record_sort(frame, sort_keys, stable_columns=stable_columns, limit=20)
    return ranked[list(columns)] if columns else ranked
