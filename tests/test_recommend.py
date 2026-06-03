"""Engine tests against the hand-made fixture dataset."""

from __future__ import annotations

import pytest

from jars_lib.constants import GENDER_FEMALE, GENDER_NEUTRAL, IIT_TYPES, NON_IIT_TYPES
from jars_lib.engine import RecoEngine
from jars_lib.fixtures import cutoffs_df, nirf_scores
from jars_lib.match import nirf_lookup
from jars_lib.recommend import feasibility


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


def test_alpha_changes_ordering(engine):
    safe_first = engine.recommend(1500, jee_adv_rank=1500, jee_mains_rank=1500,
                                  seat_type="OPEN", alpha=1.0)
    nirf_first = engine.recommend(1500, jee_adv_rank=1500, jee_mains_rank=1500,
                                  seat_type="OPEN", alpha=0.0)
    assert safe_first and nirf_first
    assert safe_first[0].feasibility >= nirf_first[0].feasibility


def test_alpha_validation(engine):
    with pytest.raises(ValueError):
        engine.recommend(2000, jee_adv_rank=100, alpha=1.5)


def test_nirf_matched_for_known_institutes(lookup):
    assert any("Tiruchirappalli" in name for name in lookup)
    assert any("Karnataka" in name for name in lookup)


def test_engine_facade_end_to_end(engine):
    assert not engine.is_empty
    assert engine.years() == [2025]
    # Both ranks → mixed results, capped
    recs = engine.recommend(5000, jee_adv_rank=200, jee_mains_rank=4000,
                             seat_type="OPEN", alpha=0.5, limit=5)
    assert recs
    assert len(recs) <= 5
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert any(r.nirf_rank is not None for r in recs)
