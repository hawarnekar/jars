"""Parser tests for the scrapers (no network — operate on inline HTML fixtures)."""

from __future__ import annotations

import httpx
import pytest

from jars_lib.constants import shorten_institute_name, shorten_program_name
from jars_lib.scrape.aspform import parse_form
from jars_lib.scrape.errors import ScrapeError
from jars_lib.scrape.josaa import JosaaClient, parse_result_table
from jars_lib.scrape.nirf import parse_nirf_table


def test_shorten_institute_name():
    assert shorten_institute_name("Indian Institute of Technology Bombay") == "IIT Bombay"
    assert (
        shorten_institute_name("National Institute of Technology Tiruchirappalli")
        == "NIT Tiruchirappalli"
    )
    assert (
        shorten_institute_name("Indian Institute of Information Technology, Allahabad")
        == "IIIT, Allahabad"
    )
    assert (
        shorten_institute_name("Malaviya National Institute of Technology Jaipur")
        == "Malaviya NIT Jaipur"
    )
    # IIIT must not be mangled by the IIT rule, and already-short names are unchanged.
    assert shorten_institute_name("IIT Madras") == "IIT Madras"
    # Unrelated institutes are left alone.
    assert shorten_institute_name("Anna University") == "Anna University"


def test_shorten_program_name():
    assert (
        shorten_program_name("Computer Science and Engineering (4 Years, Bachelor of Technology)")
        == "Computer Science and Engineering (4 Years, B.Tech.)"
    )
    assert (
        shorten_program_name("Physics (4 Years, Bachelor of Science)")
        == "Physics (4 Years, B.S.)"
    )
    # Tech dual-degree / integrated phrasings -> "B.Tech. + M.Tech." (note nested parens).
    assert (
        shorten_program_name("Civil Engineering (5 Years, Bachelor and Master of Technology (Dual Degree))")
        == "Civil Engineering (5 Years, B.Tech. + M.Tech.)"
    )
    assert (
        shorten_program_name("Mechanical (5 Years, Integrated Master of Technology)")
        == "Mechanical (5 Years, B.Tech. + M.Tech.)"
    )
    # Science dual-degree / integrated phrasings -> "B.S. + M.S.".
    assert (
        shorten_program_name("Chemistry (5 Years, Bachelor of Science and Master of Science (Dual Degree))")
        == "Chemistry (5 Years, B.S. + M.S.)"
    )
    assert (
        shorten_program_name("Chemistry (5 Years, Integrated Bachelor of Science-Master of Science)")
        == "Chemistry (5 Years, B.S. + M.S.)"
    )
    # MBA dual-degree phrasings keep the MBA but drop the "(Dual Degree)" wrapper.
    assert (
        shorten_program_name("Chemistry (5 Years, Bachelor of Science and MBA (Dual Degree))")
        == "Chemistry (5 Years, B.S. and MBA)"
    )
    assert (
        shorten_program_name("Mechanical (5 Years, Bachelor of Technology and MBA (Dual Degree))")
        == "Mechanical (5 Years, B.Tech. and MBA)"
    )
    # Pre-abbreviated B.Tech.+M.Tech./MS variant: tidy the MS and drop "(Dual Degree)".
    assert (
        shorten_program_name("EE (5 Years, B.Tech. + M.Tech./MS (Dual Degree))")
        == "EE (5 Years, B.Tech. + M.Tech./M.S.)"
    )
    # Blanket "Master of Science" -> "M.S." also reaches standalone/integrated forms.
    assert (
        shorten_program_name("Maths (5 Years, Integrated Master of Science)")
        == "Maths (5 Years, Integrated M.S.)"
    )
    # Already-short and unrelated descriptors are untouched.
    assert shorten_program_name("CSE (4 Years, B.Tech.)") == "CSE (4 Years, B.Tech.)"
    assert (
        shorten_program_name("Architecture (5 Years, Bachelor of Architecture)")
        == "Architecture (5 Years, Bachelor of Architecture)"
    )

