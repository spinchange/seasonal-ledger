"""Fetch S&P 500 (^GSPC) daily closes into data/raw/gspc.csv.

The raw price series is NOT committed (it is S&P Dow Jones Indices data,
redistributed by Yahoo). Only derived statistics in data/stats/ are committed,
so the planner can be rebuilt without network access.

Usage: python pipeline/fetch.py
"""
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "gspc.csv"


def main() -> None:
    df = yf.download("^GSPC", start="1949-12-01", auto_adjust=False, progress=False)
    if df.empty:
        raise SystemExit("no data returned for ^GSPC")
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    out = df[["Close"]].rename(columns={"Close": "close"})
    out.index.name = "date"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, float_format="%.4f")
    print(f"{len(out)} rows, {out.index.min().date()} .. {out.index.max().date()} -> {OUT}")


if __name__ == "__main__":
    main()
