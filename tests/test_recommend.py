"""Engine tests against the hand-made fixture dataset."""

from __future__ import annotations

import pytest

from jars_lib.constants import CUTOFF_COLUMNS, GENDER_FEMALE, GENDER_NEUTRAL, NON_IIT_TYPES
from jars_lib.engine import RecoEngine
from jars_lib.fixtures import cutoffs_df, nirf_scores
from jars_lib.match import nirf_lookup
from jars_lib.recommend import (
    _W_CLOSING,
    _W_NIRF,
    _W_OPENING,
    _closing_trend,
    feasibility,
    recommend as recommend_fn,
)


@pytest.fixture
def df():
    return cutoffs_df()


@pytest.fixture
def lookup(df):
    return nirf_lookup(df["institute_name"].tolist(), nirf_scores())


@pytest.fixture
def engine(df):
    return RecoEngine(cutoffs=df, nirf=nirf_scores())


# --------------------------------------------------------------------------- feasibility

def test_feasibility_monotonic_and_bounded():
    assert 0.0 <= feasibility(100, 1000) <= 1.0
    assert feasibility(100, 1000) > feasibility(100, 200)
    assert feasibility(1000, 100) < 0.5   # reach
    assert feasibility(50, 100) > 0.5     # safe
    assert feasibility(100, None) == 0.0


# --------------------------------------------------------------------------- engine dual-rank API

def test_adv_rank_only_returns_iit(engine):
    recs = engine.recommend(500, jee_adv_rank=200)
    assert recs
    assert all(r.cutoff.institute_type == "IIT" for r in recs)


def test_mains_rank_only_returns_non_iit(engine):
    recs = engine.recommend(5000, jee_mains_rank=4000)
    assert recs
    assert all(r.cutoff.institute_type != "IIT" for r in recs)


def test_both_ranks_returns_mixed(engine):
    recs = engine.recommend(5000, jee_adv_rank=500, jee_mains_rank=4000)
    types = {r.cutoff.institute_type for r in recs}
    assert "IIT" in types
    # At least one non-IIT type present
    assert types & NON_IIT_TYPES


def test_both_ranks_sorted_by_score(engine):
    recs = engine.recommend(5000, jee_adv_rank=500, jee_mains_rank=4000)
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_neither_rank_raises(engine):
    with pytest.raises(ValueError, match="at least one"):
        engine.recommend(2000)


def test_window_filters_by_closing_rank(engine):
    recs = engine.recommend(100, jee_adv_rank=250)
    assert recs
    for r in recs:
        assert 150 <= r.cutoff.closing_rank <= 350


def test_seat_type_filter(engine):
    recs = engine.recommend(500, jee_adv_rank=300, seat_type="OBC-NCL")
    assert recs
    assert all(r.cutoff.seat_type == "OBC-NCL" for r in recs)


def test_gender_pool(engine):
    female = engine.recommend(50, jee_adv_rank=290, seat_type="OPEN", gender=GENDER_FEMALE)
    neutral = engine.recommend(50, jee_adv_rank=290, seat_type="OPEN", gender=GENDER_NEUTRAL)
    assert any(r.cutoff.gender == GENDER_FEMALE for r in female)
    assert all(r.cutoff.gender == GENDER_NEUTRAL for r in neutral)


def test_home_state_quota_visibility(engine):
    without = engine.recommend(6000, jee_mains_rank=4000, seat_type="OPEN")
    with_hs = engine.recommend(6000, jee_mains_rank=4000, seat_type="OPEN", home_state="Rajasthan")
    assert all(r.cutoff.quota != "HS" for r in without)
    assert any(r.cutoff.quota == "HS" for r in with_hs)


def test_institute_type_filter_restricts(engine):
    recs = engine.recommend(3000, jee_mains_rank=3000, seat_type="OPEN", institute_types={"NIT"})
    assert recs
    assert all(r.cutoff.institute_type == "NIT" for r in recs)


def test_institute_type_filter_iit_with_mains_rank_returns_empty(engine):
    # Asking for IITs but only providing Mains rank → engine intersects IIT_TYPES ∩ {IIT}
    # but no Mains rank call is made for IITs, so result is empty.
    recs = engine.recommend(3000, jee_mains_rank=3000, seat_type="OPEN", institute_types={"IIT"})
    assert recs == []


