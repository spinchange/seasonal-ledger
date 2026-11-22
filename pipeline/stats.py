"""Compute every seasonal statistic the planner prints.

Reads data/raw/gspc.csv (from fetch.py) and planner/<year>/calendar.yaml,
writes data/stats/<year>.json (committed). Every number in the PDF comes from here
or from calendar.yaml; templates never compute statistics.

Usage: python pipeline/stats.py [year]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
from dateutil.easter import easter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cal import Calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def summ(r: pd.Series | list, years=None) -> dict:
    s = pd.Series(r, dtype=float).dropna()
    if s.empty:
        return {"n": 0}
    out = {"n": int(len(s)), "avg": round(float(s.mean()) * 100, 2),
           "pct_up": round(float((s > 0).mean()) * 100), "median": round(float(s.median()) * 100, 2)}
    if years is not None:
        ys = pd.Series(years, index=s.index if len(years) == len(s) else None)
        out["best"] = {"year": int(ys[s.idxmax()]), "chg": round(float(s.max()) * 100, 1)}
        out["worst"] = {"year": int(ys[s.idxmin()]), "chg": round(float(s.min()) * 100, 1)}
    return out


def cycle_year(y: int) -> int:
    """1 post-election, 2 midterm, 3 pre-election, 4 election."""
    return {1: 1, 2: 2, 3: 3, 0: 4}[y % 4]


def observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def nth_weekday(y, m, wd, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(wd - d.weekday()) % 7)
    return d + dt.timedelta(days=7 * (n - 1))


def last_weekday(y, m, wd):
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


HOLIDAY_RULES = {
    "mlk": lambda y: nth_weekday(y, 1, 0, 3) if y >= 1998 else None,
    "presidents": lambda y: nth_weekday(y, 2, 0, 3) if y >= 1971 else observed(dt.date(y, 2, 22)),
    "good_friday": lambda y: easter(y) - dt.timedelta(days=2),
    "memorial": lambda y: last_weekday(y, 5, 0) if y >= 1971 else observed(dt.date(y, 5, 30)),
    "july4": lambda y: observed(dt.date(y, 7, 4)),
    "labor": lambda y: nth_weekday(y, 9, 0, 1),
    "thanksgiving": lambda y: nth_weekday(y, 11, 3, 4),
    "christmas": lambda y: observed(dt.date(y, 12, 25)),
}


def main(year: int) -> None:
    cal = Calendar(year)
    y0, y1 = cal.cfg["stats_window"]
    px = pd.read_csv(ROOT / "data" / "raw" / "gspc.csv", parse_dates=["date"]).set_index("date")["close"]
    px = px[px.index <= f"{y1 + 1}-01-31"]  # keep Jan of y1+1 for Santa windows that end in it
    ret = px.pct_change()
    days = ret[(ret.index >= f"{y0}-01-01") & (ret.index <= f"{y1}-12-31")]
    tdates = [d.date() for d in px.index]
    tset = set(tdates)
    close = {d.date(): c for d, c in px.items()}
    dret = {d.date(): r for d, r in ret.items()}

    def last_before(d):  # last trading date strictly before d
        i = pd.Index(tdates).searchsorted(d) - 1
        return tdates[i]

    def first_after(d):
        i = pd.Index(tdates).searchsorted(d, side="right")
        return tdates[i]

    def chg(a, b):
        return close[b] / close[a] - 1

    out: dict = {"meta": {"year": year, "first_year": y0, "last_year": y1, "n_years": y1 - y0 + 1,
                          "series": "S&P 500 price index (^GSPC), daily closes, dividends excluded",
                          "built": dt.date.today().isoformat()}}

    # ---- months & years -------------------------------------------------------
    me = px.resample("ME").last()
    mchg = me.pct_change()
    mchg = mchg[(mchg.index.year >= y0) & (mchg.index.year <= y1)]
    ye = px.resample("YE").last()
    ychg = ye.pct_change()
    ychg = ychg[(ychg.index.year >= y0) & (ychg.index.year <= y1)]
    yby = {i.year: v for i, v in ychg.items()}

    months = {}
    for m in range(1, 13):
        s = mchg[mchg.index.month == m]
        yrs = list(s.index.year)
        pre = s[[cycle_year(y) == 3 for y in yrs]]
        rec = s[[y > y1 - 20 for y in yrs]]
        months[m] = {"all": summ(s.values, yrs), "pre": summ(pre.values),
                     "last20": summ(rec.values)}
    out["months"] = months
    out["years"] = {"all": summ(list(yby.values()), list(yby.keys()))}
    out["cycle"] = {}
    for c in (1, 2, 3, 4):
        ys = [y for y in yby if cycle_year(y) == c]
        out["cycle"][c] = summ([yby[y] for y in ys]) | {"first": ys[0], "last": ys[-1]}

    # ---- six-month periods -----------------------------------------------------
    best, worst = [], []
    for y in range(y0, y1 + 1):
        oct_prev = me[(me.index.year == y - 1) & (me.index.month == 10)]
        apr = me[(me.index.year == y) & (me.index.month == 4)]
        octy = me[(me.index.year == y) & (me.index.month == 10)]
        if len(oct_prev) and len(apr) and y - 1 >= y0:
            best.append(apr.iloc[0] / oct_prev.iloc[0] - 1)
        if len(apr) and len(octy):
            worst.append(octy.iloc[0] / apr.iloc[0] - 1)
    grow = lambda xs: round(10000 * float(pd.Series(xs).add(1).prod()))  # noqa: E731
    out["six"] = {"best": summ(best) | {"growth10k": grow(best)},
                  "worst": summ(worst) | {"growth10k": grow(worst)}}

    # ---- January Barometer -----------------------------------------------------
    hits = [mchg[(mchg.index.year == y) & (mchg.index.month == 1)].iloc[0] * yby[y] > 0
            for y in yby]
    out["jan_barometer"] = {"hits": int(sum(hits)), "n": len(hits),
                            "pct": round(100 * sum(hits) / len(hits))}

    # ---- Santa Claus Rally ------------------------------------------------------
    sc, nxt = [], []
    for y in range(y0, y1 + 1):
        dec = [d for d in tdates if d.year == y and d.month == 12]
        jan = [d for d in tdates if d.year == y + 1 and d.month == 1]
        if len(dec) < 6 or len(jan) < 2:
            continue
        r = chg(dec[-6], jan[1])
        sc.append(r)
        if y + 1 in yby:
            nxt.append((r, yby[y + 1]))
    fail = [n for r, n in nxt if r <= 0]
    ok = [n for r, n in nxt if r > 0]
    out["santa"] = summ(sc) | {"after_fail": summ(fail), "after_success": summ(ok)}

    # ---- trading-day-of-month slots ---------------------------------------------
    slots: dict = {m: {} for m in range(1, 13)}
    from_start: dict = {m: {} for m in range(1, 13)}
    for (yy, mm), grp in days.groupby([days.index.year, days.index.month]):
        n = len(grp)
        for i, (d, r) in enumerate(grp.items(), start=1):
            s = i - n - 1 if i > n - 4 else i
            slots[mm].setdefault(s, []).append(r)
            from_start[mm].setdefault(i, []).append(r)
    out["slots"] = {m: {str(k): summ(v) for k, v in sorted(slots[m].items())} for m in slots}
    out["td_from_start"] = {m: {str(k): summ(v) for k, v in sorted(from_start[m].items())}
                            for m in from_start}

    # ---- holidays -----------------------------------------------------------------
    hol = {}
    for key, rule in HOLIDAY_RULES.items():
        before, after, mon_after = [], [], []
        for y in range(y0, y1 + 1):
            h = rule(y)
            if h is None or h.weekday() >= 5 or h in tset:
                continue  # market was not actually closed that weekday
            b, a = last_before(h), first_after(h)
            if b.year < y0 or a.year > y1 + 1:
                continue
            before.append(dret[b])
            after.append(dret[a])
            if key == "thanksgiving":
                mon_after.append(dret[first_after(h + dt.timedelta(days=3))])
        hol[key] = {"before": summ(before), "after": summ(after)}
        if key == "thanksgiving":
            hol[key]["monday_after"] = summ(mon_after)
            wk = []
            for y in range(y0, y1 + 1):
                h = rule(y)
                start = last_before(h - dt.timedelta(days=3))  # prior Friday's close
                wk.append(chg(start, first_after(h)))
            hol[key]["week"] = summ(wk)
    # first / last trading day of year
    fy = [dret[min(d for d in tdates if d.year == y)] for y in range(y0, y1 + 1)]
    ly = [dret[max(d for d in tdates if d.year == y)] for y in range(y0, y1 + 1)]
    hol["new_year"] = {"before": summ(ly), "after": summ(fy)}
    out["holidays"] = hol

    # ---- calendar-aligned weekly windows for the target year ------------------------
    weeks = {}
    for w, wdays in enumerate(cal.weeks(), start=1):
        mon, fri = wdays[0], wdays[-1]
        rs = []
        for y in range(y0, y1 + 1):
            try:
                a = last_before(dt.date(y, mon.month, mon.day))
                b = last_before(dt.date(y, fri.month, fri.day) + dt.timedelta(days=1))
            except ValueError:
                continue
            if a < b:
                rs.append(chg(a, b))
        weeks[w] = summ(rs)
    out["weeks"] = weeks

    # ---- earnings seasons (calendar-aligned to the target year's estimated windows) ----
    seas, off = {}, []
    for i, s in enumerate(cal.seasons):
        rs = []
        for y in range(y0, y1 + 1):
            a = last_before(dt.date(y, s["start"].month, s["start"].day))
            b = last_before(dt.date(y, s["end"].month, s["end"].day) + dt.timedelta(days=1))
            rs.append(chg(a, b))
        seas[s["quarter"]] = summ(rs)
    # in-season vs off-season, average daily change, using this year's window dates every year
    def in_season(d: dt.date) -> bool:
        md = (d.month, d.day)
        return any((s["start"].month, s["start"].day) <= md <= (s["end"].month, s["end"].day)
                   for s in cal.seasons)
    ins = [r for d, r in days.items() if in_season(d.date())]
    outs = [r for d, r in days.items() if not in_season(d.date())]
    recent = lambda xs, f: [r for d, r in days.items() if d.year >= 1995 and f(d.date())]  # noqa: E731
    out["earnings"] = {
        "seasons": seas,
        "daily_in": summ(ins) | {"avg_bp": round(float(pd.Series(ins).mean()) * 1e4, 1)},
        "daily_out": summ(outs) | {"avg_bp": round(float(pd.Series(outs).mean()) * 1e4, 1)},
        "daily_in_1995": {"avg_bp": round(float(pd.Series(recent(None, in_season)).mean()) * 1e4, 1)},
        "daily_out_1995": {"avg_bp": round(float(pd.Series(recent(None, lambda d: not in_season(d))).mean()) * 1e4, 1)},
    }

    dest = ROOT / "data" / "stats" / f"{year}.json"
    dest.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2027)
