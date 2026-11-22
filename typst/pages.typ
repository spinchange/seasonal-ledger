#import "theme.typ": *

// ---------------------------------------------------------------- charts

// Grouped bars: all years (grey) vs pre-election (blue), by month.
#let month-chart(P) = {
  let S = P.stats.months
  let vals = range(1, 13).map(m => (S.at(str(m)).all.avg, S.at(str(m)).pre.avg))
  let hi = calc.max(..vals.map(v => calc.max(v.at(0), v.at(1))))
  let lo = calc.min(0, ..vals.map(v => calc.min(v.at(0), v.at(1))))
  let H = 120pt
  let scale = H / (hi - lo)
  let zero = hi * scale
  let names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
  block(width: 100%, height: H + 30pt)[
    #place(top + right, dy: -4pt)[
      #box(width: 12pt, height: 7pt, fill: grey-bar) #text(size: 7.5pt)[All years (#P.window)] #h(10pt)
      #box(width: 12pt, height: 7pt, fill: blue) #text(size: 7.5pt)[Pre-election years (n = #S.at("1").pre.n)]
    ]
    #for tick in range(int(calc.floor(lo)), int(calc.ceil(hi)) + 1) {
      if calc.rem(tick, 2) == 0 {
        let y = zero - tick * scale
        place(dx: 22pt, dy: y, line(length: 100% - 22pt, stroke: (paint: if tick == 0 { ink } else { rule-c }, thickness: if tick == 0 { 0.7pt } else { 0.4pt })))
        place(dx: 0pt, dy: y - 5pt, text(size: 7.5pt, fill: mute, str(tick)))
      }
    }
    #layout(sz => {
      let w = (sz.width - 22pt) / 12
      for (i, v) in vals.enumerate() {
        for (j, val) in v.enumerate() {
          let bh = calc.abs(val) * scale
          let x = 22pt + i * w + w * 0.18 + j * w * 0.32
          let y = if val >= 0 { zero - bh } else { zero }
          place(dx: x, dy: y, rect(width: w * 0.3, height: bh, fill: if j == 0 { grey-bar } else { blue }))
          if j == 1 and (val == calc.max(..vals.map(v => v.at(1))) or val == calc.min(..vals.map(v => v.at(1)))) {
            place(dx: x - 2pt, dy: if val >= 0 { y - 10pt } else { y + bh + 2pt },
              text(size: 6.5pt, fix(val, d: 1)))
          }
        }
        place(dx: 22pt + i * w, dy: H + 8pt, box(width: w, align(center, text(size: 7.5pt, fill: mute, names.at(i)))))
      }
    })
  ]
}

// Average change by trading day of month, labelled with % up.
#let td-chart(mo) = {
  let pts = mo.chart
  let hi = calc.max(0.05, ..pts.map(p => p.avg))
  let lo = calc.min(-0.05, ..pts.map(p => p.avg))
  let H = 104pt
  let scale = H / (hi - lo)
  let zero = hi * scale + 16pt
  block(width: 100%, height: H + 54pt, above: 10pt)[
    #place(dx: 26pt, dy: -4pt, small[Bar labels: % of years the day closed up])
    #place(dx: 26pt, dy: zero, line(length: 100% - 26pt, stroke: 0.7pt + ink))
    #for t in (-0.2, -0.1, 0.1, 0.2, 0.3) {
      if t <= hi and t >= lo {
        place(dx: 26pt, dy: zero - t * scale, line(length: 100% - 26pt, stroke: 0.4pt + rule-c))
        place(dx: 0pt, dy: zero - t * scale - 5pt, text(size: 7pt, fill: mute, fix(t, d: 1)))
      }
    }
    #layout(sz => {
      let w = (sz.width - 26pt) / pts.len()
      for (i, p) in pts.enumerate() {
        let bh = calc.max(0.6pt, calc.abs(p.avg) * scale)
        let x = 26pt + i * w + w * 0.15
        let y = if p.avg >= 0 { zero - bh } else { zero }
        place(dx: x, dy: y, rect(width: w * 0.7, height: bh, fill: if p.avg >= 0 { blue } else { orange }))
        place(dx: 26pt + i * w, dy: if p.avg >= 0 { y - 9pt } else { y + bh + 2pt },
          box(width: w, align(center, text(size: 6pt, fill: mute, str(p.pct_up)))))
        place(dx: 26pt + i * w, dy: H + 26pt, box(width: w, align(center, text(size: 7pt, fill: mute, str(p.td)))))
      }
      place(dy: H + 40pt, box(width: sz.width, align(center, text(size: 7.5pt, fill: mute)[#mo.name trading day])))
    })
  ]
}

