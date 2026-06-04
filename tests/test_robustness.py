"""Tests for the robustness fixes: data-dir resolution, retry/backoff, NIRF error
translation, the no-guess button rule, and per-round meta counts."""

from __future__ import annotations

import httpx
import pytest

from jars_lib import config, storage
from jars_lib.config import Paths
from jars_lib.fixtures import cutoffs_df
from jars_lib.scrape import retry as retry_mod
from jars_lib.scrape.aspform import parse_form
from jars_lib.scrape.errors import ScrapeError
from jars_lib.scrape.josaa import JosaaClient
from jars_lib.scrape.nirf import scrape_nirf
from jars_lib.update import _round_counts, seed_demo


# --------------------------------------------------------------------- 1.5 data_dir


def test_data_dir_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_DATA_DIR, str(tmp_path))
    assert config.data_dir() == tmp_path


def test_data_dir_prefers_source_tree_when_present(monkeypatch):
    monkeypatch.delenv(config.ENV_DATA_DIR, raising=False)
    # The checkout ships a data/ dir, so it should win over the per-user fallback.
    assert config.PROJECT_DATA_DIR.exists()
    assert config.data_dir() == config.PROJECT_DATA_DIR


def test_data_dir_falls_back_to_user_dir_when_source_absent(monkeypatch, tmp_path):
    monkeypatch.delenv(config.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(config, "PROJECT_DATA_DIR", tmp_path / "does-not-exist")
    result = config.data_dir()
    # Whatever platformdirs (or the XDG fallback) returns, it is a writable per-user
    # location scoped to "jars" — never the missing source path.
    assert result != tmp_path / "does-not-exist"
    assert "jars" in str(result).lower()


# ---------------------------------------------------------------------- 1.6 retry


def _no_sleep(monkeypatch):
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)


def test_with_retry_succeeds_after_transient_failures(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("transient")
        return "ok"

    assert retry_mod.with_retry(flaky, attempts=3, base_delay=0) == "ok"
    assert calls["n"] == 3


def test_with_retry_does_not_retry_non_transient(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        retry_mod.with_retry(boom, attempts=3, base_delay=0)
    assert calls["n"] == 1  # failed fast, no retries


def test_with_retry_gives_up_and_reraises_after_attempts(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def always():
        calls["n"] += 1
        raise httpx.ReadTimeout("still down")

    with pytest.raises(httpx.ReadTimeout):
        retry_mod.with_retry(always, attempts=3, base_delay=0)
    assert calls["n"] == 3


def test_with_retry_retries_5xx_but_not_404(monkeypatch):
    _no_sleep(monkeypatch)
    assert retry_mod.is_transient_http(
        httpx.HTTPStatusError(
            "x", request=httpx.Request("GET", "http://x"),
            response=httpx.Response(503),
        )
    )
    assert not retry_mod.is_transient_http(
        httpx.HTTPStatusError(
            "x", request=httpx.Request("GET", "http://x"),
            response=httpx.Response(404),
        )
    )


# ------------------------------------------------------------------- 2.5 NIRF 404


def test_scrape_nirf_404_becomes_scrapeerror(httpx_mock):
    httpx_mock.add_response(status_code=404)
    with pytest.raises(ScrapeError, match="404"):
        scrape_nirf(1999)


def test_scrape_nirf_transport_error_becomes_scrapeerror(httpx_mock, monkeypatch):
    _no_sleep(monkeypatch)  # don't actually back off during the test
    # A transport error is transient, so with_retry tries 3 times before giving up.
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("no route"))
    with pytest.raises(ScrapeError, match="reach NIRF"):
        scrape_nirf(2024)


# ------------------------------------------------------------------ 1.8 no-guess button

_NO_KEYWORD_BUTTON_HTML = """
<form method="post" action="x.aspx">
  <input type="hidden" name="__VIEWSTATE" value="x" />
  <select name="ddlYear"><option value="2025">2025</option></select>
  <input type="submit" name="ctl00$cph$someUnrelatedControl" value="Go" />
</form>
"""

_KEYWORD_BUTTON_HTML = _NO_KEYWORD_BUTTON_HTML.replace(
    "someUnrelatedControl", "btnSubmit"
)


def test_find_button_returns_none_without_keyword_match():
    form = parse_form(_NO_KEYWORD_BUTTON_HTML)
    # No fallback to "first button" — an unidentifiable button means skip the leaf.
    assert JosaaClient._find_button(form) is None


def test_find_button_matches_on_keyword():
    form = parse_form(_KEYWORD_BUTTON_HTML)
    assert JosaaClient._find_button(form) == "ctl00$cph$btnSubmit"


# ----------------------------------------------------------------- 1.7 round counts


def test_round_counts_from_fixture():
    df = cutoffs_df()
    counts = _round_counts(df)
    # The demo fixture is a single (year, round): 2025 round 6.
    assert "2025/6" in counts
    assert counts["2025/6"] == len(df)


def test_round_counts_empty_frame():
    assert _round_counts(storage.empty_cutoffs()) == {}


def test_seed_demo_records_round_counts(tmp_path):
    paths = Paths(root=tmp_path)
    seed_demo(paths)
    meta = storage.read_meta(paths)
    assert meta.get("round_counts")  # non-empty dict persisted