def test_institute_type_filter_non_iit_with_adv_rank_returns_empty(engine):
    # Asking for NITs but only providing Advanced rank → empty.
    recs = engine.recommend(500, jee_adv_rank=200, seat_type="OPEN", institute_types={"NIT"})
    assert recs == []


def test_nirf_matched_for_known_institutes(lookup):
    assert any("Tiruchirappalli" in name for name in lookup)
    assert any("Karnataka" in name for name in lookup)


def test_in_range_years_and_open_close_restricted():
    """A year counts only when the rank is within that year's open..close band, and
    Open/Close summarise just those years."""
    import pandas as pd

    from jars_lib.constants import CUTOFF_COLUMNS

    rows = [
        # year, round, type, institute, program, quota, seat, gender, open, close
        (2025, 6, "NIT", "NIT X", "CSE", "OS", "OPEN", GENDER_NEUTRAL, 900, 2100),
        (2024, 6, "NIT", "NIT X", "CSE", "OS", "OPEN", GENDER_NEUTRAL, 800, 2600),
        (2023, 6, "NIT", "NIT X", "CSE", "OS", "OPEN", GENDER_NEUTRAL, 3000, 5200),
    ]
    df = pd.DataFrame([dict(zip(CUTOFF_COLUMNS, r)) for r in rows], columns=list(CUTOFF_COLUMNS))
    eng = RecoEngine(cutoffs=df, nirf=[])

    # rank 2500, window ±1000 → [1500, 3500] selects the program (2025 close 2100 in window).
    recs = eng.recommend(1000, jee_mains_rank=2500)
    assert len(recs) == 1
    r = recs[0]
    # 2025: 2500 > 2100 (no). 2024: 800 ≤ 2500 ≤ 2600 (yes). 2023: 2500 < 3000 (no).
    assert r.in_range_years == [2024]
    assert (r.opening_rank_min, r.opening_rank_min_year) == (800, 2024)
    assert (r.closing_rank_max, r.closing_rank_max_year) == (2600, 2024)
    # With an in-range year, the displayed band reflects it.
    assert r.band_in_range is True
    assert r.band_years == [2024]


def test_reach_shows_window_year_band_when_no_in_range_year():
    """A program selected via the +/- window but never in-range falls back to showing the
    window year's opening/closing (instead of blank), so a low chance is explainable."""
    rows = [
        # rank 5115 is worse than every year's closing -> never in range, but 2022 closed
        # within +/-100, so it's selected as a reach.
        (2025, 6, "IIT", "Inst A", "P", "AI", "OPEN", GENDER_NEUTRAL, 3000, 4800),
        (2022, 6, "IIT", "Inst A", "P", "AI", "OPEN", GENDER_NEUTRAL, 4222, 5075),
    ]
    recs = recommend_fn(5115, 100, data=_make_df(rows), nirf_by_institute={"Inst A": (1, 90.0)})
    assert len(recs) == 1
    r = recs[0]
    assert r.in_range_years == []          # never cleared the cutoff
    assert r.window_years == [2022]        # but closed within the window in 2022
    assert r.band_in_range is False
    assert r.band_years == [2022]
    assert (r.opening_rank_min, r.opening_rank_min_year) == (4222, 2022)
    assert (r.closing_rank_max, r.closing_rank_max_year) == (5075, 2022)


def test_fmt_years_reach_marker():
    from jars_lib.cli import _fmt_years
    assert _fmt_years([2022]) == "2022"
    assert _fmt_years([2022], reach=True) == "~2022"
    assert _fmt_years([2023, 2022], reach=True) == "~(2023, 2022)"
    assert _fmt_years([]) == "-"


def test_engine_facade_end_to_end(engine):
    assert not engine.is_empty
    assert engine.years() == [2025]
    # Both ranks → mixed results, capped
    recs = engine.recommend(5000, jee_adv_rank=200, jee_mains_rank=4000,
                            seat_type="OPEN", limit=5)
    assert recs
    assert len(recs) <= 5
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert any(r.nirf_rank is not None for r in recs)


# ----------------------------------------------- ranking: weighted score (NIRF, close, open)

