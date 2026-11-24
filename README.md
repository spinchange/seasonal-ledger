# The Seasonal Ledger

A trader's planner and trade journal for 2027. Every seasonal statistic in it is computed from
S&P 500 history (1950–2025) by the open pipeline in this repo. Nothing in it is investment advice.

**What's inside (~148 pages, US Letter):** cover · the year ahead (presidential cycle, month table) ·
year-at-a-glance market calendar (NYSE holidays, FOMC, opex, Santa Claus Rally, earnings seasons;
VIX expirations; 13F filing deadlines; economic releases (jobs report, CPI, PPI, PCE, GDP, retail sales, housing
starts and more, with release times) and Treasury coupon auctions on the day pages) ·
earnings-season page · annual plan · for each month an opener (stats, trading-day chart, goals) and a
month grid · for each of 52 weeks a day page (per-day history, events) and an ideas/trades/review page,
with an earnings table in reporting season · quarterly reviews · year-end review · my dates (coupons, dividends, maturities) · trade log · methodology.

**The workbook** (`build/seasonal-ledger-2027.xlsx`) holds the same calendar and statistics as the PDF,
with the journal made live: a trade log that calculates risk, P&L, R multiple and status, and picks up each
entry day's history; a review that totals it by setup, month, side and earnings season; and a Today
sheet showing the day, week, month, what's coming up and the next 14 days; and a My Dates sheet for your own
coupons, dividends and maturities (enter the first date and how often it repeats), which then appear on the
calendar and are totalled by month. It opens in Excel and converts to
Google Sheets on upload to Drive. The statistics in it are values computed by the pipeline; the formulas
are only the journal's. Keep your filled-in copy private.

**Calendar files** (`build/seasonal-ledger-2027.ics`, `-history.ics`) import into Google Calendar, Apple
Calendar or Outlook. The first holds the market calendar: closures, FOMC, option and VIX expirations,
13F deadlines, Treasury auctions, estimated earnings seasons, and economic releases at their release time
(Eastern). The second puts each trading day's history on that day (% of years up, average change, n = years
in the sample), so it can be shown or hidden separately. Entries have stable IDs: re-importing a newer
build updates them.

## Build

Requirements: Python 3.11+, [Typst](https://typst.app) 0.15.1. Fonts (Crimson Text, Fira Sans; SIL OFL)
are vendored in `fonts/`.

```sh
pip install -r requirements.txt
python build.py              # -> build/seasonal-ledger-2027.pdf, .xlsx and .ics files
python build.py --fetch      # refresh S&P 500 prices first, then recompute stats
python build.py --no-stats   # build from committed stats only (no price data needed)
python build.py --png 1-9    # also render pages to build/png/ for review
```

Every push builds the PDF and workbook in GitHub Actions; download it from the run's artifacts.

## How it fits together

```
pipeline/fetch.py     ^GSPC daily closes -> data/raw/gspc.csv        (not committed)
pipeline/stats.py     every statistic    -> data/stats/2027.json     (committed)
planner/2027/calendar.yaml   holidays, FOMC, opex overrides, earnings windows (hand-maintained, sourced)
planner/2027/notes.yaml      editorial text; numbers only via {tokens}
planner/2027/econ_releases.yaml      BLS/BEA/Census release dates, from pipeline/fetch_econ.py (BLS part copied by hand)
planner/2027/treasury_auctions.yaml  coupon auctions, from pipeline/fetch_auctions.py (Treasury's tentative schedule)
pipeline/assemble.py  stats + calendar + notes -> build/planner.json
pipeline/sheet.py     build/planner.json -> build/seasonal-ledger-2027.xlsx (workbook)
pipeline/ics.py       build/planner.json -> build/seasonal-ledger-2027.ics, -history.ics (calendar files)
typst/planner.typ     page order;  typst/pages.typ  page layouts;  typst/theme.typ  design tokens
```

The raw price series is not redistributed; derived statistics are. See the methodology page of the
PDF (or `typst/pages.typ`, `methodology`) for exact definitions.

## License

Code: MIT. Fonts: SIL Open Font License (see `fonts/OFL-*.txt`).
