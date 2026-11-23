// Design tokens and small components shared by every page.

#let blue = rgb("#2f5f9f")
#let blue-soft = rgb("#eef1f7")
#let orange = rgb("#c9822f")
#let orange-soft = rgb("#fbf1e1")
#let ink = rgb("#222222")
#let mute = rgb("#777777")
#let rule-c = rgb("#cccccc")
#let track = rgb("#e9e9e4")
#let grey-bar = rgb("#bdbdb8")
#let shade = rgb("#f5f5f1")

#let serif = ("Crimson Text",)
#let sans = ("Fira Sans",)

#let kicker(t) = text(font: sans, size: 7.5pt, weight: "semibold", fill: blue, tracking: 0.12em, upper(t))
#let title(t, size: 26pt) = text(font: serif, size: size, weight: "semibold", fill: ink, t)
#let h2(t) = text(font: serif, size: 15pt, weight: "semibold", t)
#let label(t) = text(size: 8.5pt, weight: "semibold", t)
#let small(t) = text(size: 7pt, fill: mute, t)
#let md(s) = if s == none { [] } else { eval(s, mode: "markup") }

#let header(k, t, aside: none) = block(below: 14pt)[
  #kicker(k) \
  #v(-6pt)
  #grid(columns: (1fr, auto), align: (left + bottom, right + bottom),
    title(t), if aside != none { small(aside) })
]

#let card(big, lab, sub, hi: false) = box(
  width: 100%, inset: (x: 9pt, y: 7pt), radius: 3pt,
  stroke: if hi { 1pt + blue } else { 0.6pt + rule-c },
  fill: if hi { blue-soft } else { white },
)[
  #stack(spacing: 5pt,
    text(font: serif, size: 20pt, fill: if hi { blue } else { ink }, big),
    text(size: 7.5pt, weight: "semibold", lab),
    small(sub))
]

// fixed decimals, with sign
#let fix(x, d: 2, sign: true) = {
  let a = calc.abs(x)
  let s = str(calc.round(a, digits: d))
  if d > 0 {
    if not s.contains(".") { s += "." }
    let have = s.len() - s.position(".") - 1
    s += "0" * (d - have)
  }
  if x < 0 { "−" + s } else if sign and x > 0 { "+" + s } else { s }
}

#let cards(items) = grid(columns: (1fr,) * items.len(), column-gutter: 8pt,
  ..items.map(c => card(c.big, c.label, c.sub)))

#let lines(n, gap: 18pt, color: rule-c) = for i in range(n) {
  v(gap, weak: false)
  line(length: 100%, stroke: 0.5pt + color)
}

#let write-box(lab, n, gap: 18pt) = block[
  #label(lab)
  #v(-4pt)
  #lines(n, gap: gap)
]

#let pct-bar(p, w: 82pt) = box(width: w, height: 7pt, baseline: 1pt)[
  #place(rect(width: 100%, height: 100%, fill: track, radius: 1.5pt))
  #place(rect(width: p / 100 * w, height: 100%, fill: blue, radius: 1.5pt))
  #place(dx: w / 2 - 0.4pt, dy: -1pt, rect(width: 0.8pt, height: 9pt, fill: ink))
]

#let tag(t, kind) = {
  let (bg, fg) = if kind == "early" { (orange-soft, ink) }
    else if kind == "fomc" { (blue, white) }
    else if kind == "opex" { (orange-soft, orange.darken(25%)) }
    else if kind == "earn" { (rgb("#e8f1e8"), rgb("#2f6f3f")) }
    else if kind == "auction" { (rgb("#ece8f3"), rgb("#4a3f6b")) }
    else if kind == "econ" { (rgb("#f1ece2"), rgb("#6b4f1d")) }
    else if kind == "filing" { (rgb("#e3eef0"), rgb("#2b5b63")) }
    else { (blue-soft, ink) }
  box(fill: bg, inset: (x: 5pt, y: 2pt), radius: 2pt, text(size: 6.5pt, fill: fg, weight: "medium", t))
}

#let signed(x) = if x > 0 { "+" + str(x) } else if x < 0 { "−" + str(calc.abs(x)) } else { "0" }