def _make_df(rows):
    """Build a cutoffs frame from tuples in CUTOFF_COLUMNS order."""
    import pandas as pd

    return pd.DataFrame(
        [dict(zip(CUTOFF_COLUMNS, r)) for r in rows], columns=list(CUTOFF_COLUMNS)
    )


def test_score_weights_are_in_priority_order():
    # The requirement: NIRF weighted most, then closing, then opening; weights normalise.
    assert _W_NIRF > _W_CLOSING > _W_OPENING
    assert abs((_W_NIRF + _W_CLOSING + _W_OPENING) - 1.0) < 1e-9


def test_score_nirf_dominates_when_closing_and_opening_equal():
    # Closing/opening identical → the better NIRF rank gives the higher score.
    rows = [
        (2025, 6, "IIT", "Inst A", "P", "AI", "OPEN", GENDER_NEUTRAL, 500, 1000),
        (2025, 6, "IIT", "Inst B", "P", "AI", "OPEN", GENDER_NEUTRAL, 500, 1000),
    ]
    recs = recommend_fn(
        1000, 1500, data=_make_df(rows),
        nirf_by_institute={"Inst A": (1, 90.0), "Inst B": (50, 70.0)},
    )
    assert [r.cutoff.institute_name for r in recs] == ["Inst A", "Inst B"]
    assert recs[0].score > recs[1].score


def test_score_lower_closing_wins_when_nirf_equal():
    rows = [
        (2025, 6, "IIT", "Inst A", "P_hi", "AI", "OPEN", GENDER_NEUTRAL, 100, 2000),
        (2025, 6, "IIT", "Inst A", "P_lo", "AI", "OPEN", GENDER_NEUTRAL, 100, 1000),
    ]
    recs = recommend_fn(
        1500, 1500, data=_make_df(rows), nirf_by_institute={"Inst A": (1, 90.0)}
    )
    assert [r.cutoff.program_name for r in recs] == ["P_lo", "P_hi"]


def test_score_lower_opening_wins_when_nirf_and_closing_equal():
    rows = [
        (2025, 6, "IIT", "Inst A", "P_hiopen", "AI", "OPEN", GENDER_NEUTRAL, 800, 1000),
        (2025, 6, "IIT", "Inst A", "P_loopen", "AI", "OPEN", GENDER_NEUTRAL, 200, 1000),
    ]
    recs = recommend_fn(
        1000, 1000, data=_make_df(rows), nirf_by_institute={"Inst A": (1, 90.0)}
    )
    assert [r.cutoff.program_name for r in recs] == ["P_loopen", "P_hiopen"]


def test_score_large_closing_advantage_outweighs_small_nirf_gap():
    # The key difference from a strict priority: a big closing-rank advantage can beat a
    # one-place-worse NIRF rank, because the score is a *weighted blend*, not lexicographic.
    rows = [
        (2025, 6, "IIT", "Inst A", "P", "AI", "OPEN", GENDER_NEUTRAL, 500, 2000),
        (2025, 6, "IIT", "Inst B", "P", "AI", "OPEN", GENDER_NEUTRAL, 500, 1000),
    ]
    recs = recommend_fn(
        1500, 1500, data=_make_df(rows),
        nirf_by_institute={"Inst A": (1, 90.0), "Inst B": (3, 88.0)},
    )
    # Inst B has a slightly worse NIRF rank (3 vs 1) but a much lower closing rank → wins.
    assert recs[0].cutoff.institute_name == "Inst B"


def test_score_weights_recent_years_more():
    # P has a low closing rank recently (2025) and a high one in 2023; Q is the reverse.
    # Recency weighting makes P's recent low dominate, so P scores higher.
    rows = [
        (2025, 6, "NIT", "Inst A", "P_recent_lo", "OS", "OPEN", GENDER_NEUTRAL, 100, 1000),
        (2023, 6, "NIT", "Inst A", "P_recent_lo", "OS", "OPEN", GENDER_NEUTRAL, 100, 5000),
        (2025, 6, "NIT", "Inst A", "Q_recent_hi", "OS", "OPEN", GENDER_NEUTRAL, 100, 5000),
        (2023, 6, "NIT", "Inst A", "Q_recent_hi", "OS", "OPEN", GENDER_NEUTRAL, 100, 1000),
    ]
    recs = recommend_fn(
        3000, 2500, data=_make_df(rows), nirf_by_institute={"Inst A": (1, 90.0)}
    )
    names = [r.cutoff.program_name for r in recs]
    assert names.index("P_recent_lo") < names.index("Q_recent_hi")


