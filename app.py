"""Sru & Aaku Expenses - a shared UPI / credit card ledger for Streamlit."""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ledger import (
    LEDGER_TITLES,
    PEOPLE,
    SOURCES,
    filter_period,
    format_day,
    format_long,
    format_month,
    group_by_day,
    inr,
    merge_tags,
    month_options,
    parse_amount,
    round2,
    summarize,
)
from storage import build_store

st.set_page_config(page_title="Sru & Aaku Expenses", page_icon="🧾", layout="wide")


# --------------------------------------------------------------------------
# Settings: Streamlit secrets first, then environment variables.
# --------------------------------------------------------------------------
def setting(name: str, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # no secrets file on a local run
        pass
    return os.environ.get(name.upper(), default)


def password_gate() -> None:
    """Optional: set `app_password` in secrets to keep the ledger private."""
    password = setting("app_password")
    if not password or st.session_state.get("authed"):
        return
    st.title("Sru & Aaku Expenses")
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(str(entered), str(password)):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("That password is not right.")
    st.stop()


@st.cache_resource(show_spinner=False)
def get_store(database_url: str | None, seed: bool):
    return build_store(database_url, sqlite_path=os.environ.get("LEDGER_DB", "expenses.db"), seed=seed)


password_gate()

try:
    store = get_store(
        setting("database_url"),
        str(setting("seed_sample_data", "true")).strip().lower() not in ("false", "0", "no"),
    )
except Exception as exc:  # bad URL, wrong password, database asleep...
    st.error(f"Could not open the ledger database: {exc}")
    st.stop()

try:
    tz = ZoneInfo(str(setting("timezone", "Asia/Kolkata")))
except Exception:
    tz = ZoneInfo("Asia/Kolkata")
today: date = datetime.now(tz).date()


# --------------------------------------------------------------------------
# Styling (rows and tiles use fixed colours with dark text, so they read in
# both the light and the dark Streamlit theme).
# --------------------------------------------------------------------------
st.markdown(
    "<style>"
    ".lg-day{display:flex;justify-content:space-between;font-size:.85rem;font-weight:600;opacity:.75;margin:14px 0 6px}"
    ".lg-row{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:8px 10px;"
    "border-radius:8px;margin-bottom:4px;color:#101828}"
    ".lg-badge{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:700;"
    "font-size:.8rem;color:#101828}"
    ".lg-item{font-weight:500;overflow-wrap:anywhere}"
    ".lg-meta{font-size:.8rem;opacity:.7}"
    ".lg-amt{font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:500;white-space:nowrap}"
    ".lg-tile{display:flex;gap:10px;padding:12px;border-radius:10px;color:#101828}"
    ".lg-tname{font-weight:600}"
    ".lg-tamt{font-size:1.7rem;font-weight:700;line-height:1.2}"
    ".lg-tmeta{font-size:.85rem;opacity:.7}"
    ".lg-split{display:flex;height:10px;border-radius:99px;overflow:hidden;background:rgba(128,128,128,.3);margin-top:10px}"
    ".lg-split i{display:block;height:100%}"
    ".lg-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}"
    ".lg-chip{border:1px solid rgba(128,128,128,.4);border-radius:99px;padding:2px 10px;font-size:.85rem}"
    ".lg-empty{opacity:.7;padding:12px 0}"
    "</style>",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
expenses = store.list_expenses()
all_tags = merge_tags(store.list_tags(), [e["tag"] for e in expenses])


def flash(kind: str, message: str) -> None:
    st.session_state["flash"] = (kind, message)


def on_add_expense() -> None:
    ss = st.session_state
    item = str(ss.get("f_item", "")).strip()
    amount = parse_amount(ss.get("f_amount"))
    if not item:
        flash("error", "Enter what the money was spent on.")
        return
    if amount is None:
        flash("error", "Enter an amount, like 250 or 650 + 1300.")
        return
    store.add_expense(
        {
            "spent_on": ss["f_date"].isoformat(),
            "source": ss["f_source"],
            "who": ss["f_who"],
            "item": item,
            "amount": amount,
            "tag": ss["f_tag"],
        }
    )
    ss["f_item"] = ""
    ss["f_amount"] = ""
    flash("ok", f"Added {inr(amount)} for {item}.")


def on_add_tag() -> None:
    ss = st.session_state
    name = " ".join(str(ss.get("f_newtag", "")).split())
    if not name:
        flash("error", "Type a name for the tag.")
        return
    if len(name) > 30:
        flash("error", "Keep tag names under 30 characters.")
        return
    current = merge_tags(store.list_tags(), [e["tag"] for e in store.list_expenses()])
    existing = next((t for t in current if t.lower() == name.lower()), None)
    if existing is None:
        store.add_tag(name)
        existing = name
        flash("ok", f'Added the tag "{name}".')
    else:
        flash("ok", f'The tag "{existing}" already exists, so it is selected.')
    ss["f_tag"] = existing
    ss["f_newtag"] = ""


# --------------------------------------------------------------------------
# Header + period filter
# --------------------------------------------------------------------------
head_left, head_right = st.columns([3, 1])
with head_left:
    st.title("Sru & Aaku Expenses")
    st.caption("Shared ledger for UPI and credit card spends")

period_choices = ["all", *month_options(expenses)]
if st.session_state.get("period", "all") not in period_choices:
    st.session_state["period"] = "all"
with head_right:
    period = st.selectbox(
        "Show",
        period_choices,
        key="period",
        format_func=lambda p: "All entries" if p == "all" else format_month(p),
    )

view = filter_period(expenses, period)
stats = summarize(view)


# --------------------------------------------------------------------------
# Totals
# --------------------------------------------------------------------------
left, right = st.columns([1, 1.3])
with left:
    label = f"Total as of {format_long(today)}" if period == "all" else f"{format_month(period)} total"
    st.metric(label, inr(stats["total"]))
    noun = "entry" if stats["count"] == 1 else "entries"
    st.caption(
        f"UPI {inr(stats['by_source']['upi'])}  ·  Credit card {inr(stats['by_source']['card'])}  ·  {stats['count']} {noun}"
    )
    if stats["by_tag"]:
        chips = "".join(
            f'<span class="lg-chip">{escape(tag)} <b>{inr(amount)}</b></span>' for tag, amount in stats["by_tag"].items()
        )
        st.markdown(f'<div class="lg-chips">{chips}</div>', unsafe_allow_html=True)

with right:
    st.markdown("**Spent by each person**")
    tile_cols = st.columns(2)
    people_total = sum(v["total"] for v in stats["by_who"].values())
    for col, (key, person) in zip(tile_cols, PEOPLE.items()):
        info = stats["by_who"][key]
        pct = round(info["total"] / stats["total"] * 100) if stats["total"] else 0
        count_noun = "entry" if info["count"] == 1 else "entries"
        with col:
            st.markdown(
                f'<div class="lg-tile" style="background:{person["soft"]}">'
                f'<span class="lg-badge" style="background:{person["strong"]}">{person["initial"]}</span>'
                f'<div><div class="lg-tname">{person["name"]}</div>'
                f'<div class="lg-tamt">{inr(info["total"])}</div>'
                f'<div class="lg-tmeta">{info["count"]} {count_noun}  ·  {pct}%</div></div></div>',
                unsafe_allow_html=True,
            )
    widths = {k: (v["total"] / people_total * 100 if people_total else 0) for k, v in stats["by_who"].items()}
    st.markdown(
        '<div class="lg-split">'
        f'<i style="width:{widths["sru"]:.2f}%;background:{PEOPLE["sru"]["strong"]}"></i>'
        f'<i style="width:{widths["aaku"]:.2f}%;background:{PEOPLE["aaku"]["strong"]}"></i>'
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()


# --------------------------------------------------------------------------
# Add expense
# --------------------------------------------------------------------------
st.subheader("Add expense")
if st.session_state.get("f_tag") not in all_tags:
    st.session_state["f_tag"] = all_tags[0]

with st.form("add_form", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.radio("Paid via", list(SOURCES), format_func=SOURCES.get, horizontal=True, key="f_source")
    c2.radio("Spent by", list(PEOPLE), format_func=lambda k: PEOPLE[k]["name"], horizontal=True, key="f_who")
    c3.date_input("Date", value=today, key="f_date")
    c4.selectbox("Tag", all_tags, key="f_tag")
    c5, c6 = st.columns([3, 1])
    c5.text_input("Item", key="f_item", placeholder="Chai, Rapido, Bed delivery")
    c6.text_input("Amount (₹)", key="f_amount", placeholder="250 or 650 + 1300")
    st.form_submit_button("Add expense", type="primary", on_click=on_add_expense)

with st.expander("+ New tag"):
    t1, t2 = st.columns([3, 1])
    t1.text_input("New tag name", key="f_newtag", placeholder="Fuel, Rent, Medicines", max_chars=30)
    t2.write("")
    t2.button("Add tag", on_click=on_add_tag)

message = st.session_state.pop("flash", None)
if message:
    (st.success if message[0] == "ok" else st.error)(message[1])


# --------------------------------------------------------------------------
# Ledgers
# --------------------------------------------------------------------------
def row_html(e: dict) -> str:
    p = PEOPLE.get(e["who"], {"name": "?", "initial": "?", "soft": "#EEEEEE", "strong": "#CCCCCC"})
    return (
        f'<div class="lg-row" style="background:{p["soft"]}">'
        f'<span class="lg-badge" style="background:{p["strong"]}">{p["initial"]}</span>'
        f'<div><div class="lg-item">{escape(e["item"])}</div>'
        f'<div class="lg-meta">{escape(e["tag"])}  ·  {p["name"]}</div></div>'
        f'<div class="lg-amt">{inr(e["amount"])}</div></div>'
    )


def ledger_html(rows: list[dict]) -> str:
    parts = []
    for day, items in group_by_day(rows):
        day_total = round2(sum(i["amount"] for i in items))
        parts.append(f'<div class="lg-day"><span>{format_day(day)}</span><span>{inr(day_total)}</span></div>')
        parts.extend(row_html(i) for i in items)
    return "".join(parts)


ledger_cols = st.columns(2)
for col, source in zip(ledger_cols, ("upi", "card")):
    rows = [e for e in view if e["source"] == source]
    with col:
        st.subheader(LEDGER_TITLES[source])
        st.caption(f"{inr(sum(r['amount'] for r in rows))}  ·  {len(rows)} {'entry' if len(rows) == 1 else 'entries'}")
        if rows:
            st.markdown(ledger_html(rows), unsafe_allow_html=True)
        else:
            where = "yet" if period == "all" else "in this month"
            st.markdown(f'<div class="lg-empty">No {LEDGER_TITLES[source].lower()} {where}. Add one above.</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Edit or delete
# --------------------------------------------------------------------------
with st.expander("Edit or delete entries"):
    if not view:
        st.write("Nothing to edit yet.")
    else:
        label_to_source = {v: k for k, v in SOURCES.items()}
        label_to_who = {v["name"]: k for k, v in PEOPLE.items()}
        frame = pd.DataFrame(
            [
                {
                    "id": e["id"],
                    "Delete": False,
                    "Date": date.fromisoformat(e["spent_on"]),
                    "Paid via": SOURCES.get(e["source"], "UPI"),
                    "Spent by": PEOPLE.get(e["who"], {"name": "Sru"})["name"],
                    "Item": e["item"],
                    "Amount": float(e["amount"]),
                    "Tag": e["tag"],
                }
                for e in view
            ]
        )
        version = st.session_state.get("editor_version", 0)
        edited = st.data_editor(
            frame,
            key=f"editor_{version}",
            hide_index=True,
            disabled=["id"],
            column_order=["Delete", "Date", "Paid via", "Spent by", "Item", "Amount", "Tag"],
            column_config={
                "Delete": st.column_config.CheckboxColumn("Delete"),
                "Date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                "Paid via": st.column_config.SelectboxColumn("Paid via", options=list(label_to_source)),
                "Spent by": st.column_config.SelectboxColumn("Spent by", options=list(label_to_who)),
                "Item": st.column_config.TextColumn("Item"),
                "Amount": st.column_config.NumberColumn("Amount (₹)", min_value=0.01, format="%.2f"),
                "Tag": st.column_config.SelectboxColumn("Tag", options=all_tags),
            },
        )
        if st.button("Save changes"):
            originals = {e["id"]: e for e in view}
            updated = deleted = 0
            problems = []
            for _, r in edited.iterrows():
                original = originals.get(int(r["id"]))
                if original is None:
                    continue
                if bool(r["Delete"]):
                    store.delete_expense(original["id"])
                    deleted += 1
                    continue
                item = "" if pd.isna(r["Item"]) else str(r["Item"]).strip()
                if not item or pd.isna(r["Amount"]) or float(r["Amount"]) <= 0 or pd.isna(r["Date"]):
                    problems.append(original["item"])
                    continue
                new = {
                    "spent_on": pd.to_datetime(r["Date"]).date().isoformat(),
                    "source": label_to_source[r["Paid via"]],
                    "who": label_to_who[r["Spent by"]],
                    "item": item,
                    "amount": round2(r["Amount"]),
                    "tag": str(r["Tag"]),
                }
                old = {k: original[k] for k in ("spent_on", "source", "who", "item", "tag")}
                old["amount"] = round2(original["amount"])
                if new != old:
                    store.update_expense(original["id"], new)
                    updated += 1
            st.session_state["editor_version"] = version + 1
            parts = []
            if updated:
                parts.append(f"{updated} updated")
            if deleted:
                parts.append(f"{deleted} deleted")
            if problems:
                parts.append(f"skipped {len(problems)} with a missing item, date or amount")
            flash("error" if problems else "ok", ", ".join(parts).capitalize() + "." if parts else "No changes to save.")
            st.rerun()

st.caption(
    "Saved in a hosted database."
    if store.kind == "postgres"
    else "Saved in a local file (expenses.db). On Streamlit Community Cloud this file is erased when the app restarts; "
    "add a database_url secret to keep your data."
)
