"""A small, testable model of an ASP.NET WebForms page.

JoSAA's archive is a single ``<form>`` whose dropdowns post back to the server, each
returning a fresh page with updated ViewState and repopulated downstream dropdowns. This
helper captures the current form state (hidden tokens + every ``<select>`` and its
options) and produces the POST payload that emulates "user changed dropdown X".

Keeping this pure (HTML in, dict out) lets us unit-test it against saved fixtures without
touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# ASP.NET's standard hidden fields that must be round-tripped on every postback.
HIDDEN_KEYS = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__EVENTTARGET",
    "__EVENTARGUMENT",
    "__LASTFOCUS",
    "__VIEWSTATEENCRYPTED",
)


@dataclass(slots=True)
class Select:
    name: str
    options: list[tuple[str, str]]  # (value, visible_text)
    selected: str | None


@dataclass(slots=True)
class AspForm:
    """Parsed state of the WebForms page."""

    action: str
    hidden: dict[str, str] = field(default_factory=dict)
    selects: dict[str, Select] = field(default_factory=dict)
    other_inputs: dict[str, str] = field(default_factory=dict)
    buttons: dict[str, str] = field(default_factory=dict)  # name -> default value

    # -- introspection ------------------------------------------------------

    def find_select(self, *keywords: str) -> Select | None:
        """Return the first select whose name contains all ``keywords`` (case-insensitive)."""
        kws = [k.lower() for k in keywords]
        for name, sel in self.selects.items():
            low = name.lower()
            if all(k in low for k in kws):
                return sel
        return None

    def options(self, *keywords: str, skip_placeholder: bool = True) -> list[tuple[str, str]]:
        sel = self.find_select(*keywords)
        if not sel:
            return []
        opts = sel.options
        if skip_placeholder:
            opts = [
                (v, t)
                for v, t in opts
                if v not in ("", "0")
                and "select" not in t.lower()
                and t.strip() not in ("", "--")
            ]
        return opts

    # -- payload construction ----------------------------------------------

    def base_payload(self) -> dict[str, str]:
        """All current field values (hidden + selected option per select + others)."""
        payload: dict[str, str] = {}
        payload.update(self.hidden)
        for name, sel in self.selects.items():
            payload[name] = sel.selected or ""
        payload.update(self.other_inputs)
        return payload

    def postback(self, target_name: str, value: str) -> dict[str, str]:
        """Payload emulating an AutoPostBack: set ``target_name`` to ``value``.

        Sets ``__EVENTTARGET`` to the changed control and applies the new value so the
        server repopulates the dependent dropdowns.
        """
        payload = self.base_payload()
        payload[target_name] = value
        payload["__EVENTTARGET"] = target_name
        payload["__EVENTARGUMENT"] = ""
        return payload

    def submit(self, button_name: str, button_value: str = "Submit") -> dict[str, str]:
        """Payload emulating a button click (no __EVENTTARGET; button name carries value)."""
        payload = self.base_payload()
        payload["__EVENTTARGET"] = ""
        payload["__EVENTARGUMENT"] = ""
        payload[button_name] = button_value
        return payload


def parse_form(html: str) -> AspForm:
    """Parse an ASP.NET page into an :class:`AspForm`."""
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form")
    if form is None:
        raise ValueError("no <form> found on page")

    action = form.get("action") or ""
    hidden: dict[str, str] = {}
    other_inputs: dict[str, str] = {}
    buttons: dict[str, str] = {}

    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        value = inp.get("value", "")
        if name in HIDDEN_KEYS or itype == "hidden":
            hidden[name] = value
        elif itype in ("submit", "button", "image"):
            buttons[name] = value
        elif itype in ("text", "number", "search"):
            other_inputs[name] = value
        # checkboxes/radios are added intentionally at submit time

    # Ensure the core hidden keys exist even if empty.
    for key in ("__EVENTTARGET", "__EVENTARGUMENT"):
        hidden.setdefault(key, "")

    selects: dict[str, Select] = {}
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        options: list[tuple[str, str]] = []
        selected: str | None = None
        for opt in sel.find_all("option"):
            val = opt.get("value", opt.get_text(strip=True))
            text = opt.get_text(strip=True)
            options.append((val, text))
            if opt.has_attr("selected"):
                selected = val
        if selected is None and options:
            selected = options[0][0]
        selects[name] = Select(name=name, options=options, selected=selected)

    return AspForm(
        action=action,
        hidden=hidden,
        selects=selects,
        other_inputs=other_inputs,
        buttons=buttons,
    )
