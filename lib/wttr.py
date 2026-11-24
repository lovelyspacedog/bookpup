"""wttr.in one-line weather for US ZIP codes."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

from .metadata_search import user_agent

_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")

_WWO_EMOJI: dict[str, str] = {
    "113": "☀️",
    "116": "⛅",
    "119": "☁️",
    "122": "☁️",
    "143": "🌫️",
    "176": "🌦️",
    "179": "🌨️",
    "182": "🌧️",
    "185": "🌧️",
    "200": "⛈️",
    "227": "🌨️",
    "230": "🌨️",
    "248": "🌫️",
    "260": "🌫️",
    "263": "🌦️",
    "266": "🌧️",
    "281": "🌧️",
    "284": "🌧️",
    "293": "🌦️",
    "296": "🌧️",
    "299": "🌧️",
    "302": "🌧️",
    "305": "🌧️",
    "308": "🌧️",
    "311": "🌧️",
    "314": "🌧️",
    "317": "🌧️",
    "320": "🌨️",
    "323": "🌨️",
    "326": "🌨️",
    "329": "❄️",
    "332": "❄️",
    "335": "❄️",
    "338": "❄️",
    "350": "🌨️",
    "353": "🌦️",
    "356": "🌧️",
    "359": "🌧️",
    "362": "🌨️",
    "365": "🌧️",
    "368": "🌨️",
    "371": "❄️",
    "374": "🌨️",
    "377": "🌨️",
    "386": "⛈️",
    "389": "⛈️",
    "392": "⛈️",
    "395": "❄️",
}

Unit = Literal["F", "C"]


def normalize_us_zip(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if not _ZIP_RE.match(s):
        return None
    return s[:5]


def _wwo_emoji(code: object) -> str:
    return _WWO_EMOJI.get(str(code or "").strip(), "🌡️")


def _temp_sign(temp: str) -> str:
    return "" if temp.startswith("-") else "+"


def format_forecast_line(city: str, emoji: str, temp: str, unit: Unit) -> str:
    line = f"{city}: {emoji}  {_temp_sign(temp)}{temp}°{unit}"
    if len(line) > 120:
        line = line[:117].rstrip() + "…"
    return line


def forecast_from_j1(payload: dict[str, Any]) -> dict[str, str]:
    areas = payload.get("nearest_area") or []
    if not areas:
        raise ValueError("no nearest_area")
    names = areas[0].get("areaName") or []
    if not names:
        raise ValueError("no areaName")
    city = str(names[0].get("value") or "").strip()
    if not city:
        raise ValueError("empty city")

    conditions = payload.get("current_condition") or []
    if not conditions:
        raise ValueError("no current_condition")
    cc = conditions[0]
    temp_f = str(cc.get("temp_F") or "").strip()
    temp_c = str(cc.get("temp_C") or "").strip()
    if not temp_f or not temp_c:
        raise ValueError("no temp")
    emoji = _wwo_emoji(cc.get("weatherCode"))
    return {
        "city": city,
        "emoji": emoji,
        "temp_f": temp_f,
        "temp_c": temp_c,
        "line": format_forecast_line(city, emoji, temp_f, "F"),
    }


def line_from_j1(payload: dict[str, Any]) -> tuple[str, str]:
    data = forecast_from_j1(payload)
    return data["city"], data["line"]


def fetch_wttr_forecast(zip5: str) -> dict[str, str]:
    loc = urllib.parse.quote(zip5, safe="")
    url = f"https://wttr.in/{loc}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=12) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("invalid wttr payload")
    return forecast_from_j1(payload)


def fetch_wttr_line(zip5: str) -> tuple[str, str]:
    data = fetch_wttr_forecast(zip5)
    return data["city"], data["line"]