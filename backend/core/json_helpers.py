"""Shared JSON serialization helpers for converting numpy/pandas types to native Python."""

import numpy as np
import pandas as pd


def py_val(v):
    """Convert a single numpy/pandas scalar to a JSON-safe Python native type."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, float) and np.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (ValueError, TypeError):
        pass
    return v


def df_to_json(df, date_cols=None):
    """Convert DataFrame to list of dicts with native Python types.

    Args:
        df: pandas DataFrame (or None / empty-able)
        date_cols: list of column names whose values should be ISO-formatted
    """
    if df is None:
        return []
    if hasattr(df, 'empty') and df.empty:
        return []
    date_cols = date_cols or []
    records = []
    for _, row in df.iterrows():
        d = {}
        for k, v in row.items():
            if k in date_cols and hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
            else:
                d[k] = py_val(v)
        records.append(d)
    return records
