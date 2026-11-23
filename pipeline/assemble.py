"""Merge stats + calendar + editorial notes into build/planner.json for Typst.

All prose that quotes a number does so through {tokens} resolved here, so
the text can never drift from the data. Token syntax: {path.to.value} or
{path.to.value|signed}. Paths start at: s (stats json), w (this week's stat),
m (this month's stats), c (calendar yaml).

Usage: python pipeline/assemble.py [year]
"""
from __future__ import annotations

import calendar as pycal
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cal import Calendar, slot_label  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MONTHS = list(pycal.month_name)
MON3 = list(pycal.month_abbr)
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TOKEN = re.compile(r"\{([A-Za-z0-9_.]+)(\|signed)?\}")


def signed(v) -> str:
    if isinstance(v, (int, float)):
        return f"+{v}" if v > 0 else ("−" + str(abs(v)) if v < 0 else "0")
    return str(v)


def fill(text: str | None, ctx: dict) -> str | None:
    if text is None:
        return None

    def rep(mo):
        cur = ctx
        for part in mo.group(1).split("."):
            if isinstance(cur, dict):
                cur = cur[part] if part in cur else cur[int(part)] if part.isdigit() and int(part) in cur else cur[part]
            else:
                cur = getattr(cur, part)
        return signed(cur) if mo.group(2) else str(cur)

    return TOKEN.sub(rep, text).strip()


def fmt_day(d: dt.date) -> str:
    return f"{MON3[d.month]} {d.day}"


