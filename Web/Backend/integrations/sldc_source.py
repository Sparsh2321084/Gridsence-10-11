import re
from datetime import datetime
from html.parser import HTMLParser
from math import isfinite
from typing import TypedDict
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

SLDC_REALTIME_URL = "https://www.delhisldc.org/Redirect.aspx?Loc=0804"
IST = ZoneInfo("Asia/Kolkata")
ENTITY_ROWS = {
    "BRPL": "brpl_mw",
    "BYPL": "bypl_mw",
    "TPDDL": "tpddl_mw",
    "NDMC": "ndmc_mw",
    "MES": "mes_mw",
    "RAILWAY": "railways_mw",
    "TOTAL": "delhi_total_mw",
}
SNAPSHOT_TIME_PATTERN = re.compile(
    r"\bDISCOM\s+DRAWL\s*\(?\s*(\d{1,2}:\d{2}:\d{2})\s*HRS",
    re.IGNORECASE,
)


class SLDCSnapshot(TypedDict):
    timestamp: pd.Timestamp
    brpl_mw: float
    bypl_mw: float
    tpddl_mw: float
    ndmc_mw: float
    mes_mw: float
    railways_mw: float
    delhi_total_mw: float


class _PageTables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _normalized(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _snapshot_timestamp(page_time: str, now: datetime | pd.Timestamp | None) -> pd.Timestamp:
    current = pd.Timestamp(now or datetime.now(IST))
    if current.tzinfo is None:
        current = current.tz_localize(IST)
    else:
        current = current.tz_convert(IST)

    parsed_time = datetime.strptime(page_time, "%H:%M:%S").time()
    sample = pd.Timestamp(datetime.combine(current.date(), parsed_time)).tz_localize(IST)
    if sample - current > pd.Timedelta(hours=12):
        sample -= pd.Timedelta(days=1)
    elif current - sample > pd.Timedelta(hours=12):
        sample += pd.Timedelta(days=1)
    return sample.floor("15min")


def parse_sldc_snapshot(
    html: str,
    now: datetime | pd.Timestamp | None = None,
) -> SLDCSnapshot:
    parser = _PageTables()
    parser.feed(html)
    page_text = _normalized(" ".join(parser.text))
    time_match = SNAPSHOT_TIME_PATTERN.search(page_text)
    if time_match is None:
        raise ValueError("SLDC page does not contain a DISCOM DRAWL timestamp")

    header_index = None
    drawl_index = None
    for index, row in enumerate(parser.rows):
        header = [_normalized(cell).upper() for cell in row]
        if header and header[0] == "DISCOM" and "DRAWL" in header:
            header_index = index
            drawl_index = header.index("DRAWL")
            break
    if header_index is None or drawl_index is None:
        raise ValueError("SLDC page does not contain the DISCOM DRAWL table")

    readings: dict[str, float] = {}
    for row in parser.rows[header_index + 1 :]:
        if not row:
            continue
        label = _normalized(row[0]).upper()
        entity = ENTITY_ROWS.get(label)
        if entity is None:
            continue
        if drawl_index >= len(row):
            raise ValueError(f"SLDC Drawl value is missing for {label}")
        numeric_text = _normalized(row[drawl_index]).replace(",", "")
        try:
            value = float(numeric_text)
        except ValueError as error:
            raise ValueError(f"SLDC Drawl value is invalid for {label}") from error
        if not isfinite(value):
            raise ValueError(f"SLDC Drawl value is not finite for {label}")
        readings[entity] = value

    missing = sorted(set(ENTITY_ROWS.values()) - readings.keys())
    if missing:
        raise ValueError(f"SLDC Drawl table is missing entities: {', '.join(missing)}")

    return {
        "timestamp": _snapshot_timestamp(time_match.group(1), now),
        "brpl_mw": readings["brpl_mw"],
        "bypl_mw": readings["bypl_mw"],
        "tpddl_mw": readings["tpddl_mw"],
        "ndmc_mw": readings["ndmc_mw"],
        "mes_mw": readings["mes_mw"],
        "railways_mw": readings["railways_mw"],
        "delhi_total_mw": readings["delhi_total_mw"],
    }


def fetch_sldc_snapshot(
    now: datetime | pd.Timestamp | None = None,
    timeout: float = 20,
) -> SLDCSnapshot:
    request = Request(
        SLDC_REALTIME_URL,
        headers={"User-Agent": "GridSense-Delhi-Actuals/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset)
    except (OSError, URLError) as error:
        raise OSError(f"Could not fetch the Delhi SLDC real-time page: {error}") from error
    return parse_sldc_snapshot(html, now=now)