ASP_HTML = """
<html><body>
<form method="post" action="page.aspx">
  <input type="hidden" name="__VIEWSTATE" value="abc123" />
  <input type="hidden" name="__EVENTVALIDATION" value="ev456" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="GEN" />
  <select name="ctl00$cph$ddlYear">
    <option value="">Select</option>
    <option value="2025" selected>2025</option>
    <option value="2024">2024</option>
  </select>
  <select name="ctl00$cph$ddlRoundNo">
    <option value="">Select</option>
    <option value="6">6</option>
  </select>
  <select name="ctl00$cph$ddlInstype">
    <option value="">Select</option>
    <option value="IIT">IIT</option>
    <option value="ALL">ALL</option>
  </select>
  <input type="submit" name="ctl00$cph$btnSubmit" value="Submit" />
</form>
</body></html>
"""

RESULT_HTML = """
<table>
  <tr><th>Institute</th><th>Academic Program Name</th><th>Quota</th>
      <th>Seat Type</th><th>Gender</th><th>Opening Rank</th><th>Closing Rank</th></tr>
  <tr><td>Indian Institute of Technology Bombay</td>
      <td>Computer Science and Engineering (4 Years, Bachelor of Technology)</td>
      <td>AI</td><td>OPEN</td><td>Gender-Neutral</td><td>1</td><td>67</td></tr>
  <tr><td>Indian Institute of Technology Delhi</td>
      <td>Mathematics and Computing (4 Years, Bachelor of Technology)</td>
      <td>AI</td><td>OPEN</td><td>Female-only (including Supernumerary)</td>
      <td>150</td><td>380P</td></tr>
</table>
"""

NIRF_HTML = """
<table>
  <tr><th>Institute ID</th><th>Name</th><th>City</th><th>State</th><th>Score</th><th>Rank</th></tr>
  <tr><td>IR-E-U-0456</td><td>Indian Institute of Technology Madras</td>
      <td>Chennai</td><td>Tamil Nadu</td><td>89.46</td><td>1</td></tr>
  <tr><td>IR-E-U-0306</td><td>Indian Institute of Technology Delhi</td>
      <td>New Delhi</td><td>Delhi</td><td>86.66</td><td>2</td></tr>
</table>
"""

# Mirrors the live page: a 6-column header but data rows carry extra hidden
# "More Details" cells (so Score/Rank are NOT at the header's column positions), plus
# interleaved detail sub-rows that must be skipped.
NIRF_REALISTIC_HTML = """
<table>
  <tr><th>Institute ID</th><th>Name</th><th>City</th><th>State</th><th>Score</th><th>Rank</th></tr>
  <tr>
    <td>IR-E-U-0456</td>
    <td>Indian Institute of Technology Madras More Details Close | | TLR (100)</td>
    <td>TLR (100)</td><td>RPC (100)</td><td>GO (100)</td><td>OI (100)</td><td>PERCEPTION (100)</td>
    <td>95.79</td><td>93.10</td><td>81.07</td><td>65.85</td><td>100.00</td>
    <td>Chennai</td><td>Tamil Nadu</td><td>89.46</td><td>1</td>
  </tr>
  <tr><td>TLR (100)</td><td>RPC (100)</td><td>GO (100)</td><td>OI (100)</td><td>PERCEPTION (100)</td></tr>
  <tr><td>95.79</td><td>93.10</td><td>81.07</td><td>65.85</td><td>100.00</td></tr>
  <tr>
    <td>IR-E-U-0306</td>
    <td>Indian Institute of Technology Delhi More Details Close | |</td>
    <td>TLR (100)</td><td>RPC (100)</td><td>GO (100)</td><td>OI (100)</td><td>PERCEPTION (100)</td>
    <td>90.00</td><td>88.00</td><td>80.00</td><td>60.00</td><td>95.00</td>
    <td>New Delhi</td><td>Delhi</td><td>86.66</td><td>2</td>
  </tr>
</table>
"""


