"""The target year's trading calendar, built from planner/<year>/calendar.yaml."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(year: int) -> dict:
    return yaml.safe_load((ROOT / "planner" / str(year) / "calendar.yaml").read_text(encoding="utf-8"))


def third_friday(year: int, month: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(4 - d.weekday()) % 7)
    return d + dt.timedelta(days=14)


class Calendar:
    def __init__(self, year: int):
        self.year = year
        self.cfg = load(year)
        self.holidays = {h["date"]: h for h in self.cfg["holidays"]}
        self.early = {e["date"]: e for e in self.cfg.get("early_closes", [])}
        self.fomc = {f["date"]: f for f in self.cfg.get("fomc", [])}
        overrides = {o["month"]: o for o in self.cfg.get("opex_overrides", [])}
        self.opex = {}
        for m in range(1, 13):
            d = overrides[m]["date"] if m in overrides else third_friday(year, m)
            self.opex[d] = {"quad": m in (3, 6, 9, 12), "note": overrides.get(m, {}).get("note")}
        self.days = [dt.date(year, 1, 1) + dt.timedelta(days=i)
                     for i in range((dt.date(year, 12, 31) - dt.date(year, 1, 1)).days + 1)]
        self.trading = [d for d in self.days if d.weekday() < 5 and d not in self.holidays]
        # Santa Claus Rally: last 5 sessions of December + first 2 of January (of both years touched).
        self.santa = set(self.trading[-5:]) | set(self.trading[:2])
        self.seasons = self.cfg.get("earnings_seasons", [])

    def month_trading(self, m: int) -> list[dt.date]:
        return [d for d in self.trading if d.month == m]

    def slot(self, d: dt.date):
        """Trading-day-of-month slot: 1..N-4 from the start, -4..-1 from the end."""
        days = self.month_trading(d.month)
        i = days.index(d) + 1
        n = len(days)
        return i - n - 1 if i > n - 4 else i

    def season_for(self, d: dt.date):
        for s in self.seasons:
            if s["start"] <= d <= s["end"]:
                return s
        return None

    def weeks(self) -> list[list[dt.date]]:
        """Monday-start weeks whose Monday falls in the year (Mon..Fri dates)."""
        first = dt.date(self.year, 1, 1)
        mon = first + dt.timedelta(days=(7 - first.weekday()) % 7)
        out = []
        while mon.year == self.year:
            out.append([mon + dt.timedelta(days=i) for i in range(5)])
            mon += dt.timedelta(days=7)
        return out


def slot_label(s: int) -> str:
    if s > 0:
        return f"TD {s} of the month"
    return {-1: "Last TD of the month", -2: "2nd-to-last TD of the month",
            -3: "3rd-to-last TD of the month", -4: "4th-to-last TD of the month"}[s]
