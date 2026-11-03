"""Pure helpers for the expense ledger. No Streamlit and no database in here,
so everything in this file can be tested with plain Python."""
from __future__ import annotations

import re
from datetime import date

DEFAULT_TAGS = ["Food", "Food - Swiggy", "Food - Restaurant", "Grocery", "Snacks", "Other"]

# Colours match the original spreadsheet: green for Sru, blue for Aaku.
PEOPLE = {
    "sru": {"name": "Sru", "initial": "S", "soft": "#E4F3D3", "strong": "#86C443"},
    "aaku": {"name": "Aaku", "initial": "A", "soft": "#DFE6F8", "strong": "#8EA5E3"},
}
SOURCES = {"upi": "UPI", "card": "Credit card"}
LEDGER_TITLES = {"upi": "UPI swipes", "card": "Credit card swipes"}

_NUMBER = re.compile(r"^(\d+\.?\d*|\.\d+)$")


def round2(value: float) -> float:
    return round(float(value), 2)


def parse_amount(text) -> float | None:
    """Turn '250', '1,250' or '650 + 1300' into a number. Returns None when the
    text is not a valid positive amount."""
    if text is None:
        return None
    parts = re.sub(r"[₹,\s]", "", str(text)).split("+")
    total = 0.0
    for part in parts:
        if not _NUMBER.match(part):
            return None
        total += float(part)
    total = round2(total)
    return total if total > 0 else None


def inr(value: float) -> str:
    """Format with Indian digit grouping: 195000 -> ₹1,95,000."""
    cents = int(round(abs(float(value)) * 100))
    whole, frac = divmod(cents, 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    out = "₹" + digits + (f".{frac:02d}" if frac else "")
    return "-" + out if value < 0 else out


def merge_tags(custom: list[str], used: list[str]) -> list[str]:
    """Default tags first, then custom ones, then any tag found on an entry."""
    seen: set[str] = set()
    merged: list[str] = []
    for name in [*DEFAULT_TAGS, *custom, *used]:
        name = str(name).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            merged.append(name)
    return merged


def month_options(expenses: list[dict]) -> list[str]:
    return sorted({e["spent_on"][:7] for e in expenses}, reverse=True)


def filter_period(expenses: list[dict], period: str) -> list[dict]:
    if period == "all":
        return list(expenses)
    return [e for e in expenses if e["spent_on"][:7] == period]


def summarize(expenses: list[dict]) -> dict:
    total = 0.0
    by_source = {k: 0.0 for k in SOURCES}
    by_who = {k: {"total": 0.0, "count": 0} for k in PEOPLE}
    by_tag: dict[str, float] = {}
    for e in expenses:
        amount = float(e["amount"])
        total += amount
        if e["source"] in by_source:
            by_source[e["source"]] += amount
        if e["who"] in by_who:
            by_who[e["who"]]["total"] += amount
            by_who[e["who"]]["count"] += 1
        by_tag[e["tag"]] = by_tag.get(e["tag"], 0.0) + amount
    return {
        "total": round2(total),
        "count": len(expenses),
        "by_source": {k: round2(v) for k, v in by_source.items()},
        "by_who": {k: {"total": round2(v["total"]), "count": v["count"]} for k, v in by_who.items()},
        "by_tag": dict(sorted(((k, round2(v)) for k, v in by_tag.items()), key=lambda kv: -kv[1])),
    }


def group_by_day(expenses: list[dict]) -> list[tuple[str, list[dict]]]:
    """Newest day first; inside a day, the most recently added entry first."""
    rows = sorted(expenses, key=lambda e: (e["spent_on"], e.get("created_at", 0), e.get("id", 0)), reverse=True)
    groups: list[tuple[str, list[dict]]] = []
    for row in rows:
        if groups and groups[-1][0] == row["spent_on"]:
            groups[-1][1].append(row)
        else:
            groups.append((row["spent_on"], [row]))
    return groups


def format_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%a} {d.day} {d:%b}"


def format_long(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def format_month(key: str) -> str:
    d = date.fromisoformat(key + "-01")
    return f"{d:%B %Y}"
