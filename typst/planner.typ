// The Seasonal Ledger — entry point. Build with: python build.py
#import "theme.typ": *
#import "pages.typ": *

#let P = json("/build/planner.json")

#set document(title: "The Seasonal Ledger " + str(P.year))
#set text(font: sans, size: 9pt, fill: ink, lang: "en")
#set par(leading: 0.55em, spacing: 0.9em)
#set page(paper: "us-letter", margin: (x: 0.62in, top: 0.6in, bottom: 0.75in),
  footer: context {
    let n = counter(page).get().first()
    if n == 1 { return }
    set text(size: 7pt, fill: mute, tracking: 0.08em)
    if calc.even(n) [#n #h(1fr) THE SEASONAL LEDGER · #P.year]
    else [NOT INVESTMENT ADVICE #h(1fr) #n]
  })

#cover(P)
#pagebreak()
#year-ahead(P)
#pagebreak()
#year-glance(P)
#pagebreak()
#earnings-page(P)
#pagebreak()
#plan-page(P)

#for mo in P.months {
  pagebreak(to: "even")
  month-opener(P, mo)
  pagebreak()
  month-grid(P, mo)
  for w in mo.weeks {
    pagebreak(to: "even")
    week-days(P, w)
    pagebreak()
    week-review(P, w)
  }
  if calc.rem(mo.m, 3) == 0 and mo.m < 12 {
    pagebreak(to: "even")
    quarter-review(P, calc.div-euclid(mo.m, 3))
    pagebreak()
    quarter-plan(P, calc.div-euclid(mo.m, 3))
  }
}

#pagebreak(to: "even")
#year-review(P)
#pagebreak()
#my-dates(P)
#for k in range(6) {
  pagebreak()
  trade-log(P, k)
}
#pagebreak()
#methodology(P)
