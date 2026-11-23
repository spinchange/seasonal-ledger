"""Write the planner as a workbook: build/seasonal-ledger-<year>.xlsx.

Same source as the PDF (build/planner.json + calendar.yaml), so every statistic
is a value computed by pipeline/stats.py. What the formulas do is the journal:
the trade log, the reviews that total it, and the Today panel. The file opens
in Excel and converts to Google Sheets on upload (Drive: File > Open > Upload),
so it sticks to functions both support: INDEX/MATCH, COUNTIFS, SUMIFS,
AVERAGEIFS, MINIFS, IFERROR. No XLOOKUP/FILTER/spills, no Excel tables.

The workbook written here is an empty template. A copy with trades in it is
private: never commit one.

Usage: python pipeline/sheet.py [year]
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cal import Calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# --- design tokens (match typst/theme.typ) ---------------------------------
BLUE, ORANGE, INK, MUTED = "2F5F9F", "C9822F", "222222", "777777"
FONT = "Arial"
F_BODY = Font(name=FONT, size=10, color=INK)
F_MUTED = Font(name=FONT, size=9, color=MUTED)
F_ITAL = Font(name=FONT, size=9, color=MUTED, italic=True)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=16, bold=True, color=BLUE)
F_H2 = Font(name=FONT, size=12, bold=True, color=BLUE)
F_LABEL = Font(name=FONT, size=10, bold=True, color=INK)
F_BIG = Font(name=FONT, size=14, bold=True, color=INK)
FILL_HEAD = PatternFill("solid", fgColor=BLUE)
FILL_INPUT = PatternFill("solid", fgColor="FFF6CC")      # cells you fill in
FILL_CLOSED = PatternFill("solid", fgColor="E6E6E6")
FILL_FOMC = PatternFill("solid", fgColor="D6E2F3")
FILL_SEASON = PatternFill("solid", fgColor="E3F1E0")
FILL_SANTA = PatternFill("solid", fgColor="F7E6D0")
FILL_TODAY = PatternFill("solid", fgColor="FFE08A")
FILL_AUCTION = PatternFill("solid", fgColor="ECE8F3")
FILL_MINE = PatternFill("solid", fgColor="FBE3EC")
THIN = Side(style="thin", color="D0D0D0")
BOX = Border(bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

PCT0 = "0%"
SIGNED2 = '+0.00%;-0.00%;0.00%'   # avg moves, stored as fractions (0.0013 -> +0.13%)
SIGNED1 = '+0.0%;-0.0%;0.0%'
MONEY = '$#,##0.00;($#,##0.00);-'
DATE = "ddd mmm d"
DATE_Y = "mmm d, yyyy"

CAL_LAST = 366          # last Calendar row; set from the year in main()
TRADE_ROWS = 500          # Trades!5:504
WATCH_ROWS = 60
MY_ROWS, MY_FIRST = 40, 6     # 'My Dates'!6:45 are the inputs
MAX_REPEATS = 12              # monthly is the most frequent repeat: 12 dates a year
SCHED_LAST = 1 + MY_ROWS * MAX_REPEATS   # Schedule!2:481
REPEATS = [("Once", 0), ("Monthly", 1), ("Quarterly", 3), ("Semiannual", 6), ("Annual", 12)]
MY_EVENTS = ["Coupon", "Ex-dividend", "Dividend paid", "Distribution", "Maturity", "Call date", "Other"]
FIRST_TRADE, LAST_TRADE = 5, 5 + TRADE_ROWS - 1
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
HOLIDAY_NAMES = {"mlk": "MLK Day", "presidents": "Presidents' Day", "good_friday": "Good Friday",
                 "memorial": "Memorial Day", "july4": "Independence Day", "labor": "Labor Day",
                 "thanksgiving": "Thanksgiving", "christmas": "Christmas", "new_year": "New Year"}
WINDOW_NAMES = {"before": "Day before", "after": "Day after", "monday_after": "Monday after",
                "week": "Holiday week", "first": "First trading day of the year",
                "last": "Last trading day of the year"}


def num(s) -> float:
    """planner.json carries display strings like '+0.13' / '−0.07'."""
    return float(str(s).replace("−", "-").replace("+", ""))


def plain(s: str) -> str:
    """Strip the Typst markup that notes.yaml prose may carry."""
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"_([^_]+)_", r"\1", s)
    return s.replace("\\", "")


def pct(x):
    return None if x is None else x / 100


def header(ws, row, labels, widths=None, col=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=lab)
        c.font, c.fill = F_HEAD, FILL_HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths):
            ws.column_dimensions[get_column_letter(col + i)].width = w


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    ws.row_dimensions[1].height = 24
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_ITAL


def put(ws, ref, value, font=F_BODY, fmt=None, fill=None, align=None):
    c = ws[ref]
    c.value = value
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if align:
        c.alignment = align
    return c


def style_body(ws, r1, r2, c1, c2):
    for row in ws.iter_rows(min_row=r1, max_row=r2, min_col=c1, max_col=c2):
        for c in row:
            if c.font.name != FONT:
                c.font = F_BODY
            c.border = BOX


# --- data -------------------------------------------------------------------
def load(year: int):
    P = json.loads((ROOT / "build" / "planner.json").read_text(encoding="utf-8"))
    cal = Calendar(year)
    days, weeks = {}, []
    for m in P["months"]:
        for w in m["weeks"]:
            weeks.append(w)
            for d in w["days"]:
                days[dt.date.fromisoformat(d["date"])] = (w["num"], d)
    return P, cal, days, weeks


# --- sheets -----------------------------------------------------------------
def sheet_calendar(wb, P, cal, days):
    ws = wb.create_sheet("Calendar")
    cols = ["Date", "Day", "Week", "Market", "Trading-day slot", "% up", "Avg move", "n (years)",
            "FOMC", "Opex", "Earnings season", "Santa window", "Events", "History", "My notes",
            "Treasury auction", "My dates (from the My Dates sheet)"]
    header(ws, 1, cols, [13, 6, 6, 11, 22, 7, 9, 8, 15, 13, 13, 8, 40, 50, 40, 22, 34])
    ws.freeze_panes = "B2"
    r = 1
    last_week = None
    for d in cal.days:
        r += 1
        wk, rec = days.get(d, (None, None))
        if d.weekday() >= 5:
            wk = last_week
        else:
            last_week = wk
        closed = d in cal.holidays
        ws.cell(r, 1, d).number_format = DATE_Y
        ws.cell(r, 2, d.strftime("%a"))
        ws.cell(r, 3, wk)
        events = []
        if d.weekday() >= 5:
            market = "Weekend"
        elif closed:
            market = "Closed"
            events.append(f"Market closed: {cal.holidays[d]['name']}")
        elif d in cal.early:
            market = "Early close"
        else:
            market = "Open"
        ws.cell(r, 4, market)
        if rec and not rec["closed"]:
            ws.cell(r, 5, rec["slot"])
            ws.cell(r, 6, pct(rec["pct_up"])).number_format = PCT0
            ws.cell(r, 7, num(rec["avg"]) / 100).number_format = SIGNED2
            ws.cell(r, 8, rec["n"])
            events += [b["text"] for b in rec["badges"] if b["kind"] != "santa"]
            ws.cell(r, 14, "; ".join(rec["notes"]) or None)
        f = cal.fomc.get(d)
        if f:
            ws.cell(r, 9, "Strategy meeting" if f["kind"] == "strategy"
                    else "Decision + SEP" if f.get("sep") else "Decision")
        o = cal.opex.get(d)
        if o:
            ws.cell(r, 10, "Opex: quad witching" if o["quad"] else "Opex")
        s = cal.season_for(d)
        if s:
            ws.cell(r, 11, s["quarter"])
        if d in cal.santa:
            ws.cell(r, 12, "Y")
        ws.cell(r, 13, "; ".join(dict.fromkeys(events)) or None)
        ws.cell(r, 15).fill = FILL_INPUT
        if d in cal.auctions:
            ws.cell(r, 16, ", ".join(a["security"] + (" (reopening)" if a.get("reopening") else "")
                                     for a in cal.auctions[d]))
        SD, SL = f"Schedule!$F$2:$F${SCHED_LAST}", f"Schedule!$G$2:$G${SCHED_LAST}"
        cnt = f"COUNTIFS({SD},$A{r})"
        ws.cell(r, 17, f'=IF({cnt}=0,"",INDEX({SL},MATCH($A{r},{SD},0))'
                       f'&IF({cnt}>1," (+"&({cnt}-1)&" more)",""))')
    last = r
    style_body(ws, 2, last, 1, 17)
    for row in ws.iter_rows(min_row=2, max_row=last, min_col=13, max_col=17):
        for c in row:
            c.alignment = WRAP
    rng = f"A2:Q{last}"
    ws.conditional_formatting.add(rng, FormulaRule(formula=["$A2=TODAY()"], fill=FILL_TODAY, stopIfTrue=True))
    ws.conditional_formatting.add(rng, FormulaRule(formula=['OR($D2="Closed",$D2="Weekend")'], fill=FILL_CLOSED))
    ws.conditional_formatting.add(f"I2:I{last}", FormulaRule(formula=['$I2<>""'], fill=FILL_FOMC))
    ws.conditional_formatting.add(f"K2:K{last}", FormulaRule(formula=['$K2<>""'], fill=FILL_SEASON))
    ws.conditional_formatting.add(f"L2:L{last}", FormulaRule(formula=['$L2<>""'], fill=FILL_SANTA))
    ws.conditional_formatting.add(f"P2:P{last}", FormulaRule(formula=['$P2<>""'], fill=FILL_AUCTION))
    ws.conditional_formatting.add(f"Q2:Q{last}", FormulaRule(formula=['$Q2<>""'], fill=FILL_MINE))
    ws.conditional_formatting.add(f"G2:G{last}", ColorScaleRule(
        start_type="num", start_value=-0.004, start_color="E8A5A0",
        mid_type="num", mid_value=0, mid_color="FFFFFF",
        end_type="num", end_value=0.004, end_color="9CC5A1"))
    ws.auto_filter.ref = f"A1:Q{last}"
    return last


def sheet_weeks(wb, P, weeks):
    ws = wb.create_sheet("Weeks")
    cols = ["Week", "Monday", "Friday", "Title", "What history shows", "% up", "Avg", "Median",
            "Rank (of 52)", "n", "Earnings season", "Events", "My plan for the week"]
    header(ws, 1, cols, [6, 11, 11, 28, 70, 7, 8, 8, 8, 5, 11, 45, 45])
    ws.freeze_panes = "B2"
    for i, w in enumerate(weeks, start=2):
        ds = [dt.date.fromisoformat(d["date"]) for d in w["days"]]
        st = w["stat"]
        ev = [b["text"] for d in w["days"] for b in d.get("badges", []) if b["kind"] != "santa"]
        ev += [d["closed_text"] for d in w["days"] if d.get("closed_text")]
        vals = [w["num"], ds[0], ds[-1], plain(w["title"]), plain(w["blurb"]), pct(st["pct_up"]),
                st["avg"] / 100, st["median"] / 100, st["rank"], st["n"], w.get("season"),
                "; ".join(dict.fromkeys(ev)) or None, None]
        for j, v in enumerate(vals, start=1):
            ws.cell(i, j, v)
        ws.cell(i, 2).number_format = ws.cell(i, 3).number_format = DATE
        ws.cell(i, 6).number_format = PCT0
        ws.cell(i, 7).number_format = ws.cell(i, 8).number_format = SIGNED2
        ws.cell(i, 13).fill = FILL_INPUT
    last = 1 + len(weeks)
    style_body(ws, 2, last, 1, 13)
    for row in ws.iter_rows(min_row=2, max_row=last, min_col=4, max_col=13):
        for c in row:
            c.alignment = WRAP
    ws.conditional_formatting.add(f"A2:M{last}", FormulaRule(
        formula=["AND(TODAY()>=$B2,TODAY()<=$C2+2)"], fill=FILL_TODAY))
    ws.conditional_formatting.add(f"G2:G{last}", ColorScaleRule(
        start_type="num", start_value=-0.006, start_color="E8A5A0",
        mid_type="num", mid_value=0, mid_color="FFFFFF",
        end_type="num", end_value=0.006, end_color="9CC5A1"))
    ws.auto_filter.ref = f"A1:M{last}"


def sheet_months(wb, P):
    ws = wb.create_sheet("Months")
    S = P["stats"]["months"]
    cols = ["#", "Month", "Sessions in 2027", "Avg (all years)", "% up", "Median", "Best", "Worst",
            "Pre-election avg", "% up", "n", "Last-20 avg", "% up", "What history shows",
            "My goal", "Closed trades", "Realized P&L", "My scheduled payments"]
    header(ws, 1, cols, [4, 11, 9, 9, 7, 8, 14, 14, 9, 7, 5, 9, 7, 70, 35, 9, 12, 12])
    ws.freeze_panes = "C2"
    for i, m in enumerate(P["months"], start=2):
        s = S[str(m["m"])]
        a, pre, l20 = s["all"], s["pre"], s["last20"]
        vals = [m["m"], m["name"], m["sessions"], a["avg"] / 100, pct(a["pct_up"]), a["median"] / 100,
                f"{a['best']['chg']:+.1f}% ({a['best']['year']})",
                f"{a['worst']['chg']:+.1f}% ({a['worst']['year']})".replace("-", "−"),
                pre["avg"] / 100, pct(pre["pct_up"]), pre["n"], l20["avg"] / 100, pct(l20["pct_up"]),
                plain(m["blurb"]), None,
                f'=COUNTIFS(Trades!$R${FIRST_TRADE}:$R${LAST_TRADE},A{i},'
                f'Trades!$Q${FIRST_TRADE}:$Q${LAST_TRADE},"<>Open")',
                f"=SUMIFS(Trades!$M${FIRST_TRADE}:$M${LAST_TRADE},Trades!$R${FIRST_TRADE}:$R${LAST_TRADE},A{i})"]
        for j, v in enumerate(vals, start=1):
            ws.cell(i, j, v)
        for j in (4, 6, 9, 12):
            ws.cell(i, j).number_format = SIGNED2
        for j in (5, 10, 13):
            ws.cell(i, j).number_format = PCT0
        ws.cell(i, 15).fill = FILL_INPUT
        ws.cell(i, 17).number_format = MONEY
        ws.cell(i, 18, f"=SUMIFS(Schedule!$H$2:$H${SCHED_LAST},Schedule!$I$2:$I${SCHED_LAST},A{i})"
                ).number_format = MONEY
    style_body(ws, 2, 13, 1, 18)
    for row in ws.iter_rows(min_row=2, max_row=13, min_col=14, max_col=15):
        for c in row:
            c.alignment = WRAP
    ws.conditional_formatting.add("A2:R13", FormulaRule(formula=["MONTH(TODAY())=$A2"], fill=FILL_TODAY))
    put(ws, "A15", "Pre-election = years divisible by 4 with remainder 3 (2027 is one). "
        "Best/worst are calendar-month changes. Closed trades and P&L total the Trades sheet by close month.",
        F_ITAL)


def sheet_reference(wb, P):
    ws = wb.create_sheet("Reference")
    S = P["stats"]
    title(ws, f"The year in context, {P['window']}", f"{S['meta']['series']}. "
          f"{S['meta']['n_years']} years. Describes the past; predicts nothing.")
    for col, w in zip("ABCDEFG", [34, 10, 9, 9, 9, 16, 30]):
        ws.column_dimensions[col].width = w
    r = 4

    def table(head, rows, fmts):
        nonlocal r
        header(ws, r, head)
        for row in rows:
            r += 1
            for j, v in enumerate(row, start=1):
                c = ws.cell(r, j, v)
                c.font, c.border = F_BODY, BOX
                if fmts[j - 1]:
                    c.number_format = fmts[j - 1]
        r += 2

    def h2(text):
        nonlocal r
        put(ws, f"A{r}", text, F_H2)
        r += 1

    h2("Presidential cycle (calendar-year change)")
    names = {1: "Post-election", 2: "Midterm", 3: "Pre-election (2027)", 4: "Election"}
    table(["Year of cycle", "Avg", "% up", "Median", "n", "Range"],
          [[names[k], v["avg"] / 100, pct(v["pct_up"]), v["median"] / 100, v["n"],
            f"{v['first']}–{v['last']}"] for k, v in ((int(k), v) for k, v in S["cycle"].items())],
          [None, SIGNED2, PCT0, SIGNED2, None, None])
    y = S["years"]["all"]
    table(["All years", "Avg", "% up", "Median", "n", "Best / worst"],
          [["Calendar-year change", y["avg"] / 100, pct(y["pct_up"]), y["median"] / 100, y["n"],
            f"{y['best']['chg']:+.1f}% ({y['best']['year']}) / {y['worst']['chg']:+.1f}% ({y['worst']['year']})"]],
          [None, SIGNED2, PCT0, SIGNED2, None, None])

    h2("Best and worst six months")
    six = S["six"]
    table(["Period", "Avg", "% up", "Median", "n", "$10,000 grew to"],
          [["Nov–Apr (best six)", six["best"]["avg"] / 100, pct(six["best"]["pct_up"]),
            six["best"]["median"] / 100, six["best"]["n"], six["best"]["growth10k"]],
           ["May–Oct (worst six)", six["worst"]["avg"] / 100, pct(six["worst"]["pct_up"]),
            six["worst"]["median"] / 100, six["worst"]["n"], six["worst"]["growth10k"]]],
          [None, SIGNED2, PCT0, SIGNED2, None, "$#,##0"])

    h2("January Barometer and Santa Claus Rally")
    jb, sa = S["jan_barometer"], S["santa"]
    table(["Measure", "Avg", "% up", "Median", "n", "Note"],
          [["January Barometer: January's sign matched the year's", None, pct(jb["pct"]), None, jb["n"],
            f"{jb['hits']} of {jb['n']} years"],
           ["Santa Claus Rally (last 5 + first 2 sessions)", sa["avg"] / 100, pct(sa["pct_up"]),
            sa["median"] / 100, sa["n"], None],
           ["Following year, after a Santa rally", sa["after_success"]["avg"] / 100,
            pct(sa["after_success"]["pct_up"]), sa["after_success"]["median"] / 100, sa["after_success"]["n"], None],
           ["Following year, after no Santa rally", sa["after_fail"]["avg"] / 100,
            pct(sa["after_fail"]["pct_up"]), sa["after_fail"]["median"] / 100, sa["after_fail"]["n"],
            "small sample"]],
          [None, SIGNED2, PCT0, SIGNED2, None, None])

    h2("Around market holidays (daily change; only years the market closed on a weekday)")
    rows = []
    for k, sub in S["holidays"].items():
        for wk, v in sub.items():
            if isinstance(v, dict) and v.get("n"):
                rows.append([f"{HOLIDAY_NAMES.get(k, k)}: {WINDOW_NAMES.get(wk, wk)}", v["avg"] / 100,
                             pct(v["pct_up"]), v["median"] / 100, v["n"], None])
    table(["Window", "Avg", "% up", "Median", "n", ""], rows, [None, SIGNED2, PCT0, SIGNED2, None, None])

    h2("Earnings seasons: average daily change")
    E = S["earnings"]
    table(["Days", "Avg (bp)", "% up", "Median", "n (days)", "Since 1995 (bp)"],
          [["In season", E["daily_in"]["avg_bp"], pct(E["daily_in"]["pct_up"]), E["daily_in"]["median"] / 100,
            E["daily_in"]["n"], E["daily_in_1995"]["avg_bp"]],
           ["Off season", E["daily_out"]["avg_bp"], pct(E["daily_out"]["pct_up"]),
            E["daily_out"]["median"] / 100, E["daily_out"]["n"], E["daily_out_1995"]["avg_bp"]]],
          [None, "0.0", PCT0, SIGNED2, "#,##0", "0.0"])
    put(ws, f"A{r}", "bp = basis points (0.01%). Season windows are the 2027 estimated dates, "
        "measured on the same calendar dates in every year.", F_ITAL)


def sheet_earnings(wb, P, cal):
    ws = wb.create_sheet("Earnings")
    title(ws, f"Earnings seasons {P['year']}", plain(P["earnings_note"]))
    header(ws, 4, ["Season", "Opens", "Closes", "Status", "% up", "Avg", "Median", "n"],
           [14, 12, 12, 30, 9, 10, 9, 6, 9, 30])
    for i, s in enumerate(cal.seasons, start=5):
        st = P["stats"]["earnings"]["seasons"][s["quarter"]]
        status = "Kickoff confirmed" if s.get("kickoff") else "Estimated window"
        vals = [s["quarter"], s["start"], s["end"], status, pct(st["pct_up"]), st["avg"] / 100,
                st["median"] / 100, st["n"]]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(i, j, v)
            c.font, c.border = F_BODY, BOX
        ws.cell(i, 2).number_format = ws.cell(i, 3).number_format = DATE_Y
        ws.cell(i, 5).number_format = PCT0
        ws.cell(i, 6).number_format = ws.cell(i, 7).number_format = SIGNED2
    put(ws, "A9", "% up / avg / median: S&P 500 change over the same calendar window in each year.", F_ITAL)

    put(ws, "A11", "Watchlist report dates", F_H2)
    cols = ["Ticker", "Company", "Season", "Report date", "Timing", "Week", "EPS est.", "EPS actual",
            "Surprise", "Next-day move", "Notes"]
    header(ws, 12, cols)
    for col, w in zip("ABCDEFGHIJK", [9, 22, 11, 13, 8, 6, 9, 9, 9, 10, 40]):
        ws.column_dimensions[col].width = w
    r1, r2 = 13, 12 + WATCH_ROWS
    for r in range(r1, r2 + 1):
        for j in (1, 2, 3, 4, 5, 7, 8, 10, 11):
            ws.cell(r, j).fill = FILL_INPUT
        ws.cell(r, 4).number_format = DATE
        ws.cell(r, 6, f'=IF(D{r}="","",IFERROR(INDEX(Calendar!$C$2:$C${CAL_LAST},MATCH(D{r},Calendar!$A$2:$A${CAL_LAST},0)),""))')
        ws.cell(r, 9, f'=IF(OR(G{r}="",H{r}="",G{r}=0),"",(H{r}-G{r})/ABS(G{r}))').number_format = SIGNED1
        ws.cell(r, 10).number_format = SIGNED1
    style_body(ws, r1, r2, 1, 11)
    ws.freeze_panes = "B13"
    dv = DataValidation(type="list", formula1=f"=$A$5:$A${4 + len(cal.seasons)}", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"C{r1}:C{r2}")
    dv2 = DataValidation(type="list", formula1='"BMO,AMC"', allow_blank=True)
    ws.add_data_validation(dv2)
    dv2.add(f"E{r1}:E{r2}")
    dv3 = DataValidation(type="date", operator="between", formula1="DATE(2026,12,1)",
                         formula2="DATE(2028,1,31)", allow_blank=True)
    ws.add_data_validation(dv3)
    dv3.add(f"D{r1}:D{r2}")
    ws.conditional_formatting.add(f"A{r1}:K{r2}", FormulaRule(
        formula=[f"AND($D{r1}<>\"\",$D{r1}>=TODAY(),$D{r1}<=TODAY()+7)"], fill=FILL_TODAY))


def sheet_lists(wb):
    ws = wb.create_sheet("Lists")
    title(ws, "Lists", "Edit the yellow cells. Setup tags feed the Trades dropdown and the Review.")
    header(ws, 4, ["Setup tags"], [26])
    tags = ["Breakout", "Pullback", "Earnings", "Seasonal", "Mean reversion", "Trend follow", "Other"]
    for i in range(30):
        c = ws.cell(5 + i, 1, tags[i] if i < len(tags) else None)
        c.fill, c.font, c.border = FILL_INPUT, F_BODY, BOX
    header(ws, 4, ["Repeats", "Months apart"], [14, 13], col=3)
    for i, (name, m) in enumerate(REPEATS, start=5):
        ws.cell(i, 3, name).font = F_BODY
        ws.cell(i, 4, m).font = F_BODY
    header(ws, 4, ["My date kinds"], [18], col=6)
    for i in range(5, 20):
        c = ws.cell(i, 6, MY_EVENTS[i - 5] if i - 5 < len(MY_EVENTS) else None)
        c.fill, c.font, c.border = FILL_INPUT, F_BODY, BOX
    return 5


def sheet_trades(wb, tag_first):
    ws = wb.create_sheet("Trades")
    title(ws, "Trade log", "Yellow columns are yours to fill; the rest calculate. "
          "Shares are positive for both sides; Side decides the sign.")
    inputs = ["Open date", "Ticker", "Side", "Setup", "Shares", "Entry", "Stop", "Target",
              "Close date", "Exit", "Fees"]
    calc = ["Risk $", "P&L $", "R multiple", "Return", "Days held", "Status", "Close month",
            "Entry day: % up", "Entry week", "In earnings season"]
    cols = inputs + calc + ["Notes"]
    header(ws, 4, cols, [11, 8, 7, 14, 8, 9, 9, 9, 11, 9, 7, 10, 11, 8, 8, 7, 7, 7, 8, 7, 9, 40])
    for j in range(1, len(inputs) + 1):
        ws.cell(3, j).fill = FILL_INPUT
    put(ws, "A3", "Inputs →", F_MUTED, fill=FILL_INPUT)
    put(ws, "L3", "Calculated →", F_MUTED)
    ws.freeze_panes = "C5"
    for r in range(FIRST_TRADE, LAST_TRADE + 1):
        for j in list(range(1, 12)) + [22]:
            ws.cell(r, j).fill = FILL_INPUT
        ws.cell(r, 1).number_format = ws.cell(r, 9).number_format = DATE
        for j in (6, 7, 8, 10):
            ws.cell(r, j).number_format = "0.00"
        ws.cell(r, 11).number_format = "0.00"
        f = {
            12: f'=IF(OR(E{r}="",F{r}="",G{r}=""),"",ABS(F{r}-G{r})*E{r})',
            13: f'=IF(OR(J{r}="",E{r}="",F{r}=""),"",IF(C{r}="Short",-1,1)*(J{r}-F{r})*E{r}-N(K{r}))',
            14: f'=IF(OR(M{r}="",L{r}="",L{r}=0),"",M{r}/L{r})',
            15: f'=IF(OR(M{r}="",F{r}=0),"",M{r}/(F{r}*E{r}))',
            16: f'=IF(OR(A{r}="",I{r}=""),"",I{r}-A{r})',
            17: f'=IF(B{r}="","",IF(J{r}="","Open",IF(M{r}>0,"Win",IF(M{r}<0,"Loss","Flat"))))',
            18: f'=IF(OR(I{r}="",J{r}=""),"",MONTH(I{r}))',
            19: f'=IF(A{r}="","",IFERROR(INDEX(Calendar!$F$2:$F${CAL_LAST},MATCH(A{r},Calendar!$A$2:$A${CAL_LAST},0)),""))',
            20: f'=IF(A{r}="","",IFERROR(INDEX(Calendar!$C$2:$C${CAL_LAST},MATCH(A{r},Calendar!$A$2:$A${CAL_LAST},0)),""))',
            21: f'=IF(A{r}="","",IFERROR(IF(INDEX(Calendar!$K$2:$K${CAL_LAST},MATCH(A{r},Calendar!$A$2:$A${CAL_LAST},0))="","No","Yes"),""))',
        }
        for j, v in f.items():
            ws.cell(r, j, v)
        ws.cell(r, 12).number_format = ws.cell(r, 13).number_format = MONEY
        ws.cell(r, 14).number_format = '+0.00"R";-0.00"R";0.00"R"'
        ws.cell(r, 15).number_format = SIGNED1
        ws.cell(r, 19).number_format = PCT0
    style_body(ws, FIRST_TRADE, LAST_TRADE, 1, 22)
    rng = f"A{FIRST_TRADE}:V{LAST_TRADE}"
    ws.conditional_formatting.add(f"M{FIRST_TRADE}:N{LAST_TRADE}", FormulaRule(
        formula=[f'AND(ISNUMBER($M{FIRST_TRADE}),$M{FIRST_TRADE}<0)'], font=Font(name=FONT, color="B03A2E")))
    ws.conditional_formatting.add(f"M{FIRST_TRADE}:N{LAST_TRADE}", FormulaRule(
        formula=[f'AND(ISNUMBER($M{FIRST_TRADE}),$M{FIRST_TRADE}>0)'], font=Font(name=FONT, color="2E7D32")))
    ws.conditional_formatting.add(rng, FormulaRule(
        formula=[f'$Q{FIRST_TRADE}="Open"'], fill=PatternFill("solid", fgColor="EEF3FA")))
    tr = f"{FIRST_TRADE}:{LAST_TRADE}"
    side = DataValidation(type="list", formula1='"Long,Short"', allow_blank=True)
    setup = DataValidation(type="list", formula1=f"=Lists!$A${tag_first}:$A${tag_first + 29}", allow_blank=True)
    pos = DataValidation(type="decimal", operator="greaterThan", formula1="0", allow_blank=True,
                         error="Shares and prices are positive; use Side for shorts.", showErrorMessage=True)
    dates = DataValidation(type="date", operator="between", formula1="DATE(2026,1,1)",
                           formula2="DATE(2028,12,31)", allow_blank=True)
    for dv in (side, setup, pos, dates):
        ws.add_data_validation(dv)
    a, b = tr.split(":")
    side.add(f"C{a}:C{b}")
    setup.add(f"D{a}:D{b}")
    pos.add(f"E{a}:H{b}")
    pos.add(f"J{a}:J{b}")
    dates.add(f"A{a}:A{b}")
    dates.add(f"I{a}:I{b}")
    ws.auto_filter.ref = f"A4:V{LAST_TRADE}"


def sheet_review(wb, tag_first):
    ws = wb.create_sheet("Review")
    title(ws, "Review", "Everything here totals the Trades sheet. Closed = has an exit price.")
    for col, w in zip("ABCDEFGHIJ", [24, 10, 8, 8, 9, 13, 11, 11, 9, 14]):
        ws.column_dimensions[col].width = w
    T = lambda c: f"Trades!${c}${FIRST_TRADE}:${c}${LAST_TRADE}"  # noqa: E731
    PNL, R, ST, DAYS = T("M"), T("N"), T("Q"), T("P")
    closed = f'(COUNTIFS({ST},"Win")+COUNTIFS({ST},"Loss")+COUNTIFS({ST},"Flat"))'

    put(ws, "A4", "The year so far", F_H2)
    summary = [
        ("Closed trades", f"={closed}", "0"),
        ("Open trades", f'=COUNTIFS({ST},"Open")', "0"),
        ("Wins", f'=COUNTIFS({ST},"Win")', "0"),
        ("Losses", f'=COUNTIFS({ST},"Loss")', "0"),
        ("Win rate", f'=IFERROR(B7/B5,"")', PCT0),
        ("Net P&L", f"=SUM({PNL})", MONEY),
        ("Average win", f'=IFERROR(AVERAGEIFS({PNL},{ST},"Win"),"")', MONEY),
        ("Average loss", f'=IFERROR(AVERAGEIFS({PNL},{ST},"Loss"),"")', MONEY),
        ("Payoff ratio (avg win / avg loss)", '=IFERROR(B11/ABS(B12),"")', '0.00"x"'),
        ("Average R", f'=IFERROR(AVERAGE({R}),"")', '+0.00"R";-0.00"R";0.00"R"'),
        ("P&L per closed trade", '=IFERROR(B10/B5,"")', MONEY),
        ("Largest win", f'=IF(COUNTIFS({ST},"Win")=0,"",MAX({PNL}))', MONEY),
        ("Largest loss", f'=IF(COUNTIFS({ST},"Loss")=0,"",MIN({PNL}))', MONEY),
        ("Average days held", f'=IFERROR(AVERAGE({DAYS}),"")', "0.0"),
    ]
    for i, (lab, f, fmt) in enumerate(summary, start=5):
        put(ws, f"A{i}", lab, F_LABEL)
        put(ws, f"B{i}", f, F_BODY, fmt)
        ws[f"A{i}"].border = ws[f"B{i}"].border = BOX

    def breakdown(r, heading, key_head, keys, extra=None):
        """keys: (label or label formula, criteria) where criteria is 'range,crit[,range,crit]'."""
        put(ws, f"A{r}", heading, F_H2)
        heads = [key_head, "Closed", "Wins", "Win rate", "Net P&L", "Avg R", "Avg win", "Avg loss"]
        if extra:
            heads.append(extra[0])
        header(ws, r + 1, heads)
        for n, (lab, crit) in enumerate(keys):
            i = r + 2 + n
            k = f"$A{i}"
            cnt = lambda s: f'COUNTIFS({crit},{ST},"{s}")'  # noqa: E731
            row = [lab,
                   f'=IF({k}="","",{cnt("Win")}+{cnt("Loss")}+{cnt("Flat")})',
                   f'=IF({k}="","",{cnt("Win")})',
                   f'=IF(OR({k}="",N(B{i})=0),"",C{i}/B{i})',
                   f'=IF({k}="","",SUMIFS({PNL},{crit}))',
                   f'=IF({k}="","",IFERROR(AVERAGEIFS({R},{crit}),""))',
                   f'=IF({k}="","",IFERROR(AVERAGEIFS({PNL},{crit},{ST},"Win"),""))',
                   f'=IF({k}="","",IFERROR(AVERAGEIFS({PNL},{crit},{ST},"Loss"),""))']
            if extra:
                row.append(extra[1](n))
            for j, v in enumerate(row, start=1):
                c = ws.cell(i, j, v)
                c.font, c.border = (F_LABEL if j == 1 else F_BODY), BOX
            ws.cell(i, 4).number_format = PCT0
            for j in (5, 7, 8):
                ws.cell(i, j).number_format = MONEY
            ws.cell(i, 6).number_format = '+0.00"R";-0.00"R";0.00"R"'
            if extra:
                ws.cell(i, 9).number_format = extra[2]
        return r + 2 + len(keys) + 1

    r = 20
    tags = [(f'=IF(Lists!$A${tag_first + n}="","",Lists!$A${tag_first + n})', f"{T('D')},$A{r + 2 + n}")
            for n in range(30)]
    r = breakdown(r, "By setup", "Setup", tags)
    r = breakdown(r, "By close month", "Month", [(MONTHS[n], f"{T('R')},{n + 1}") for n in range(12)],
                  extra=("S&P avg month", lambda n: f"=Months!D{n + 2}", SIGNED2))
    r = breakdown(r, "By side", "Side", [(x, f'{T("C")},"{x}"') for x in ("Long", "Short")])
    r = breakdown(r, "Entered in earnings season", "In season",
                  [(x, f'{T("U")},"{x}"') for x in ("Yes", "No")])
    S_ = T("S")
    r = breakdown(r, "By the entry day's history", "Entry day",
                  [("Up ≥ 60% of years", f'{S_},">=0.6"'),
                   ("Up 50–59% of years", f'{S_},">=0.5",{S_},"<0.6"'),
                   ("Up < 50% of years", f'{S_},"<0.5"')])
    put(ws, f"A{r}", "Comparisons with history describe; they don't test anything. "
        "Small counts mean little.", F_ITAL)


def sheet_today(wb, P, cal_last):
    ws = wb.active
    ws.title = "Today"
    title(ws, f"The Seasonal Ledger {P['year']}: today",
          "Shows today during 2027; before then it shows the first trading day. Type a date in the "
          "yellow cell to look at any other day.")
    for col, w in zip("ABCDEFGH", [26, 16, 12, 26, 12, 12, 40, 4]):
        ws.column_dimensions[col].width = w
    CAL = lambda c: f"Calendar!${c}$2:${c}${cal_last}"  # noqa: E731
    put(ws, "A4", "Look up a date (optional)", F_LABEL)
    put(ws, "B4", None, F_BODY, DATE_Y, FILL_INPUT)
    put(ws, "A5", "Showing", F_LABEL)
    in_year = f"AND(TODAY()>=DATE({P['year']},1,1),TODAY()<=DATE({P['year']},12,31))"
    first_td = next(cal_days_iter(P))
    put(ws, "B5", f'=IF(B4<>"",B4,IF({in_year},TODAY(),DATE({first_td.year},{first_td.month},{first_td.day})))',
        F_BIG, "dddd, mmm d, yyyy")
    put(ws, "D5", f'=IF(B4<>"","your date",IF({in_year},"today","{P["year"]} hasn\'t started"))', F_ITAL)
    # helper: row of the date in the Calendar range (hidden column I)
    put(ws, "I5", f"=IFERROR(MATCH(B5,{CAL('A')},0),\"\")", F_MUTED)
    ws.column_dimensions["I"].hidden = True
    at = lambda c: f'=IF($I$5="","",INDEX({CAL(c)},$I$5)&"")'  # noqa: E731
    atn = lambda c: f'=IF($I$5="","",IF(INDEX({CAL(c)},$I$5)="","",INDEX({CAL(c)},$I$5)))'  # noqa: E731

    put(ws, "A7", "The day", F_H2)
    day = [("Market", at("D"), None), ("Trading-day slot", at("E"), None),
           ("Up in this slot", atn("F"), PCT0), ("Average move", atn("G"), SIGNED2),
           ("Years of data (n)", atn("H"), "0"), ("Events", at("M"), None),
           ("Treasury auction", at("P"), None), ("My dates", at("Q"), None),
           ("History", at("N"), None), ("My notes (Calendar sheet)", at("O"), None)]
    for i, (lab, f, fmt) in enumerate(day, start=8):
        put(ws, f"A{i}", lab, F_LABEL)
        put(ws, f"B{i}", f, F_BODY, fmt, align=Alignment(wrap_text=True, vertical="top"))
        ws.merge_cells(f"B{i}:G{i}")
    for i in (13, 16):
        ws.row_dimensions[i].height = 28

    put(ws, "A19", "The week", F_H2)
    put(ws, "I19", '=IF($I$5="","",INDEX(' + CAL("C") + ',$I$5))', F_MUTED)
    wk = lambda c: f'=IF(N($I$19)=0,"",IFERROR(INDEX(Weeks!${c}$2:${c}$53,MATCH($I$19,Weeks!$A$2:$A$53,0)),""))'  # noqa: E731
    week = [("Week", wk("A"), "0"), ("Title", wk("D"), None), ("Up in this week", wk("F"), PCT0),
            ("Average week", wk("G"), SIGNED2), ("Rank of 52", wk("I"), "0"), ("Events", wk("L"), None),
            ("My plan (Weeks sheet)", wk("M"), None)]
    for i, (lab, f, fmt) in enumerate(week, start=20):
        put(ws, f"A{i}", lab, F_LABEL)
        put(ws, f"B{i}", f, F_BODY, fmt, align=Alignment(wrap_text=True, vertical="top"))
        ws.merge_cells(f"B{i}:G{i}")
    ws.row_dimensions[25].height = 28

    put(ws, "A28", "The month", F_H2)
    mo = lambda c: f'=IF($B$5="","",INDEX(Months!${c}$2:${c}$13,MONTH($B$5)))'  # noqa: E731
    month = [("Month", mo("B"), None), ("Average (all years)", mo("D"), SIGNED2), ("Up", mo("E"), PCT0),
             ("Pre-election years", mo("I"), SIGNED2), ("Closed trades so far", mo("P"), "0"),
             ("Realized P&L", mo("Q"), MONEY), ("My scheduled payments", mo("R"), MONEY)]
    for i, (lab, f, fmt) in enumerate(month, start=29):
        put(ws, f"A{i}", lab, F_LABEL)
        put(ws, f"B{i}", f, F_BODY, fmt)

    put(ws, "D28", "Coming up", F_H2)
    nxt = lambda crit_col, crit: (  # noqa: E731
        f'=IFERROR(1/(1/_xlfn.MINIFS({CAL("A")},{CAL(crit_col)},{crit},{CAL("A")},">="&$B$5)),"none left")')
    upcoming = [("FOMC decision", nxt("I", '"Decision*"')),
                ("Options expiration", nxt("J", '"Opex*"')),
                ("Market holiday", nxt("D", '"Closed"')),
                ("Earnings season opens",
                 f'=IFERROR(1/(1/_xlfn.MINIFS(Earnings!$B$5:$B$8,Earnings!$B$5:$B$8,">="&$B$5)),"none left")'),
                ("Santa Claus Rally window", nxt("L", '"Y"')),
                ("Treasury coupon auction", nxt("P", '"*-yr*"')),
                ("My next date",
                 f'=IFERROR(1/(1/_xlfn.MINIFS(Schedule!$F$2:$F${SCHED_LAST},Schedule!$F$2:$F${SCHED_LAST},'
                 f'">="&$B$5)),"none")')]
    for i, (lab, f) in enumerate(upcoming, start=29):
        put(ws, f"D{i}", lab, F_LABEL)
        put(ws, f"E{i}", f, F_BODY, DATE)
        put(ws, f"F{i}", f'=IF(ISNUMBER(E{i}),E{i}-$B$5&" days","")', F_MUTED)
    put(ws, "G34", f'=IF(ISNUMBER(E34),INDEX({CAL("P")},MATCH(E34,{CAL("A")},0)),"")', F_MUTED)
    put(ws, "G35", f'=IF(ISNUMBER(E35),INDEX({CAL("Q")},MATCH(E35,{CAL("A")},0)),"")', F_MUTED)

    put(ws, "A37", "The next 14 days", F_H2)
    header(ws, 38, ["Date", "Market", "Up in slot", "Avg move", "My dates", "", "Events"])
    for k in range(14):
        i = 39 + k
        idx = f"$I$5+{k}"
        g = lambda c: f'=IF(OR($I$5="",{idx}>{cal_last - 1}),"",INDEX({CAL(c)},{idx}))'  # noqa: E731
        put(ws, f"A{i}", g("A"), F_BODY, DATE)
        put(ws, f"B{i}", g("D"))
        put(ws, f"C{i}", f'=IF(OR($I$5="",{idx}>{cal_last - 1}),"",IF(INDEX({CAL("F")},{idx})="","",'
            f'INDEX({CAL("F")},{idx})))', F_BODY, PCT0)
        put(ws, f"D{i}", f'=IF(OR($I$5="",{idx}>{cal_last - 1}),"",IF(INDEX({CAL("G")},{idx})="","",'
            f'INDEX({CAL("G")},{idx})))', F_BODY, SIGNED2)
        put(ws, f"E{i}", f'=IF(OR($I$5="",{idx}>{cal_last - 1}),"",INDEX({CAL("Q")},{idx})&"")', F_BODY)
        ws.merge_cells(f"E{i}:F{i}")
        put(ws, f"G{i}", f'=IF(OR($I$5="",{idx}>{cal_last - 1}),"",INDEX({CAL("M")},{idx})&"")', F_BODY)
        for c in "ABCDEFG":
            ws[f"{c}{i}"].border = BOX
    ws.conditional_formatting.add("A39:G52", FormulaRule(
        formula=['OR($B39="Closed",$B39="Weekend")'], fill=FILL_CLOSED))
    ws.conditional_formatting.add("A39:G52", FormulaRule(formula=["$A39=$B$5"], fill=FILL_TODAY))
    put(ws, "A54", f"Statistics: {P['stats']['meta']['series']}, {P['window']}. "
        "They describe the past and predict nothing. Not investment advice.", F_ITAL)


def sheet_mydates(wb, year):
    """Your own securities: coupons, dividends, maturities. One row per stream; repeats expand on Schedule."""
    ws = wb.create_sheet("My Dates")
    title(ws, "My dates: coupons, dividends, maturities",
          "One row per payment stream. Give the first date in the year and how often it repeats; "
          "the Schedule sheet lists every date, and they appear on the Calendar and Today sheets.")
    put(ws, "A3", "Example: UST 4.25% 2031 | Coupon | Feb 15, 2027 | Semiannual | Feb 15, 2031 | "
        "2,125.00   ·   XYZ | Ex-dividend | Mar 10, 2027 | Quarterly | (blank) | 48.00", F_ITAL)
    put(ws, "A4", "Dates are the scheduled ones: a payment due on a weekend or holiday usually arrives the "
        "next business day. Ex-dividend dates after the first are a guide until the company declares them.",
        F_ITAL)
    cols = ["Security", "What", f"First date in {year}", "Repeats", "Last date (optional)",
            "Amount per payment", "Notes", f"Dates in {year}", f"Total {year}"]
    header(ws, 5, cols, [24, 14, 14, 12, 14, 13, 36, 9, 12])
    ws.freeze_panes = f"B{MY_FIRST}"
    last = MY_FIRST + MY_ROWS - 1
    for r in range(MY_FIRST, last + 1):
        for j in range(1, 8):
            ws.cell(r, j).fill = FILL_INPUT
        ws.cell(r, 3).number_format = ws.cell(r, 5).number_format = DATE_Y
        ws.cell(r, 6).number_format = MONEY
        n = r - MY_FIRST + 1
        ws.cell(r, 8, f'=IF(A{r}="","",COUNTIFS(Schedule!$B$2:$B${SCHED_LAST},{n},'
                      f'Schedule!$F$2:$F${SCHED_LAST},">0"))')
        ws.cell(r, 9, f'=IF(A{r}="","",SUMIFS(Schedule!$H$2:$H${SCHED_LAST},Schedule!$B$2:$B${SCHED_LAST},{n}))'
                ).number_format = MONEY
    style_body(ws, MY_FIRST, last, 1, 9)
    put(ws, f"G{last + 2}", "Total scheduled", F_LABEL)
    put(ws, f"I{last + 2}", f"=SUM(I{MY_FIRST}:I{last})", F_LABEL, MONEY)
    what = DataValidation(type="list", formula1="=Lists!$F$5:$F$19", allow_blank=True)
    rep = DataValidation(type="list", formula1=f"=Lists!$C$5:$C${4 + len(REPEATS)}", allow_blank=True)
    dates = DataValidation(type="date", operator="between", formula1="DATE(2000,1,1)",
                           formula2="DATE(2100,12,31)", allow_blank=True)
    for dv in (what, rep, dates):
        ws.add_data_validation(dv)
    what.add(f"B{MY_FIRST}:B{last}")
    rep.add(f"D{MY_FIRST}:D{last}")
    dates.add(f"C{MY_FIRST}:C{last}")
    dates.add(f"E{MY_FIRST}:E{last}")


def sheet_schedule(wb, year):
    """Every date the My Dates rows produce in the year: entry n, repeat k -> EDATE(first, k * months)."""
    ws = wb.create_sheet("Schedule")
    title_row = ["Repeat", "Entry", "First date", "Months apart", "Ends", "Date", "Label", "Amount", "Month"]
    header(ws, 1, title_row, [7, 6, 13, 8, 13, 13, 36, 12, 7])
    ws.freeze_panes = "A2"
    MD = lambda c: f"'My Dates'!${c}${MY_FIRST}:${c}${MY_FIRST + MY_ROWS - 1}"  # noqa: E731
    y0, y1 = f"DATE({year},1,1)", f"DATE({year},12,31)"
    r = 1
    for n in range(1, MY_ROWS + 1):
        for k in range(MAX_REPEATS):
            r += 1
            ws.cell(r, 1, k)
            ws.cell(r, 2, n)
            src = lambda c: f"INDEX({MD(c)},$B{r})"  # noqa: E731
            ws.cell(r, 3, f'=IF(OR({src("A")}="",{src("C")}=""),"",{src("C")})').number_format = DATE_Y
            ws.cell(r, 4, f'=IF(C{r}="","",IFERROR(INDEX(Lists!$D$5:$D${4 + len(REPEATS)},'
                          f'MATCH({src("D")},Lists!$C$5:$C${4 + len(REPEATS)},0)),0))')
            ws.cell(r, 5, f'=IF(C{r}="","",IF({src("E")}="",{y1},MIN({src("E")},{y1})))').number_format = DATE_Y
            ws.cell(r, 6, f'=IF(OR(C{r}="",AND(D{r}=0,A{r}>0)),"",IF(OR(EDATE(C{r},A{r}*D{r})>E{r},'
                          f'EDATE(C{r},A{r}*D{r})<{y0}),"",EDATE(C{r},A{r}*D{r})))').number_format = DATE
            ws.cell(r, 7, f'=IF(F{r}="","",{src("A")}&": "&LOWER({src("B")}))')
            ws.cell(r, 8, f'=IF(OR(F{r}="",{src("F")}=""),"",{src("F")})').number_format = MONEY
            ws.cell(r, 9, f'=IF(F{r}="","",MONTH(F{r}))')
    style_body(ws, 2, r, 1, 9)
    ws.auto_filter.ref = f"A1:I{r}"
    put(ws, "K1", "Calculated from My Dates; nothing to type here.", F_ITAL)


def cal_days_iter(P):
    for m in P["months"]:
        for w in m["weeks"]:
            for d in w["days"]:
                if not d["closed"]:
                    yield dt.date.fromisoformat(d["date"])


def sheet_readme(wb, P):
    ws = wb.create_sheet("How to use", 1)
    title(ws, "How to use this workbook", f"The Seasonal Ledger {P['year']} · built {P['stats']['meta']['built']}")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 100
    rows = [
        ("Yellow cells", "are the only cells to type in. Everything else is either history (fixed values "
         "computed from S&P 500 closes, 1950–2025) or a formula."),
        ("Today", "the day, its week and month, what's coming up, and the next 14 days. Type a date in the "
         "yellow cell to look at another day."),
        ("Calendar", "every day of 2027: market status, trading-day slot and its history, FOMC, options "
         "expiration, earnings seasons, the Santa Claus Rally window. Filter with the header arrows. "
         "The 'My notes' column is yours."),
        ("Weeks / Months", "the history of each week and month, ranked; columns for your plan and goals. "
         "Months also totals your closed trades by month."),
        ("Earnings", "the four seasons (estimated windows until big-bank dates are announced) and a "
         "watchlist of report dates; Week and Surprise calculate."),
        ("Trades", "one row per trade. Fill in the yellow columns; risk, P&L, R multiple, return, days held "
         "and status calculate, and each trade picks up its entry day's history from the Calendar."),
        ("Review", "totals the Trades sheet: the year so far, then by setup, close month, side, earnings "
         "season and the entry day's history."),
        ("My Dates", "your own securities: coupons, dividends, maturities. One row per payment stream with "
         "its first date and how often it repeats; every date then shows on the Calendar and Today sheets, "
         "and the Months sheet totals the payments. Schedule is the worked-out list."),
        ("Treasury auctions", "coupon auctions (notes, bonds, TIPS, FRNs) from Treasury's tentative "
         "schedule, in the Calendar's Treasury auction column. Treasury publishes about six months at a time, "
         "so later dates arrive with each quarterly refunding."),
        ("Lists", "your setup tags and kinds of dates (they feed the dropdowns)."),
        ("Reference", "the presidential cycle, best and worst six months, January Barometer, Santa Claus "
         "Rally, holiday windows and earnings-season daily averages."),
        ("Google Sheets", "upload the file to Drive and open it with Google Sheets (or set Drive to convert "
         "uploads). The formulas work in both."),
        ("Privacy", "keep your filled-in copy to yourself; the template in the public repo stays empty."),
    ]
    for i, (a, b) in enumerate(rows, start=4):
        put(ws, f"A{i}", a, F_LABEL, align=TOP)
        put(ws, f"B{i}", b, F_BODY, align=WRAP)
        ws.row_dimensions[i].height = 30
    r = 4 + len(rows) + 1
    put(ws, f"A{r}", "Example trade row", F_H2)
    ex_h = ["Open date", "Ticker", "Side", "Setup", "Shares", "Entry", "Stop", "Target", "Close date",
            "Exit", "Fees"]
    ex = [dt.date(2027, 3, 1), "XYZ", "Long", "Breakout", 100, 52.40, 50.90, 56.00, dt.date(2027, 3, 12),
          55.10, 2.00]
    sub = ws.cell(r + 1, 1, "Format only; type real trades on the Trades sheet. This row gives "
                  "Risk $150.00, P&L $268.00, +1.79R, status Win.")
    sub.font = F_ITAL
    header(ws, r + 2, ex_h, col=1)
    for j, v in enumerate(ex, start=1):
        c = ws.cell(r + 3, j, v)
        c.font = F_BODY
        if isinstance(v, dt.date):
            c.number_format = DATE
    for j in range(3, 12):
        ws.column_dimensions[get_column_letter(j)].width = 10
    put(ws, f"A{r + 5}", "Describes the past; predicts nothing. Not investment advice.", F_ITAL)


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    P, cal, days, weeks = load(year)
    global CAL_LAST
    CAL_LAST = 1 + len(cal.days)
    wb = Workbook()
    cal_last = sheet_calendar(wb, P, cal, days)
    sheet_today(wb, P, cal_last)
    sheet_readme(wb, P)
    sheet_weeks(wb, P, weeks)
    sheet_months(wb, P)
    sheet_earnings(wb, P, cal)
    tag_first = sheet_lists(wb)
    sheet_trades(wb, tag_first)
    sheet_review(wb, tag_first)
    sheet_reference(wb, P)
    sheet_mydates(wb, year)
    sheet_schedule(wb, year)
    order = ["Today", "How to use", "Calendar", "Weeks", "Months", "Earnings", "My Dates", "Trades", "Review",
             "Reference", "Schedule", "Lists"]
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    colors = {"Today": ORANGE, "Trades": ORANGE, "Review": ORANGE, "My Dates": ORANGE}
    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = colors.get(ws.title, BLUE)
        ws.sheet_view.showGridLines = ws.title in ("Calendar", "Trades")
    out = ROOT / "build" / f"seasonal-ledger-{year}.xlsx"
    wb.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
