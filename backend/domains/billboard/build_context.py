"""Owned, invocation-local facts for one controlled Billboard publication.

No context or DataFrame is retained by an LRU. Consumers receive independent
copies because legacy builders add columns, including nested record frames.
"""

from __future__ import annotations

from copy import deepcopy


def shared_fact(context, key, builder):
    return builder() if context is None else context.fact(key, builder)


class BillboardBuildContext:
    def __init__(self, filters):
        from backend.domains.billboard.persistent_cache import build_cache_context

        self.filters = dict(filters)
        self.source = build_cache_context("full_data", self.filters)
        self._facts = {}
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            if exc[0] is None:
                self.check_source()  # includes the final snapshot publication
        finally:
            self._facts.clear()
            self._closed = True

    def check_source(self):
        from backend.domains.billboard.persistent_cache import build_cache_context

        if self._closed:
            raise RuntimeError("Billboard build context is closed")
        if build_cache_context("full_data", self.filters) != self.source:
            raise RuntimeError("Billboard source changed during generation")

    def fact(self, key, builder):
        # The Records consumers select identity/peak/weeks/power_score columns;
        # cross-level power enrichment only adds other columns. Both family
        # builders therefore consume the same Records facts. Album total_plays
        # overrides remain local to the power_scores response and never enter
        # this shared base or the full_data/records inputs.
        if self._closed:
            raise RuntimeError("Billboard build context is closed")
        if key not in self._facts:
            self._facts[key] = builder()
        return deepcopy(self._facts[key])

    def compute(self, family, params, cached_builder):
        # Year/output limits do not alter the shared weekly inputs. All other
        # filter fields must belong to this exact generation and DB namespace.
        excluded = {"year", "year_end_top_n", "year_end_album_top_n", "year_end_artist_top_n"}
        expected = {k: v for k, v in self.filters.items() if k in params}
        actual = {k: v for k, v in params.items() if k not in excluded}
        if actual != expected:
            raise ValueError("Billboard build context filter mismatch")
        self.check_source()
        result = cached_builder.__wrapped__(**params, _facts=self)
        self.check_source()  # fail before the existing atomic row writer
        return result

    def load_raw(self, loader, *args, **kwargs):
        # Ranked facts already unify normal Top-N and all annual candidates.
        # Own the fallback input only until ranking consumes it; do not leave
        # full raw/weighted frames in the loader's process-wide legacy LRU.
        if self._closed:
            raise RuntimeError("Billboard build context is closed")
        from backend.domains.playback.logical_timeline import (
            attach_billboard_weighted_frame,
            get_billboard_weighted_frame,
        )

        raw = loader.__wrapped__(*args, **kwargs)
        # Reconstruction and effective artist-credit fan-out have completed.
        # Rank/album consumers need these facts, not interval reconstruction
        # objects copied through every merge and groupby. Preserve row order,
        # independent count/duration weights and all identity/date inputs.
        columns = (
            "billboard_week",
            "track_id",
            "l1_id",
            "representative_track_id",
            "track_name",
            "artist_id",
            "artist_name",
            "album_name",
            "source_album_id",
            "ts",
            "ts_date",
            "ms_played",
            "play_count",
            "total_ms",
        )

        def required_copy(frame):
            result = frame.loc[:, [c for c in columns if c in frame.columns]].copy()
            result.attrs = {}
            return result

        result = required_copy(raw)
        weighted = get_billboard_weighted_frame(raw)
        if weighted is not None:
            attach_billboard_weighted_frame(result, required_copy(weighted))
        return result

    @staticmethod
    def release_raw_inputs(*frames):
        # These owned outputs have finished all duration/album computations.
        # Subsequent consumers need event counts, dates and coverage metadata,
        # not the large immutable raw references inherited through pandas attrs.
        for frame in frames:
            for name in ("billboard_weighted_frame", "listening_duration_frame"):
                frame.attrs.pop(name, None)

    def load_rank(self, params, *, year_end=False):
        from backend.domains.billboard.chart_load_rank import (
            _copy_load_and_rank_result,
            _finish_ranked_facts,
            _load_and_rank_uncached,
        )

        tops = ("bb_top_n", "bb_album_top_n", "bb_artist_top_n")
        base = {k: v for k, v in params.items() if k not in tops}
        key = tuple(sorted(base.items()))
        ranked_key = ("ranked", key)
        if ranked_key not in self._facts:
            self._facts[ranked_key] = _load_and_rank_uncached(
                **base, **dict.fromkeys(tops, 1_000_000), _ranking_only=True, _facts=self
            )
        if year_end:
            # Year-End recomputes its metrics inside each annual window and
            # derives true debut from the entire published Top-N history. It
            # consumes no all-time prefix columns or charting-child counts.
            # Preserve the original entity/week order (including first-row
            # display/cover choices), without building those unused columns.
            def annual_inputs():
                ranked = list(_copy_load_and_rank_result(self._facts[ranked_key]))
                for index, keys in enumerate(
                    (["track_id"], ["artist_name", "album_name"], ["artist_name"])
                ):
                    frame = ranked[index]
                    if not frame.empty:
                        ranked[index] = frame.sort_values(keys + ["billboard_week"]).reset_index(
                            drop=True
                        )
                return tuple(ranked)

            return self.fact(("annual_inputs", key), annual_inputs)
        prefix_key = ("prefix", key, *(params[k] for k in tops))

        def build_prefix():
            ranked = list(_copy_load_and_rank_result(self._facts[ranked_key]))
            for index, name in enumerate(tops):
                frame = ranked[index]
                if "rank" in frame.columns:
                    ranked[index] = frame[frame["rank"] <= params[name]].copy()
            return _finish_ranked_facts(ranked, *(params[k] for k in tops), params["merge_level"])

        return self.fact(prefix_key, build_prefix)
