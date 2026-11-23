# CLAUDE.md — The Seasonal Ledger

Data-driven trader's planner (PDF) for 2027. Public repo; agents work on it locally and in the cloud.

## Build & check
- `python build.py` (local, has `data/raw/gspc.csv`) or `python build.py --no-stats` (cloud/CI: uses committed `data/stats/2027.json`).
- Typst **0.15.1**, always `--font-path fonts --ignore-system-fonts` (build.py does this). Never depend on system fonts.
- Look at what you changed: `python build.py --png <pages>` and view `build/png/*.png`. A compile without errors is not a check — overflow pushes content onto a new page and breaks the even/odd spread pairing (day page must be even, its review page odd). Page count is currently 148; if it changes unexpectedly, something overflowed.

## Hard rules
1. **No hand-typed statistics anywhere.** Prose in `planner/2027/notes.yaml` quotes numbers only through `{tokens}` (see the header of that file). Templates never compute stats; `pipeline/stats.py` does.
2. **Describe, don't predict.** No causal stories, no "will", no advice. Small samples get their n shown.
3. **Calendar facts need a source** in `planner/2027/calendar.yaml` (NYSE, federalreserve.gov). Don't invent dates. Earnings-season windows are estimates and are labelled so until a confirmed big-bank date replaces `kickoff: null`.
4. Never commit `data/raw/` (S&P price data is not ours to redistribute). Derived stats are fine.
5. The workbook (`pipeline/sheet.py`) must work in Excel **and** Google Sheets: INDEX/MATCH, COUNTIFS,
   SUMIFS, AVERAGEIFS, `_xlfn.MINIFS`, IFERROR only; no XLOOKUP/FILTER/spills, no Excel tables, bounded
   ranges (not `A:A`). Statistics go in as values; formulas are for the journal. Never commit a filled-in copy.
6. Notes text is Typst markup: escape `$ # _ *` and `~` (non-breaking space) when meant literally. `#expr;` eats the semicolon — write `#expr;;`.

## Open work (good tasks for an agent)
- **Week blurbs:** 47 of 52 weeks use the auto blurb from `assemble.py`. Write hand blurbs in `notes.yaml` (`weeks: <n>: {title, blurb, next}`) for notable weeks — FOMC weeks, opex weeks, month-ends, quarter-ends, holiday weeks. Tokens only; events are appended automatically.
- **Earnings:** replace estimated `kickoff` dates once JPM/big banks announce; consider per-season stats on the first two weeks vs. the rest.
- **Verify** the Nov 17 FOMC SEP flag against federalreserve.gov/monetarypolicy/fomccalendars.htm; fill `next_year.first_fomc` once 2028 is published.
- **Treasury auctions:** `python pipeline/fetch_auctions.py` after each quarterly refunding (early Feb, May, Aug 2027) extends `planner/2027/treasury_auctions.yaml`; currently covered through Apr 27. Commit the YAML (public data).
- **Economic calendar** (CPI, jobs report) once BLS publishes its 2027 schedule — add to calendar.yaml with source, then badges.
- Print production: cover art, binding margins (inner/outer), a PDF/X export.
