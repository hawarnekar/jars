"""Round-trip tests for the storage layer."""

from __future__ import annotations

from jars_lib import storage
from jars_lib.config import Paths
from jars_lib.fixtures import cutoffs_df, nirf_scores


def test_cutoffs_round_trip(tmp_path):
    paths = Paths(root=tmp_path)
    df = cutoffs_df()
    storage.save_cutoffs(df, paths)
    loaded = storage.load_cutoffs(paths)
    assert len(loaded) == len(df)
    assert list(loaded.columns) == list(df.columns)
    # Ranks survive as nullable integers.
    assert int(loaded["closing_rank"].iloc[0]) == int(df["closing_rank"].iloc[0])


def test_nirf_round_trip(tmp_path):
    paths = Paths(root=tmp_path)
    scores = nirf_scores()
    storage.save_nirf(scores, paths)
    loaded = storage.load_nirf(paths)
    assert len(loaded) == len(scores)
    assert loaded[0].institute_name == scores[0].institute_name


def test_meta_update(tmp_path):
    paths = Paths(root=tmp_path)
    meta = storage.update_meta(paths, years=[2024, 2025], rounds=6)
    assert "last_updated" in meta
    assert storage.read_meta(paths)["years"] == [2024, 2025]


def test_load_missing_returns_empty(tmp_path):
    paths = Paths(root=tmp_path)
    assert len(storage.load_cutoffs(paths)) == 0
    assert storage.load_nirf(paths) == []
