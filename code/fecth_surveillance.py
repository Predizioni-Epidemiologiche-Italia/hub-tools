#!/usr/bin/env python3
# tools/fetch_surveillance.py
from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import subprocess
import sys

ROME = ZoneInfo("Europe/Rome")

PRODUCTS = [
    ("ARI",       "Influcast/sorveglianza/ARI"),
    ("ARI+_FLU",  "Influcast/sorveglianza/ARI+_FLU"),
]

def season_for(date: datetime) -> str:
    # stagione tipo 2025-2026: se mese >= 7 => stagione inizia nell'anno corrente
    start = date.year if date.month >= 7 else date.year - 1
    return f"{start}-{start+1}"

def compute_year_week(now: datetime) -> tuple[int, int]:
    # ISO settimana/anno nella tz di Roma
    iso = now.isocalendar()  # (year, week, weekday)
    return iso.year, iso.week

def run_parset(product: str, out_csv: Path, year: int, week: int) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_csv.exists():
        print(f"[skip] Esiste già: {out_csv}")
        return
    # >>>>> QUI adatta la CLI se necessario <<<<<
    cmd = [
        sys.executable, "parset_respivirnet.py",
        "--product", product,
        "--out", str(out_csv),
        "--year", str(year),
        "--week", f"{week:02d}",
    ]
    print("[exec]", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--override-year", type=int)
    ap.add_argument("--override-week", type=int)
    args = ap.parse_args()

    now = datetime.now(tz=ROME)
    year, week = (args.override_year, args.override_week) if (args.override_year and args.override_week) else compute_year_week(now)
    seas = season_for(now)

    print(f"Roma now={now.isoformat()}  -> ISO {year}-W{week:02d}  season={seas}")

    for product, base in PRODUCTS:
        out_dir = Path(base) / seas
        out_csv = out_dir / f"{year}_{week:02d}.csv"
        run_parset(product, out_csv, year, week)

    print("Fetch completato.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())