// ---------------------------------------------------------------- front matter

#let cover(P) = {
  let S = P.stats
  v(1.4in)
  kicker[#P.year edition]
  v(-2pt)
  block(par(leading: 0.25em, text(font: serif, size: 54pt, weight: "semibold")[The Seasonal \ Ledger]))
  v(4pt)
  text(font: serif, size: 54pt, fill: blue, str(P.year))
  v(0.7in)
  line(length: 2.2in, stroke: 1.2pt + ink)
  v(6pt)
  block(width: 4.2in, text(size: 11.5pt)[A trader's planner and trade journal, with every seasonal statistic computed from #S.meta.n_years years of S&P 500 history.])
  v(1fr)
  grid(columns: (1fr, 1fr, 1fr), column-gutter: 10pt,
    card[#S.cycle.at("3").pct_up%][of pre-election years up][S&P 500, #S.cycle.at("3").n years, #S.cycle.at("3").first–#S.cycle.at("3").last],
    card[#S.santa.pct_up%][Santa Claus Rally hit rate][last 5 + first 2 trading days],
    card[#S.jan_barometer.pct%][January Barometer record][#S.jan_barometer.hits of #S.jan_barometer.n years],
  )
  v(8pt)
  small[Methodology and data open source. Statistics describe the past; they do not predict the future. Nothing here is investment advice.]
  v(0.3in)
}

#let year-ahead(P) = {
  let S = P.stats
  let c3 = S.cycle.at("3")
  header("The year ahead", [#P.year is a pre-election year])
  par(md(P.notes.year_ahead))
  v(4pt)
  cards((
    (big: fix(c3.avg, d: 1) + "%", label: "Avg. pre-election year", sub: [#c3.pct_up% up · n = #c3.n]),
    (big: fix(S.six.best.avg, d: 1) + "%", label: "Best six months", sub: [Nov–Apr · #S.six.best.pct_up% up · n = #S.six.best.n]),
    (big: fix(S.six.worst.avg, d: 1) + "%", label: "Worst six months", sub: [May–Oct · #S.six.worst.pct_up% up · n = #S.six.worst.n]),
    (big: str(S.jan_barometer.pct) + "%", label: "January Barometer", sub: [year followed January's sign]),
  ))
  v(4pt)
  h2[Average monthly change, all years vs. pre-election years]
  month-chart(P)
  h2[Month by month]
  v(-6pt)
  let M = range(1, 13).map(m => S.months.at(str(m)))
  set text(size: 7.5pt)
  table(columns: (auto,) + (1fr,) * 12, stroke: none, align: (left,) + (center,) * 12, inset: 3.2pt,
    table.hline(stroke: 0.7pt),
    [], ..("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec").map(x => text(weight: "semibold", x)),
    table.hline(stroke: 0.4pt + rule-c),
    text(fill: mute)[All: avg], ..M.map(m => fix(m.all.avg) + "%"),
    text(fill: mute)[All: % up], ..M.map(m => str(m.all.pct_up)),
    table.hline(stroke: 0.4pt + rule-c),
    text(fill: blue, weight: "semibold")[Pre-elec: avg], ..M.map(m => text(weight: "semibold", fix(m.pre.avg) + "%")),
    text(fill: blue, weight: "semibold")[Pre-elec: % up], ..M.map(m => text(weight: "semibold", str(m.pre.pct_up))),
    table.hline(stroke: 0.7pt),
  )
  small[Month-end to month-end change in the S&P 500 price index, #P.window. Pre-election years: #c3.first, #(c3.first + 4) … #c3.last (n = #c3.n).]
  v(2pt)
  h2[The four-year presidential cycle]
  let names = ("Post-election", "Midterm", "Pre-election", "Election")
  grid(columns: (1fr,) * 4, column-gutter: 8pt,
    ..range(1, 5).map(i => {
      let c = S.cycle.at(str(i))
      let hi = i == 3
      box(width: 100%, inset: 9pt, radius: 3pt, stroke: if hi { 1pt + blue } else { 0.6pt + rule-c }, fill: if hi { blue-soft } else { white })[
        #stack(spacing: 5pt, small[Year #i], label(names.at(i - 1)),
          text(font: serif, size: 18pt, fill: if hi { blue } else { ink }, fix(c.avg, d: 1) + "%"),
          pct-bar(c.pct_up, w: 115pt), small[#c.pct_up% of years up · n = #c.n],
          if hi { text(size: 7pt, fill: blue, weight: "semibold")[← #P.year] } else { small[ ] })
      ]
    }))
  v(6pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt, write-box([My themes for #P.year], 3), write-box([Rules I will trade by], 3))
}

#let mini-month(mo) = block(width: 100%)[
  #text(size: 8.5pt, weight: "semibold", mo.name)
  #v(-6pt)
  #set text(size: 6.8pt)
  #grid(columns: (1fr,) * 7, row-gutter: 1pt,
    ..("S", "M", "T", "W", "T", "F", "S").map(d => align(center, text(size: 5.5pt, fill: mute, d))),
    ..mo.cells.map(c => {
      if c == none { return [] }
      let body = str(c.day)
      let fill = if c.santa { blue-soft } else if c.season { rgb("#f1f6ef") } else { none }
      let content = if c.fomc { box(fill: blue, radius: 50%, width: 11pt, height: 11pt, align(center + horizon, text(fill: white, weight: "bold", body))) }
        else if c.opex { box(stroke: 0.8pt + orange, radius: 50%, width: 11pt, height: 11pt, align(center + horizon, body)) }
        else if c.closed { text(fill: mute, strike(body)) }
        else if c.early { text(fill: orange, weight: "bold", body) }
        else if c.weekend { text(fill: mute.lighten(30%), body) }
        else { body }
      box(width: 100%, height: 12pt, fill: fill, align(center + horizon, content))
    }))
]

#let year-glance(P) = {
  header([#P.year market calendar], [The year at a glance])
  set text(size: 7.5pt)
  [#box(fill: blue, radius: 50%, width: 8pt, height: 8pt) FOMC decision #h(8pt)
   #box(stroke: 0.8pt + orange, radius: 50%, width: 8pt, height: 8pt) Options expiration (3rd Fri; Mar/Jun/Sep/Dec = quad witching) #h(8pt)
   #text(fill: mute, strike[15]) Market closed #h(8pt)
   #text(fill: orange, weight: "bold")[26] Early close #h(8pt)
   #box(fill: blue-soft, inset: 1.5pt)[27] Santa Claus Rally window #h(8pt)
   #box(fill: rgb("#f1f6ef"), inset: 1.5pt)[12] Earnings season (est.)]
  v(8pt)
  grid(columns: (1fr,) * 4, column-gutter: 16pt, row-gutter: 12pt, ..P.glance.map(mini-month))
  v(10pt)
  grid(columns: (1fr, 1fr), column-gutter: 24pt,
    [#label[Market holidays (NYSE)] #v(-6pt) #line(length: 100%, stroke: 0.5pt + rule-c) #v(-4pt)
     #set text(size: 8pt)
     #P.holiday_list.join(linebreak())],
    [#label[FOMC meetings] #v(-6pt) #line(length: 100%, stroke: 0.5pt + rule-c) #v(-4pt)
     #set text(size: 8pt)
     #P.fomc_list.join(linebreak())
     #v(4pt)
     #text(fill: mute, P.fomc_note)])
}

#let earnings-page(P) = {
  let E = P.stats.earnings
  header("Earnings seasons", [Reporting season, #P.year])
  par(md(P.notes.earnings))
  v(4pt)
  grid(columns: (1fr,) * 4, column-gutter: 8pt,
    ..P.seasons.map(s => card(fix(s.stat.avg) + "%", [#s.quarter reports],
      [#s.start – #s.end · #s.stat.pct_up% up])))
  v(2pt)
  small[Each card: S&P 500 change over the same calendar window in every year, #P.window. #P.earnings_note]
  v(8pt)
  h2[My watchlist's report dates]
  v(-4pt)
  set text(size: 7.5pt)
  table(rows: (auto, 20pt), columns: (1.2fr, 2.2fr, 1fr, 1fr, 1fr, 1fr, 2.4fr), stroke: (x, y) => (bottom: 0.4pt + rule-c), inset: (y: 6.5pt, x: 3pt),
    table.header(..("Ticker", "Company", "Q4 '26", "Q1 '27", "Q2 '27", "Q3 '27", "What I'm watching").map(x => text(weight: "semibold", x))),
    ..range(20 * 7).map(_ => []))
}

#let plan-page(P) = {
  header([#P.year plan], [The year I intend to trade])
  grid(columns: (1fr, 1fr), column-gutter: 22pt, row-gutter: 14pt,
    write-box([Goals for the year], 5),
    write-box([Risk budget · max drawdown · position sizing], 5),
    write-box([Setups I trade], 5),
    write-box([Setups I don't], 5),
  )
  v(10pt)
  h2[Quarter by quarter]
  grid(columns: (1fr,) * 4, column-gutter: 12pt,
    ..("Q1", "Q2", "Q3", "Q4").map(q => write-box([#q focus], 5)))
  v(10pt)
  write-box([Standing watchlist], 4)
}

// ---------------------------------------------------------------- month

#let month-opener(P, mo) = {
  header("Month opener", [#mo.name #P.year])
  par(md(mo.blurb))
  v(4pt)
  cards(mo.cards)
  v(6pt)
  h2[Average change by trading day of #mo.name]
  td-chart(mo)
  small[Trading day 1 = first session of the month. Bars shown where at least 60% of years had that session; later bars rest on fewer years. #mo.name #P.year has #mo.sessions sessions.]
  v(6pt)
  h2[#mo.name goals & watchlist]
  v(-6pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt,
    [#small[Goals for the month] #lines(7, gap: 19pt)],
    [#small[Watchlist · levels · seasonal setups] #lines(7, gap: 19pt)])
}

#let month-grid(P, mo) = {
  kicker[#mo.name #P.year at a glance]
  v(-2pt)
  let rows = calc.div-euclid(mo.cells.len(), 7)
  let cellh = if rows > 5 { 104pt } else { 124pt }
  grid(columns: (1fr,) * 7, stroke: 0.5pt + rule-c,
    ..("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat").map(d => box(inset: 4pt, text(size: 7.5pt, weight: "semibold", d))),
    ..mo.cells.map(c => {
      if c == none { return box(width: 100%, height: cellh) }
      let fill = if c.weekend or c.at("closed", default: false) { shade } else if c.santa { blue-soft } else { white }
      box(width: 100%, height: cellh, fill: fill, inset: 5pt)[
        #grid(columns: (1fr, auto),
          text(size: 11pt, weight: "semibold", fill: if c.weekend or c.at("closed", default: false) { mute.lighten(20%) } else { ink }, str(c.day)),
          if "pct_up" in c { text(size: 6.5pt, weight: "semibold", fill: if c.pct_up >= 50 { blue } else { orange }, str(c.pct_up) + "%") })
        #set text(size: 6.3pt, fill: mute)
        #if "note" in c [#c.note \ ]
        #for n in c.at("notes", default: ()) [#n \ ]
        #if c.santa and not c.weekend [Santa Claus Rally window \ ]
        #if c.season and not c.weekend and not c.at("closed", default: false) [#place(bottom + right, dx: 2pt, dy: 2pt, box(width: 4pt, height: 4pt, fill: rgb("#7fb08a"), radius: 50%))]
      ]
    }))
  v(4pt)
  small[Figure in each weekday = % of years that trading-day slot of #mo.name closed up (#P.window). Green dot = earnings season (est.). Shaded blue = Santa Claus Rally window.]
}

// ---------------------------------------------------------------- week

#let week-days(P, w) = {
  header(w.kicker, w.title, aside: "bar = % of years up · tick at 50%")
  v(-6pt)
  block(fill: blue-soft, inset: 9pt, radius: 3pt, width: 100%, text(size: 8.5pt, md(w.blurb)))
  v(4pt)
  let dayh = if w.next != none { 108pt } else { 114pt }
  for d in w.days {
    block(height: if d.closed { 64pt } else { dayh }, width: 100%, above: 0pt, below: 0pt,
      stroke: (top: 0.8pt + ink), inset: (top: 6pt))[
      #grid(columns: (78pt, 1fr),
        stack(spacing: 4pt,
          [#text(font: serif, size: 21pt, str(d.day)) #h(2pt) #text(size: 7.5pt, fill: mute, d.mon)],
          text(size: 8pt, weight: "semibold", d.dow)),
        if d.closed {
          text(size: 10pt, fill: mute, d.closed_text)
        } else {
          set text(size: 7.3pt)
          grid(columns: (110pt, 92pt, auto, 1fr), align: horizon,
            text(fill: mute, d.slot), pct-bar(d.pct_up),
            [#text(weight: "bold", str(d.pct_up) + "%") up · avg #d.avg% · n = #d.n #h(6pt)],
            d.badges.map(b => tag(b.text, b.kind)).join(h(3pt)))
          for n in d.notes { v(1pt, weak: true); text(size: 7.3pt, fill: blue, style: "italic", n); linebreak() }
          lines(calc.max(2, 4 - d.notes.len() - calc.div-euclid(d.badges.len(), 3)), gap: 19pt)
        })
    ]
  }
  line(length: 100%, stroke: 0.8pt + ink)
  if w.next != none { v(-4pt); text(size: 8pt)[*Next week:* #md(w.next)] }
}

#let week-review(P, w) = {
  kicker[Week #w.num · ideas, trades & review]
  v(-4pt)
  set text(size: 7.5pt)
  let rows = if w.season != none { 7 } else { 9 }
  table(rows: (auto, 22pt), columns: (0.9fr, 0.6fr, 3.4fr, 0.8fr, 0.8fr, 0.8fr, 0.7fr, 0.6fr, 0.8fr), stroke: (x, y) => (bottom: if y == 0 { 0.8pt + ink } else { 0.4pt + rule-c }), inset: (y: 7.6pt, x: 3pt),
    ..("Ticker", "L / S", "Setup · thesis · seasonal tag", "Entry", "Stop", "Target", "Size", "Paper", "Result").map(x => text(weight: "semibold", x)),
    ..range(rows * 9).map(_ => []))
  v(6pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt, write-box([What worked], 3, gap: 17pt), write-box([What didn't], 3, gap: 17pt))
  v(6pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt,
    [*Followed my plan?* #h(4pt) ☐ Yes ☐ Mostly ☐ No],
    [*Did the seasonal context matter?* #h(4pt) ☐ Helped ☐ Neutral ☐ Misled])
  if w.season != none {
    v(6pt)
    label[Earnings this week · #w.season season]
    v(-4pt)
    table(rows: (auto, 22pt), columns: (0.9fr, 0.9fr, 0.8fr, 0.8fr, 0.9fr, 3fr), stroke: (x, y) => (bottom: if y == 0 { 0.8pt + ink } else { 0.4pt + rule-c }), inset: (y: 7pt, x: 3pt),
      ..("Ticker", "Date · B/A", "EPS est.", "Actual", "Move", "Guidance · notes").map(x => text(weight: "semibold", x)),
      ..range(5 * 6).map(_ => []))
    write-box([Notes], 5, gap: 18pt)
  } else {
    v(4pt)
    write-box([Notes], 11, gap: 20pt)
  }
}

// ---------------------------------------------------------------- reviews & back matter

#let quarter-review(P, q) = {
  header("Quarter review", [Q#q #P.year in review])
  grid(columns: (1fr,) * 4, column-gutter: 8pt,
    ..("S&P 500 for the quarter", "My return", "Closed trades · win rate", "Avg. R-multiple").map(l =>
      box(width: 100%, height: 52pt, inset: 8pt, radius: 3pt, stroke: 0.6pt + rule-c, label(l))))
  v(10pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt, row-gutter: 14pt,
    write-box([Best trades — why they worked], 6), write-box([Worst trades — what I'd change], 6),
    write-box([Seasonal setups that played out], 5), write-box([Seasonal setups that failed], 5))
  v(10pt)
  write-box([Rules to keep · rules to change], 5)
}

#let quarter-plan(P, q) = {
  header("Quarter ahead", [Planning Q#(q + 1) #P.year])
  write-box([What the calendar says about the next three months], 5)
  v(10pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt, write-box([Earnings dates I need to know], 8), write-box([Watchlist · levels], 8))
  v(10pt)
  write-box([Commitments for the quarter], 6)
}

#let year-review(P) = {
  header("Year-end review", [#P.year in review])
  grid(columns: (1fr,) * 4, column-gutter: 8pt,
    ..("S&P 500 for the year", "My return", "Trades · win rate", "Max drawdown").map(l =>
      box(width: 100%, height: 52pt, inset: 8pt, radius: 3pt, stroke: 0.6pt + rule-c, label(l))))
  v(10pt)
  h2[Results by seasonal tag]
  set text(size: 8pt)
  table(rows: (auto, 22pt), columns: (2.4fr, 1fr, 1fr, 1fr, 1fr, 2.4fr), stroke: (x, y) => (bottom: if y == 0 { 0.8pt + ink } else { 0.4pt + rule-c }), inset: (y: 7.5pt, x: 3pt),
    ..("Tag", "Trades", "Win %", "Avg. R", "Total", "Keep · drop · change").map(x => text(weight: "semibold", x)),
    ..("pre-election", "best-six", "worst-six", "Santa", "opex wk", "FOMC", "earnings", "holiday", "", "").map(t => (text(fill: mute, t), [], [], [], [], [])).flatten())
  v(10pt)
  grid(columns: (1fr, 1fr), column-gutter: 22pt, write-box([What #P.year taught me], 7), write-box([Carry into #(P.year + 1)], 7))
}

#let trade-log(P, k) = {
  if k == 0 { header("Trade log", [Closed trades & paper trades]) } else { kicker[Trade log · continued]; v(4pt) }
  set text(size: 7.5pt)
  table(rows: (auto, 22pt), columns: (0.9fr, 0.9fr, 0.5fr, 3.2fr, 0.8fr, 0.8fr, 0.6fr, 0.8fr, 0.9fr), stroke: (x, y) => (bottom: if y == 0 { 0.8pt + ink } else { 0.4pt + rule-c }), inset: (y: 8.3pt, x: 3pt),
    ..("Opened", "Ticker", "P / R", "Setup · seasonal tag", "Entry", "Exit", "Days", "Return", "R-multiple").map(x => text(weight: "semibold", x)),
    ..range((if k == 0 { 25 } else { 28 }) * 9).map(_ => []))
  if k == 0 { small[P / R = paper or real. Tag each trade with the seasonal context it was opened in (e.g., "pre-election", "best-six", "Santa", "opex wk", "earnings") so the year-end review can sort by it.] }
}

#let methodology(P) = {
  let S = P.stats
  header("Methodology", [How every number here is made])
  set text(size: 8.6pt)
  block(height: 285pt, columns(2, gutter: 20pt)[
    *Data.* Daily closing values of the S&P 500 price index (^GSPC), #S.meta.first_year–#S.meta.last_year: #S.meta.n_years complete calendar years. Price only — dividends excluded. Statistics are computed by an open-source pipeline; the price series itself is not redistributed.

    *Trading day of month.* Sessions are numbered from the first trading day of each month. The last four sessions are numbered from the end instead ("2nd-to-last TD"), so month-end effects line up across months of different length. A #P.year date inherits the history of its slot: "% up" is the share of years that slot closed higher than the prior session; "avg" is the mean daily change.

    *Weeks.* Each week's figure measures the S&P 500 from the last close before that Monday's calendar date to the last close on or before that Friday's date, in every year. Thanksgiving week is anchored to the holiday instead.

    *Months & years.* Month-end to month-end and year-end to year-end changes in the closing price.

    *Pre-election years.* The third year of each presidential term: #S.cycle.at("3").first, #(S.cycle.at("3").first + 4) … #S.cycle.at("3").last (n = #S.cycle.at("3").n).

    *Best / worst six months.* Nov 1–Apr 30 vs. May 1–Oct 31, month-end to month-end. \$10,000 compounded through every Nov–Apr period would have grown to about \$#str(calc.round(S.six.best.growth10k / 1000000, digits: 1)) million; through every May–Oct period, about \$#str(calc.round(S.six.worst.growth10k / 1000))k (price only, no costs or taxes).

    *January Barometer.* Counted a hit when January's sign matched the full year's sign.

    *Santa Claus Rally.* Close of the 6th-to-last trading day of December to close of the 2nd trading day of January.

    *Holidays.* "Day before" and "day after" use the sessions either side of each weekday the market was actually closed for that holiday; years when it fell on a weekend are skipped.

    *Earnings seasons.* The four reporting windows are estimates for #P.year;; their calendar dates were measured in every year. "In-season" days fall inside those dates.

    *Calendar.* Holidays and early closes from NYSE; FOMC dates from the Federal Reserve's revised #P.year schedule (Nov 12, 2026); options expiration is the 3rd Friday, moved to Thursday when Friday is a holiday.
  ])
  v(12pt)
  box(width: 100%, inset: 10pt, radius: 3pt, stroke: 0.6pt + rule-c, text(size: 8pt)[*Read this before you trade on any of it.* Seasonal statistics are descriptions of the past with small samples and no causal story guaranteed. Many patterns weaken once widely known. Nothing in this planner is investment advice; it is a structured place to write down your own ideas and hold yourself to them.])
  v(8pt)
  small[Built #S.meta.built from data through #S.meta.last_year.]
}