def test_parse_form_extracts_hidden_and_selects():
    form = parse_form(ASP_HTML)
    assert form.hidden["__VIEWSTATE"] == "abc123"
    assert form.hidden["__EVENTVALIDATION"] == "ev456"
    assert form.find_select("year").selected == "2025"
    assert "ctl00$cph$btnSubmit" in form.buttons


def test_postback_payload_sets_event_target():
    form = parse_form(ASP_HTML)
    year_name = form.find_select("year").name
    payload = form.postback(year_name, "2024")
    assert payload["__EVENTTARGET"] == year_name
    assert payload[year_name] == "2024"
    assert payload["__VIEWSTATE"] == "abc123"


def test_options_skips_placeholder():
    form = parse_form(ASP_HTML)
    years = [v for v, _ in form.options("year")]
    assert "2025" in years and "" not in years


def test_parse_result_table():
    rows = parse_result_table(RESULT_HTML, year=2025, round=6, institute_type="IIT")
    assert len(rows) == 2
    first = rows[0]
    assert first["institute_name"].endswith("Bombay")
    assert first["closing_rank"] == 67
    assert first["seat_type"] == "OPEN"
    # 'P' (preparatory) suffix is stripped to the numeric rank.
    assert rows[1]["closing_rank"] == 380


def test_parse_nirf_table():
    scores = parse_nirf_table(NIRF_HTML, year=2024)
    assert len(scores) == 2
    assert scores[0].institute_name == "Indian Institute of Technology Madras"
    assert scores[0].nirf_score == 89.46
    assert scores[0].nirf_rank == 1


def test_parse_nirf_table_with_more_details_columns():
    # The real page's extra hidden cells must not shift Score/Rank, and the detail
    # sub-rows must be skipped.
    scores = parse_nirf_table(NIRF_REALISTIC_HTML, year=2024)
    assert len(scores) == 2
    assert scores[0].institute_name == "Indian Institute of Technology Madras"
    assert scores[0].nirf_score == 89.46
    assert scores[0].nirf_rank == 1
    assert scores[1].institute_name == "Indian Institute of Technology Delhi"
    assert scores[1].nirf_rank == 2


# --- error handling: the archive redirecting postbacks to its error page ----------


def test_check_error_detects_aspnet_error_redirect_via_final_url():
    req = httpx.Request(
        "GET", "https://josaa.admissions.nic.in/applicant/ErrMsg.aspx?aspxerrorpath=/x"
    )
    resp = httpx.Response(200, text="<html>Error Message</html>", request=req)
    with pytest.raises(ScrapeError, match="ErrMsg"):
        JosaaClient._check_error(resp, context="submitting a form postback")


def test_check_error_detects_redirect_in_history():
    redirect = httpx.Request("POST", "https://josaa.admissions.nic.in/x.aspx")
    hist = httpx.Response(
        302,
        headers={"location": "/applicant/ErrMsg.aspx?aspxerrorpath=/x.aspx"},
        request=redirect,
    )
    final = httpx.Request("GET", "https://josaa.admissions.nic.in/clean.aspx")
    resp = httpx.Response(200, text="<html><form></form></html>", request=final, history=[hist])
    with pytest.raises(ScrapeError):
        JosaaClient._check_error(resp, context="submitting a form postback")


def test_check_error_passes_for_normal_form_page():
    req = httpx.Request("POST", "https://josaa.admissions.nic.in/x.aspx")
    resp = httpx.Response(200, text=ASP_HTML, request=req)
    # Should not raise for a normal page containing a form.
    JosaaClient._check_error(resp, context="ok")


def test_parse_wraps_missing_form_as_scrapeerror():
    req = httpx.Request("GET", "https://josaa.admissions.nic.in/x.aspx")
    resp = httpx.Response(200, text="<html><body>no form here</body></html>", request=req)
    with pytest.raises(ScrapeError, match="no form"):
        JosaaClient._parse(resp)
