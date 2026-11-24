"""build/planner.json -> two iCalendar files for calendar apps (Google, Apple, Outlook).

  build/seasonal-ledger-<year>.ics          market calendar: NYSE closures and early close, FOMC,
                                            options/VIX expirations, 13F deadlines, Treasury
                                            auctions, earnings seasons (est.), Santa Claus Rally
                                            window, and economic releases at their release times (ET)
  build/seasonal-ledger-<year>-history.ics  one all-day entry per trading day with that day's
                                            trading-day-slot history (% up, avg, n), as on the day pages

Two files so the history can be shown or hidden as its own calendar. Every entry comes from the
same sources as the PDF; nothing here is computed except the file format. UIDs are stable, so
importing a newer build updates entries instead of duplicating them.

Usage: python pipeline/ics.py [year]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cal import Calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "seasonal-ledger"
TZ = "America/New_York"
# US Eastern rules since 2007 (second Sunday of March, first Sunday of November).
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE""".splitlines()

# Day-page badges that become their own entries elsewhere in this file.
SKIP_KINDS = {"econ", "santa", "earn"}
CATS = {"fomc": "FOMC", "opex": "Expirations", "early": "Market closed", "filing": "13F deadlines",
        "auction": "Treasury auctions", "earn": "Earnings season", "santa": "Santa Claus Rally",
        "econ": "Economic data", "history": "S&P history"}


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> list[str]:
    """RFC 5545: lines of at most 75 octets, continued with a leading space."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ""
        cur += ch
    out.append(cur)
    return [out[0]] + [" " + x for x in out[1:]]


def ymd(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


class Ics:
    def __init__(self, name: str, desc: str):
        self.stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Seasonal Ledger//pipeline/ics.py//EN",
                      "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{esc(name)}",
                      f"X-WR-CALDESC:{esc(desc)}", f"X-WR-TIMEZONE:{TZ}"]
        self.uids: set[str] = set()

    def event(self, uid: str, summary: str, start: dt.date | dt.datetime, end=None,
              desc: str | None = None, cat: str | None = None, url: str | None = None):
        assert uid not in self.uids, uid
        self.uids.add(uid)
        ev = ["BEGIN:VEVENT", f"UID:{uid}@{DOMAIN}", f"DTSTAMP:{self.stamp}"]
        if isinstance(start, dt.datetime):
            end = end or start + dt.timedelta(minutes=30)
            ev += [f"DTSTART;TZID={TZ}:{start:%Y%m%dT%H%M%S}", f"DTEND;TZID={TZ}:{end:%Y%m%dT%H%M%S}"]
        else:  # all-day; DTEND is exclusive
            end = end or start
            ev += [f"DTSTART;VALUE=DATE:{ymd(start)}", f"DTEND;VALUE=DATE:{ymd(end + dt.timedelta(days=1))}"]
        ev += [f"SUMMARY:{esc(summary)}", "TRANSP:TRANSPARENT"]  # informational: never shows as busy
        if desc:
            ev.append(f"DESCRIPTION:{esc(desc)}")
        if cat:
            ev.append(f"CATEGORIES:{esc(cat)}")
        if url:
            ev.append(f"URL:{url}")
        self.lines += ev + ["END:VEVENT"]

    def write(self, path: Path, tz: bool) -> None:
        body = self.lines[:8] + (VTIMEZONE if tz else []) + self.lines[8:] + ["END:VCALENDAR"]
        path.write_bytes(("\r\n".join(x for line in body for x in fold(line)) + "\r\n").encode("utf-8"))


def main(year: int) -> None:
    P = json.loads((ROOT / "build" / "planner.json").read_text(encoding="utf-8"))
    cal = Calendar(year)
    days = {d["date"]: d for m in P["months"] for w in m["weeks"] for d in w["days"]}
    window = P["window"]
    foot = f"From The Seasonal Ledger {year}."

    # Every dated item the PDF shows must fall on a day the planner covers.
    dated = set(cal.fomc) | set(cal.opex) | set(cal.vix) | set(cal.early) | set(cal.econ) | set(cal.f13) \
        | set(cal.auctions)
    missing = sorted(d for d in dated if d.isoformat() not in days)
    assert not missing, f"events on days outside the planner's weeks: {missing}"

    ev = Ics(f"Seasonal Ledger {year}",
             f"Market calendar for {year}: NYSE closures, FOMC, expirations, 13F deadlines, Treasury "
             f"auctions, earnings seasons (estimated) and US economic releases (ET). {foot}")
    for d, h in sorted(cal.holidays.items()):
        ev.event(f"{d}-closed", f"Market closed — {h['name']}", d, cat="Market closed",
                 desc=f"NYSE closed. {foot}")
    for key, d in sorted(days.items()):
        if d["closed"]:
            continue
        date = dt.date.fromisoformat(key)
        for b in d["badges"]:
            if b["kind"] in SKIP_KINDS:
                continue
            slug = b["kind"] + ("-vix" if b["text"].startswith("VIX") else "")
            ev.event(f"{key}-{slug}", b["text"], date, cat=CATS[b["kind"]], desc=foot)
    for s in cal.seasons:
        est = "" if s.get("kickoff") else " (est.)"
        ev.event(f"{s['start']}-earnings", f"{s['quarter']} earnings season{est}", s["start"], s["end"],
                 cat=CATS["earn"], desc=("Estimated window; replaced once the first big-bank report dates are "
                                   "announced. " if est else "") + foot)
    santa = sorted(cal.santa)
    for part in ([d for d in santa if d.month == 1], [d for d in santa if d.month == 12]):
        if part:
            ev.event(f"{part[0]}-santa", "Santa Claus Rally window", part[0], part[-1], cat=CATS["santa"],
                     desc="Last five trading days of December and first two of January. " + foot)
    for d, rels in sorted(cal.econ.items()):
        by: dict[str, list[dict]] = {}
        for r in rels:
            by.setdefault(r["time"], []).append(r)
        for t, rs in sorted(by.items()):
            hh, mm = map(int, t.split(":"))
            start = dt.datetime(d.year, d.month, d.day, hh, mm)
            ev.event(f"{d}-econ-{t.replace(':', '')}", ", ".join(r["label"] for r in rs), start, cat=CATS["econ"],
                     desc="\n".join(f"{r['agency']}: {r['release']}" for r in rs) + "\nTimes are Eastern. " + foot,
                     url=cal.econ_sources.get(rs[0]["agency"], "").replace("{empsit,cpi,ppi,jolts,eci}.htm", ""))
    out = ROOT / "build" / f"seasonal-ledger-{year}.ics"
    ev.write(out, tz=True)
    print(f"{len(ev.uids)} entries -> {out}")

    hi = Ics(f"Seasonal Ledger {year} — daily history",
             f"Each trading day's S&P 500 history by trading-day slot, {window}: share of years up, average "
             f"daily change, and n (number of years in the sample). {foot}")
    for key, d in sorted(days.items()):
        if d["closed"]:
            continue
        date = dt.date.fromisoformat(key)
        hi.event(f"{key}-history", f"S&P history: {d['pct_up']}% up · avg {d['avg']}% · n = {d['n']}", date, cat=CATS["history"],
                 desc="\n".join([f"{d['slot']}. In {window}, this slot closed higher than the prior session in "
                                 f"{d['pct_up']}% of {d['n']} years; average daily change {d['avg']}%. Describes history; not a forecast or advice."]
                                + d["notes"] + [foot]))
    out = ROOT / "build" / f"seasonal-ledger-{year}-history.ics"
    hi.write(out, tz=False)
    print(f"{len(hi.uids)} entries -> {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2027)
