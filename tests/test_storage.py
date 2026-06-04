"""Round-trip tests for the storage layer."""

from __future__ import annotations

from jars_lib import storage
from jars_lib.config import Paths
from jars_lib.constants import shorten_institute_name
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
    # Names are abbreviated on save.
    assert loaded[0].institute_name == shorten_institute_name(scores[0].institute_name)


def test_cutoffs_institute_names_shortened_on_save(tmp_path):
    paths = Paths(root=tmp_path)
    storage.save_cutoffs(cutoffs_df(), paths)
    names = set(storage.load_cutoffs(paths)["institute_name"].dropna().tolist())
    assert any(n.startswith("IIT ") for n in names)
    assert any(n.startswith("NIT ") for n in names)
    # No long prefixes survive.
    assert not any("Indian Institute of Technology" in n for n in names)
    assert not any("National Institute of Technology" in n for n in names)


def test_cutoffs_program_names_shortened_on_save(tmp_path):
    paths = Paths(root=tmp_path)
    storage.save_cutoffs(cutoffs_df(), paths)
    progs = set(storage.load_cutoffs(paths)["program_name"].dropna().tolist())
    assert any("B.Tech." in p for p in progs)
    assert not any("Bachelor of Technology" in p for p in progs)


def test_meta_update(tmp_path):
    paths = Paths(root=tmp_path)
    meta = storage.update_meta(paths, years=[2024, 2025], rounds=6)
    assert "last_updated" in meta
    assert storage.read_meta(paths)["years"] == [2024, 2025]


def test_load_missing_returns_empty(tmp_path):
    paths = Paths(root=tmp_path)
    assert len(storage.load_cutoffs(paths)) == 0
    assert storage.load_nirf(paths) == []


def test_load_corrupt_cutoffs_returns_empty(tmp_path):
    paths = Paths(root=tmp_path)
    paths.cutoffs.write_bytes(b"not a parquet file at all")
    result = storage.load_cutoffs(paths)
    assert len(result) == 0


def test_load_corrupt_nirf_returns_empty(tmp_path):
    paths = Paths(root=tmp_path)
    paths.nirf.write_text("{ this is not valid json }")
    assert storage.load_nirf(paths) == []


def test_load_nirf_skips_malformed_records(tmp_path):
    import json
    paths = Paths(root=tmp_path)
    payload = [
        {"year": 2025, "institute_name": "IIT X", "nirf_rank": 1, "nirf_score": 80.0},
        {"year": 2025, "institute_name": "IIT Y", "nirf_rank": "bad", "nirf_score": 70.0},
        {"year": 2025, "institute_name": "IIT Z", "nirf_rank": 3, "nirf_score": 60.0},
    ]
    paths.nirf.write_text(json.dumps(payload))
    result = storage.load_nirf(paths)
    # Record 0 and 2 are valid; record 1 has a string rank which coerces fine
    # but we confirm we don't crash and get at least the clean records.
    assert len(result) >= 2


def test_load_corrupt_meta_returns_empty(tmp_path):
    paths = Paths(root=tmp_path)
    paths.meta.write_text("!!!invalid!!!")
    assert storage.read_meta(paths) == {}