def test_score_well_ranked_institute_beats_unranked():
    # A strongly NIRF-ranked institute outscores an unranked one even with a much lower
    # closing rank, because the dominant NIRF weight outruns the closing/opening terms.
    rows = [
        (2025, 6, "GFTI", "Ranked", "P", "AI", "OPEN", GENDER_NEUTRAL, 1500, 2000),
        (2025, 6, "GFTI", "Unranked", "P", "AI", "OPEN", GENDER_NEUTRAL, 100, 500),
    ]
    recs = recommend_fn(
        1500, 1500, data=_make_df(rows), nirf_by_institute={"Ranked": (5, 70.0)}
    )
    assert [r.cutoff.institute_name for r in recs] == ["Ranked", "Unranked"]
    assert recs[1].score == pytest.approx(_W_CLOSING + _W_OPENING)  # unranked: g_nirf = 0


# --------------------------------------------- 1.2 feasibility extreme-input (§5 gap)

def test_feasibility_extreme_inputs_no_overflow():
    assert 0.0 <= feasibility(10**9, 1) <= 1.0      # huge rank vs tiny cutoff
    assert feasibility(10**9, 1) < 0.5              # definitely a reach
    assert feasibility(1, 10**9) > 0.99             # tiny rank vs huge cutoff → near-certain

# ---------------------------------------------------------- 4.4 closing-rank trend

def test_closing_trend_single_year_returns_stable():
    rows = [(2025, 6, None, 5000)]
    assert _closing_trend(rows) == "stable"


def test_closing_trend_easing():
    # Closing rank rising year-on-year → program becoming more accessible.
    rows = [(2025, 6, None, 6000), (2024, 6, None, 5000), (2023, 6, None, 4000)]
    assert _closing_trend(rows) == "easing"


def test_closing_trend_tighter():
    # Closing rank falling year-on-year → program getting more competitive.
    rows = [(2025, 6, None, 4000), (2024, 6, None, 5000), (2023, 6, None, 6000)]
    assert _closing_trend(rows) == "tighter"


def test_closing_trend_stable():
    # Near-flat change < 3%/yr → stable.
    rows = [(2025, 6, None, 5000), (2024, 6, None, 5050), (2023, 6, None, 5020)]
    assert _closing_trend(rows) == "stable"


def test_trend_propagated_to_recommendation():
    rows = [
        (2025, 6, "NIT", "Inst A", "P", "OS", "OPEN", GENDER_NEUTRAL, 100, 4000),
        (2024, 6, "NIT", "Inst A", "P", "OS", "OPEN", GENDER_NEUTRAL, 100, 5000),
        (2023, 6, "NIT", "Inst A", "P", "OS", "OPEN", GENDER_NEUTRAL, 100, 6000),
    ]
    recs = recommend_fn(4500, 1000, data=_make_df(rows))
    assert len(recs) == 1
    assert recs[0].closing_rank_trend == "tighter"  # 4000 < 5000 < 6000: tightening


# --------------------------------------------------- 3.1 name-map cache (storage + engine)

def test_name_map_round_trip(tmp_path):
    from jars_lib import storage
    from jars_lib.config import Paths

    paths = Paths(root=tmp_path)
    lookup = {"IIT Bombay": (3, 83.0), "NIT Trichy": (9, 66.0)}
    storage.save_name_map(lookup, paths)
    loaded = storage.load_name_map(paths)
    assert loaded == lookup


def test_name_map_absent_returns_none(tmp_path):
    from jars_lib import storage
    from jars_lib.config import Paths

    assert storage.load_name_map(Paths(root=tmp_path)) is None


def test_name_map_corrupt_returns_none(tmp_path):
    from jars_lib import storage
    from jars_lib.config import Paths

    paths = Paths(root=tmp_path)
    paths.name_map.write_text("not json")
    assert storage.load_name_map(paths) is None


