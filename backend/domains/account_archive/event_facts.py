"""Compact, invocation-owned event facts shared by the three relationship chapters."""

from __future__ import annotations

from functools import cached_property

from backend.domains.account_archive import source_data


class ArchiveEventFacts:
    def __init__(self, conn, context):
        self.conn = conn
        self.context = context

    def check(self, context):
        if context.filter_fingerprint != self.context.filter_fingerprint:
            raise ValueError("Archive event facts filter mismatch")

    @cached_property
    def frame(self):
        raw = source_data.load_effective_archive_plays(self.conn, self.context)
        result = raw.loc[:, ["archive_track_id", "event_at"]].copy()
        result.attrs = {}
        return result

    @cached_property
    def times(self):
        return {
            int(track_id): sorted(group["event_at"].tolist())
            for track_id, group in self.frame.groupby("archive_track_id", sort=False)
        }

    @cached_property
    def saved(self):
        return source_data.load_saved_track_entities(self.conn, self.context)
