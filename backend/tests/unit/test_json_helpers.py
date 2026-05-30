"""Unit tests for json_helpers — numpy/pandas type conversion (no DB)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestPyVal:
    def test_none(self):
        from backend.core.json_helpers import py_val

        assert py_val(None) is None

    def test_int(self):
        from backend.core.json_helpers import py_val

        assert py_val(42) == 42
        assert isinstance(py_val(42), int)

    def test_float(self):
        from backend.core.json_helpers import py_val

        assert py_val(3.14) == 3.14

    def test_numpy_int(self):
        import numpy as np

        from backend.core.json_helpers import py_val

        v = py_val(np.int64(42))
        assert v == 42
        assert isinstance(v, int)

    def test_numpy_float(self):
        import numpy as np

        from backend.core.json_helpers import py_val

        v = py_val(np.float64(3.14))
        assert isinstance(v, float)

    def test_nan(self):
        import numpy as np

        from backend.core.json_helpers import py_val

        assert py_val(np.nan) is None
        assert py_val(float("nan")) is None


class TestDfToJson:
    def test_empty(self):
        from backend.core.json_helpers import df_to_json

        assert df_to_json(None) == []

    def test_basic(self):
        import pandas as pd

        from backend.core.json_helpers import df_to_json

        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = df_to_json(df)
        assert len(result) == 2
        assert result[0] == {"a": 1, "b": "x"}
        assert result[1] == {"a": 2, "b": "y"}