def test_load_data_uses_cached_name_map(tmp_path):
    from jars_lib import storage
    from jars_lib.config import Paths
    from jars_lib.engine import load_data
    from jars_lib.fixtures import cutoffs_df, nirf_scores as nirf_scores_fn

    paths = Paths(root=tmp_path)
    storage.save_cutoffs(cutoffs_df(), paths)
    storage.save_nirf(nirf_scores_fn(), paths)
    # Pre-build and cache the lookup.
    from jars_lib.match import nirf_lookup
    df = storage.load_cutoffs(paths)
    names = df["institute_name"].dropna().astype(str).tolist()
    lookup = nirf_lookup(names, storage.load_nirf(paths))
    storage.save_name_map(lookup, paths)

    eng = load_data(paths)
    # Engine should have used the cached map without recomputing.
    assert eng._nirf_lookup == lookup


def test_seed_demo_creates_name_map(tmp_path):
    from jars_lib import storage
    from jars_lib.config import Paths
    from jars_lib.update import seed_demo

    paths = Paths(root=tmp_path)
    seed_demo(paths)
    assert storage.load_name_map(paths) is not None


# ---------------------------------------------------------------- 1.1 empty-scrape guard

def test_empty_scrape_guard_raises(tmp_path):
    """update_database refuses to overwrite an existing store with 0 new rows."""
    import unittest.mock as mock
    from jars_lib import storage
    from jars_lib.config import Paths
    from jars_lib.fixtures import cutoffs_df, nirf_scores
    from jars_lib.scrape.errors import ScrapeError
    from jars_lib.update import update_database

    paths = Paths(root=tmp_path)
    storage.save_cutoffs(cutoffs_df(), paths)
    storage.save_nirf(nirf_scores(), paths)

    import pandas as pd
    from jars_lib.constants import CUTOFF_COLUMNS
    empty_df = pd.DataFrame(columns=list(CUTOFF_COLUMNS))

    with mock.patch("jars_lib.update._scrape_cutoffs", return_value=empty_df):
        with pytest.raises(ScrapeError, match="0 rows"):
            update_database(paths=paths)


def test_empty_scrape_force_allows_overwrite(tmp_path):
    """--force bypasses the empty-scrape guard."""
    import unittest.mock as mock
    from jars_lib import storage
    from jars_lib.config import Paths
    from jars_lib.fixtures import cutoffs_df, nirf_scores
    from jars_lib.update import update_database

    import pandas as pd
    from jars_lib.constants import CUTOFF_COLUMNS
    empty_df = pd.DataFrame(columns=list(CUTOFF_COLUMNS))

    paths = Paths(root=tmp_path)
    storage.save_cutoffs(cutoffs_df(), paths)
    storage.save_nirf(nirf_scores(), paths)

    with mock.patch("jars_lib.update._scrape_cutoffs", return_value=empty_df):
        with mock.patch("jars_lib.update.scrape_nirf", return_value=[]):
            update_database(paths=paths, force=True)

    assert len(storage.load_cutoffs(paths)) == 0


# ---------------------------------------------------------------- 2.1 CLI error handling

def test_cli_bad_category_exits_2(tmp_path, monkeypatch):
    monkeypatch.setenv("JARS_DATA_DIR", str(tmp_path))
    from jars_lib.cli import main
    from jars_lib.update import seed_demo
    from jars_lib.config import Paths
    seed_demo(Paths(root=tmp_path))
    assert main(["recommend", "--mains-rank", "25000", "--category", "INVALID"]) == 2


def test_cli_scrape_error_exits_1(tmp_path, monkeypatch):
    import unittest.mock as mock
    monkeypatch.setenv("JARS_DATA_DIR", str(tmp_path))
    from jars_lib.cli import main
    from jars_lib.scrape.errors import ScrapeError
    with mock.patch("jars_lib.cli.update_database", side_effect=ScrapeError("boom")):
        assert main(["update"]) == 1


def test_cli_keyboard_interrupt_exits_130(tmp_path, monkeypatch):
    import unittest.mock as mock
    monkeypatch.setenv("JARS_DATA_DIR", str(tmp_path))
    from jars_lib.cli import main
    with mock.patch("jars_lib.cli.update_database", side_effect=KeyboardInterrupt):
        assert main(["update"]) == 130
