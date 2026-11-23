"""One-command build: stats (if price data is present) -> assemble -> typst.

    python build.py            # full build of 2027
    python build.py --fetch    # refresh ^GSPC from Yahoo first (needs network + yfinance)
    python build.py --no-stats # use committed data/stats/<year>.json (cloud / CI path)
    python build.py --png 1-9  # also render those pages to build/png/ for review

Writes build/seasonal-ledger-<year>.pdf and build/seasonal-ledger-<year>.xlsx.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(*cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2027)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--no-stats", action="store_true")
    ap.add_argument("--png", metavar="PAGES")
    a = ap.parse_args()

    if a.fetch:
        run(PY, "pipeline/fetch.py")
    raw = ROOT / "data" / "raw" / "gspc.csv"
    if not a.no_stats and raw.exists():
        run(PY, "pipeline/stats.py", str(a.year))
    elif not a.no_stats:
        print(f"note: {raw} missing; using committed data/stats/{a.year}.json")
    run(PY, "pipeline/assemble.py", str(a.year))
    run(PY, "pipeline/sheet.py", str(a.year))
    typst = ["typst", "compile", "--root", ".", "--font-path", "fonts", "--ignore-system-fonts"]
    run(*typst, "typst/planner.typ", f"build/seasonal-ledger-{a.year}.pdf")
    if a.png:
        (ROOT / "build" / "png").mkdir(parents=True, exist_ok=True)
        run(*typst, "--ppi", "80", "--pages", a.png, "typst/planner.typ", "build/png/p{0p}.png")


if __name__ == "__main__":
    main()
