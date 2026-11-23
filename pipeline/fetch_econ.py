"""Fetch the year's major US economic releases -> planner/<year>/econ_releases.yaml.

Sources (official agency schedules, public domain):
  BEA     https://www.bea.gov/news/schedule/next-year   GDP, Personal Income and Outlays (PCE)
  Census  https://www.census.gov/economic-indicators/calendar-listview.html
          Retail sales, housing starts, new home sales, durable goods
  BLS     https://www.bls.gov/schedule/news_release/<release>.htm   jobs report, CPI, PPI, JOLTS, ECI

BLS refuses scripted downloads (HTTP 403), so the BLS entries are copied by hand from its
per-release schedule pages (empsit, cpi, ppi, jolts, eci) and this script keeps them as they
are. BEA and Census entries are replaced on every run. BEA's "next-year" page shows next
year only until January; after that use https://www.bea.gov/news/schedule/full.

Not included, because no official full-year schedule is published: Conference Board LEI and
consumer confidence, ISM PMIs, University of Michigan sentiment. Weekly jobless claims come
out every Thursday at 8:30 am ET (a day earlier in a holiday week) and are described in a
note, not marked day by day.

Usage: python pipeline/fetch_econ.py [year]
"""
from __future__ import annotations

import datetime as dt
import html
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BEA_URL = "https://www.bea.gov/news/schedule/next-year"
CENSUS_URL = "https://www.census.gov/economic-indicators/calendar-listview.html"
BLS_PAGES = "https://www.bls.gov/schedule/news_release/"

# (agency, title prefix as published, short label, key). Order sets the order within a day.
WANTED = [
    ("BEA", "GDP (Advance Estimate)", "GDP (advance)", "gdp"),
    ("BEA", "GDP (Second Estimate)", "GDP (2nd est.)", "gdp"),
    ("BEA", "GDP (Third Estimate)", "GDP (3rd est.)", "gdp"),
    ("BEA", "Personal Income and Outlays", "PCE inflation", "pce"),
    ("Census", "Advance Monthly Sales for Retail and Food Services", "Retail sales", "retail"),
    ("Census", "New Residential Construction", "Housing starts", "starts"),
    ("Census", "New Residential Sales", "New home sales", "newhome"),
    ("Census", "Advance Report on Durable Goods", "Durable goods", "durables"),
]
# Display order of all kinds, BLS included (the BLS labels are in the hand-kept entries).
ORDER = ["jobs", "cpi", "pce", "gdp", "ppi", "retail", "jolts", "eci", "starts", "newhome", "durables"]


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "seasonal-ledger-build"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def hhmm(t: str) -> str:
    h, m, ap = re.match(r"(\d+):(\d+)\s*([AP])M", t.strip(), re.I).groups()
    h = int(h) % 12 + (12 if ap.upper() == "P" else 0)
    return f"{h:02d}:{m}"


def match(agency: str, title: str):
    for a, prefix, label, key in WANTED:
        if a == agency and title.startswith(prefix):
            return label, key
    return None


def bea(year: int) -> list[dict]:
    page = get(BEA_URL)
    if f"Year {year}" not in text(page):
        sys.exit(f"BEA: {BEA_URL} does not show {year}; use the full schedule page instead")
    out = []
    for row in re.findall(r"<tr class=\"scheduled-releases-type-press\">(.*?)</tr>", page, re.S):
        d = re.search(r'release-date">([A-Za-z]+ \d+)</div>\s*<small[^>]*>([^<]+)</small>', row)
        t = re.search(r'class="release-title[^>]*>(.*?)</td>', row, re.S)
        if not d or not t:
            continue
        title = text(t.group(1))
        m = match("BEA", title)
        if m:
            date = dt.datetime.strptime(f"{d.group(1)} {year}", "%B %d %Y").date()
            out.append({"date": date, "time": hhmm(d.group(2)), "key": m[1], "label": m[0],
                        "release": title, "agency": "BEA"})
    return out


def census(year: int) -> list[dict]:
    page = get(CENSUS_URL)
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 4 or not cells[1].endswith(str(year)):
            continue
        m = match("Census", cells[0])
        if m:
            out.append({"date": dt.datetime.strptime(cells[1], "%B %d, %Y").date(), "time": hhmm(cells[2]),
                        "key": m[1], "label": m[0], "release": f"{cells[0]}, {cells[3]}", "agency": "Census"})
    return out


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    out = ROOT / "planner" / str(year) / "econ_releases.yaml"
    old = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else {}
    kept = [r for r in (old.get("releases") or []) if r["agency"] == "BLS"]
    fetched = bea(year) + census(year)
    uniq = {(r["date"], r["key"], r["label"]): r for r in fetched}  # Census lists each row twice
    rows = sorted(kept + list(uniq.values()), key=lambda r: (r["date"], ORDER.index(r["key"])))
    doc = {"note": "Generated by pipeline/fetch_econ.py (BEA, Census); BLS entries are kept by hand from "
                   "the BLS schedule pages. Times are Eastern. Re-run if an agency revises its schedule.",
           "sources": {"BLS": BLS_PAGES + "{empsit,cpi,ppi,jolts,eci}.htm", "BEA": BEA_URL, "Census": CENSUS_URL},
           "fetched": dt.date.today(),
           "releases": rows}
    out.write_text("# " + doc["note"] + "\n" + yaml.dump(doc, Dumper=Dumper, sort_keys=False, allow_unicode=True,
                                                         width=200),
                   encoding="utf-8", newline="\n")
    counts = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"{len(rows)} releases -> {out}")
    for k, v in counts.items():
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