def main(year: int) -> None:
    cal = Calendar(year)
    S = json.loads((ROOT / "data" / "stats" / f"{year}.json").read_text(encoding="utf-8"))
    notes = yaml.safe_load((ROOT / "planner" / str(year) / "notes.yaml").read_text(encoding="utf-8")) or {}
    wnotes = notes.get("weeks", {}) or {}
    mnotes = notes.get("months", {}) or {}
    y0, y1 = S["meta"]["first_year"], S["meta"]["last_year"]
    H = S["holidays"]

    # holiday-relative day notes for the target year
    day_notes: dict[dt.date, list[str]] = {}
    labels = {"mlk": "MLK Day", "presidents": "Presidents' Day", "good_friday": "Good Friday",
              "memorial": "Memorial Day", "july4": "Independence Day", "labor": "Labor Day",
              "thanksgiving": "Thanksgiving", "christmas": "Christmas"}
    for hd, h in cal.holidays.items():
        k = h["key"]
        if k not in labels or not H.get(k, {}).get("before", {}).get("n"):
            continue
        b = max(d for d in cal.trading if d < hd) if any(d < hd for d in cal.trading) else None
        a = min(d for d in cal.trading if d > hd) if any(d > hd for d in cal.trading) else None
        for d, side, word in ((b, "before", "Day before"), (a, "after", "Day after")):
            if d is None:
                continue
            st = H[k][side]
            day_notes.setdefault(d, []).append(
                f"{word} {labels[k]}: up {st['pct_up']}% of years, avg {signed(st['avg'])}% (n = {st['n']})")
        if k == "thanksgiving":
            ma = min(d for d in cal.trading if d >= hd + dt.timedelta(days=4))
            st = H[k]["monday_after"]
            day_notes.setdefault(ma, []).append(
                f"Monday after Thanksgiving: up {st['pct_up']}% of years, avg {signed(st['avg'])}%")
    st = H["new_year"]
    day_notes.setdefault(cal.trading[0], []).insert(
        0, f"First trading day of the year: up {st['after']['pct_up']}% of years, avg {signed(st['after']['avg'])}%")
    day_notes.setdefault(cal.trading[-1], []).insert(
        0, f"Last trading day of the year: up {st['before']['pct_up']}% of years, avg {signed(st['before']['avg'])}%")

    def badges(d: dt.date) -> list[dict]:
        out = []
        if d in cal.fomc:
            f = cal.fomc[d]
            out.append({"kind": "fomc", "text": "FOMC strategy meeting" if f["kind"] == "strategy"
                        else "FOMC decision" + (" + SEP" if f.get("sep") else "")})
        if d in cal.opex:
            out.append({"kind": "opex", "text": "Quad witching" if cal.opex[d]["quad"] else "Options expiration"})
        if d in cal.early:
            out.append({"kind": "early", "text": cal.early[d]["note"]})
        if d in cal.santa:
            out.append({"kind": "santa", "text": "Santa Claus Rally window"})
        if d in cal.auctions:
            secs = [a["security"] for a in cal.auctions[d]]
            out.append({"kind": "auction", "text": ("Treasury auction: " if len(secs) == 1 else "Treasury auctions: ")
                        + ", ".join(secs)})
        for s in cal.seasons:
            if d == (s.get("kickoff") or s["start"]):
                out.append({"kind": "earn", "text": f"{s['quarter']} earnings season opens" + ("" if s.get("kickoff") else " (est.)")})
        return out

    def day_rec(d: dt.date) -> dict:
        rec = {"date": d.isoformat(), "day": d.day, "mon": MON3[d.month].upper(), "dow": DOW[d.weekday()]}
        if d in cal.holidays:
            return rec | {"closed": True, "closed_text": f"Market closed — {cal.holidays[d]['name']}"}
        s = cal.slot(d)
        stt = S["slots"][str(d.month)][str(s)]
        return rec | {"closed": False, "slot": slot_label(s), "pct_up": stt["pct_up"], "avg": signed(stt["avg"]),
                      "n": stt["n"], "notes": day_notes.get(d, []), "badges": badges(d)}

    # week ranking by average
    wk_avgs = sorted(((v["avg"], int(k)) for k, v in S["weeks"].items()), reverse=True)
    rank = {w: i + 1 for i, (_, w) in enumerate(wk_avgs)}

    weeks = []
    allweeks = cal.weeks()
    for wn, wdays in enumerate(allweeks, start=1):
        mon, fri = wdays[0], wdays[-1]
        ws = S["weeks"][str(wn)] | {"rank": rank[wn], "of": len(allweeks)}
        events = []
        title = None
        hols = [cal.holidays[d] for d in wdays if d in cal.holidays]
        decision = [d for d in wdays if d in cal.fomc]
        opex = [d for d in wdays if d in cal.opex]
        season = next((s for d in wdays if (s := cal.season_for(d))), None)
        kick = [s for s in cal.seasons if mon <= (s.get("kickoff") or s["start"]) <= fri]
        for h in hols:
            events.append(f"Market closed {DOW[h['date'].weekday()]} for {h['name']}.")
        for d in decision:
            f = cal.fomc[d]
            events.append(f"FOMC strategy meeting {DOW[d.weekday()]} (no policy decision)." if f["kind"] == "strategy"
                          else f"FOMC decision {DOW[d.weekday()]}" + (" with economic projections." if f.get("sep") else "."))
        for d in opex:
            events.append(("Quad witching" if cal.opex[d]["quad"] else "Monthly options expire")
                          + f" {DOW[d.weekday()]}" + (f" ({cal.opex[d]['note']})." if cal.opex[d]["note"] else "."))
        for s in kick:
            events.append(f"{s['quarter']} earnings season opens (est.).")
        if season and not kick:
            events.append(f"{season['quarter']} earnings season under way.")
        if hols:
            title = f"{hols[0]['name'].replace(' (obs.)', '')} week"
        elif decision and cal.fomc[decision[0]]["kind"] == "decision":
            title = "FOMC week"
        elif opex and cal.opex[opex[0]]["quad"]:
            title = "Quad witching week"
        elif kick:
            title = "Earnings season opens"
        elif opex:
            title = "Options expiration week"
        else:
            title = f"{'Early' if mon.day <= 10 else 'Mid' if mon.day <= 20 else 'Late'} {MONTHS[mon.month]}"
        if wn == 1:
            title = "First week of the year"

        tone = ("One of the year's firmer windows" if ws["rank"] <= 10 else
                "One of the year's softer windows" if ws["rank"] > len(allweeks) - 10 else None)
        auto = (f"Over the same calendar window, {y0}–{y1}, the S&P 500 rose in *{ws['pct_up']}%* of years, "
                f"averaging {signed(ws['avg'])}% (rank {ws['rank']} of {len(allweeks)}). "
                + (tone + ". " if tone else "") + " ".join(events))
        note = wnotes.get(wn, {}) or {}
        ctx = {"s": S, "w": ws, "c": cal.cfg}
        nxt = allweeks[wn] if wn < len(allweeks) else None
        weeks.append({
            "num": wn, "month": mon.month,
            "kicker": f"WEEK {wn} · {MONTHS[mon.month].upper()} {mon.day} – "
                      + (f"{fri.day}" if fri.month == mon.month else f"{MONTHS[fri.month].upper()} {fri.day}")
                      + f", {year}",
            "title": fill(note.get("title"), ctx) or title,
            "blurb": (fill(note["blurb"], ctx) + ((" " + " ".join(events)) if events and note.get("events", True) else ""))
                     if note.get("blurb") else auto,
            "auto": "blurb" not in note,
            "next": fill(note.get("next"), ctx),
            "stat": ws,
            "season": season["quarter"] if season else None,
            "days": [day_rec(d) for d in wdays],
        })

    # months
    months = []
    for m in range(1, 13):
        ms = S["months"][str(m)]
        mdays = cal.month_trading(m)
        cat = []
        for d in sorted(cal.fomc):
            if d.month == m:
                f = cal.fomc[d]
                cat.append(f"FOMC {'strategy meeting' if f['kind'] == 'strategy' else 'decision'} {fmt_day(d)}")
        for d in sorted(cal.opex):
            if d.month == m:
                cat.append(("quad witching " if cal.opex[d]["quad"] else "options expiration ") + fmt_day(d))
        for s in cal.seasons:
            if s["start"].month == m:
                cat.append(f"{s['quarter']} earnings season from {fmt_day(s['start'])} (est.)")
        hol = [f"{h['name']} {fmt_day(d)}" for d, h in cal.holidays.items() if d.month == m]
        sched = " Scheduled: " + "; ".join(cat + [f"market closed {h}" for h in hol]) + "." if cat or hol else ""
        auto = (f"{MONTHS[m]} has risen in {ms['all']['pct_up']}% of years since {y0}, averaging "
                f"{signed(ms['all']['avg'])}%; in pre-election years, {ms['pre']['pct_up']}% and "
                f"{signed(ms['pre']['avg'])}%.")
        mn = mnotes.get(m, {}) or {}
        ctx = {"s": S, "m": ms, "c": cal.cfg}
        cards = [
            {"big": f"{signed(ms['all']['avg'])}%", "label": f"Avg. {MONTHS[m]}",
             "sub": f"{ms['all']['pct_up']}% up · n = {ms['all']['n']}"},
            {"big": f"{signed(ms['pre']['avg'])}%", "label": "Pre-election " + (MONTHS[m][:-1] + "ies" if MONTHS[m].endswith("ry") else MONTHS[m] + "s"),
             "sub": f"{ms['pre']['pct_up']}% up · n = {ms['pre']['n']}"},
        ]
        if m == 12:
            sc = S["santa"]
            cards.append({"big": f"{signed(sc['avg'])}%", "label": "Santa Claus Rally",
                          "sub": f"{sc['pct_up']}% up · n = {sc['n']}"})
        elif m == 1:
            jb = S["jan_barometer"]
            cards.append({"big": f"{jb['pct']}%", "label": "January Barometer",
                          "sub": f"{jb['hits']} of {jb['n']} years"})
        else:
            cards.append({"big": f"{signed(ms['last20']['avg'])}%", "label": "Last 20 years",
                          "sub": f"{ms['last20']['pct_up']}% up · {y1 - 19}–{y1}"})
        cards.append({"big": f"{signed(ms['all']['best']['chg'])}%", "label": f"Best {MONTHS[m]}",
                      "sub": f"{ms['all']['best']['year']} · worst {signed(ms['all']['worst']['chg'])}% in {ms['all']['worst']['year']}"})
        tdf = S["td_from_start"][str(m)]
        chart = [{"td": int(k), "avg": v["avg"], "pct_up": v["pct_up"], "n": v["n"]}
                 for k, v in tdf.items() if v["n"] >= 0.6 * S["meta"]["n_years"]]
        # month grid
        first = dt.date(year, m, 1)
        lead = (first.weekday() + 1) % 7  # Sunday-first
        ndays = pycal.monthrange(year, m)[1]
        cells = [None] * lead
        for i in range(1, ndays + 1):
            d = dt.date(year, m, i)
            c = {"day": i, "weekend": d.weekday() >= 5, "santa": d in cal.santa,
                 "season": bool(cal.season_for(d))}
            if d in cal.holidays:
                c["note"] = cal.holidays[d]["name"]
                c["closed"] = True
            elif d.weekday() < 5:
                s = cal.slot(d)
                c["pct_up"] = S["slots"][str(m)][str(s)]["pct_up"]
                c["notes"] = [b["text"] for b in badges(d) if b["kind"] in ("fomc", "opex", "early", "earn")]
            cells.append(c)
        while len(cells) % 7:
            cells.append(None)
        months.append({"m": m, "name": MONTHS[m], "blurb": (fill(mn.get("blurb"), ctx) or auto) + sched,
                       "cards": cards, "chart": chart, "sessions": len(mdays), "cells": cells,
                       "weeks": [w for w in weeks if w["month"] == m]})

    # year-at-a-glance mini calendars
    glance = []
    for m in range(1, 13):
        first = dt.date(year, m, 1)
        cells = [None] * ((first.weekday() + 1) % 7)
        for i in range(1, pycal.monthrange(year, m)[1] + 1):
            d = dt.date(year, m, i)
            f = cal.fomc.get(d)
            cells.append({"day": i, "weekend": d.weekday() >= 5, "closed": d in cal.holidays,
                          "early": d in cal.early, "fomc": bool(f and f["kind"] == "decision"),
                          "opex": d in cal.opex, "santa": d in cal.santa, "season": bool(cal.season_for(d))})
        glance.append({"name": MONTHS[m], "cells": cells})

    fomc_list = []
    for d, f in sorted(cal.fomc.items()):
        fomc_list.append(f"{fmt_day(d)} — " + ("FOMC strategy meeting (no decision)" if f["kind"] == "strategy"
                         else "FOMC decision" + (" + SEP" if f.get("sep") else "")))
    hol_list = [f"{fmt_day(d)} — {h['name']}" for d, h in sorted(cal.holidays.items())]
    hol_list += [f"{fmt_day(d)} — early close, 1:00 pm ET" for d in sorted(cal.early)]

    out = {
        "year": year, "meta": S["meta"], "stats": S,
        "window": f"{y0}–{y1}",
        "months": months, "glance": glance,
        "holiday_list": hol_list, "fomc_list": fomc_list, "fomc_note": cal.cfg.get("fomc_note"),
        "seasons": [{"quarter": s["quarter"], "start": fmt_day(s["start"]), "end": fmt_day(s["end"]),
                     "kickoff": fmt_day(s["kickoff"]) if s.get("kickoff") else None,
                     "stat": S["earnings"]["seasons"][s["quarter"]]} for s in cal.seasons],
        "earnings_note": cal.cfg.get("earnings_note"),
        "auction_list": [f"{fmt_day(d)}: " + ", ".join(a["security"] for a in v) for d, v in sorted(cal.auctions.items())],
        "auction_note": (f"Treasury coupon auctions (notes, bonds, TIPS, FRNs) are marked on the day pages "
                         f"through {fmt_day(cal.auctions_through)}, from Treasury's tentative schedule. Later dates "
                         f"are published at each quarterly refunding (early Feb, May and Aug)."
                         if cal.auctions_through else None),
        "notes": {k: fill(v, {"s": S, "c": cal.cfg}) for k, v in (notes.get("pages") or {}).items()},
    }
    dest = ROOT / "build" / "planner.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {dest}: {len(weeks)} weeks, {sum(1 for w in weeks if w['auto'])} with auto blurbs")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2027)
