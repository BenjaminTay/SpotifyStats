from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("timezone", ["UTC", "Asia/Shanghai"])
def test_scoped_lifetime_bounds_use_playback_timezone(timezone: str) -> None:
    # Isolate the host timezone: changing TZ in the test runner would also
    # affect unrelated background threads and other SQLite connections.
    script = """
import json,sqlite3,time
from backend.services.entity_stats_service import _global_period_bounds
time.tzset()
c=sqlite3.connect(':memory:')
c.execute('CREATE TABLE plays(ts TEXT,track_id INTEGER)')
c.executemany('INSERT INTO plays VALUES (?,?)',[
 ('2026-10-17T20:00:00Z',1),('2026-10-18T20:07:10Z',1),
 ('2026-10-20T20:00:00Z',None)])
def bounds(**kwargs):
 return _global_period_bounds(c,period='lifetime',start_date=None,end_date=None,**kwargs)
result={'music':bounds(music_only=True),'all':bounds(music_only=False)}
result['custom']=_global_period_bounds(c,period='custom',start_date='2026-09-01',end_date='2026-09-30',music_only=True)
c.execute('DELETE FROM plays')
result['empty']=bounds(music_only=True)
print(json.dumps(result))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={**os.environ, "TZ": timezone},
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    assert (actual["music"]["start_date"], actual["music"]["end_date"]) == (
        "2026-10-18",
        "2026-10-19",
    )
    assert (actual["all"]["start_date"], actual["all"]["end_date"]) == (
        "2026-10-18",
        "2026-10-21",
    )
    assert actual["custom"]["start_date"] == "2026-09-01"
    assert actual["custom"]["end_date"] == "2026-09-30"
    assert actual["empty"]["start_date"] is None
    assert actual["empty"]["end_date"] is None
