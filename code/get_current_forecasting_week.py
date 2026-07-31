#!/usr/bin/env python3
"""
get_current_forecasting_week.py

Determina la settimana di forecasting corrente a partire da
./supporting-files/forecasting_weeks.csv (righe con is_latest=True) e scrive
su $GITHUB_OUTPUT i valori pronti per lo step successivo che calcola l'indice
influmeter (compute_influmeter_index.py):

  year_week  -> es. "2026_30"  (year a 4 cifre "_" week a 2 cifre)
  csv_path   -> es. "./previsioni/influmeter/2026_30_influmeter.csv"

Env var opzionali:
  FORECASTING_WEEKS_FILE  (default "./supporting-files/forecasting_weeks.csv")
  INFLUMETER_OUTPUT_DIR   (default "./previsioni/influmeter")

Nessun argomento da riga di comando.
"""

import os
import sys

import pandas as pd

FORECASTING_WEEKS_FILE = os.environ.get(
    "FORECASTING_WEEKS_FILE", "./supporting-files/forecasting_weeks.csv"
)
OUTPUT_DIR = os.environ.get("INFLUMETER_OUTPUT_DIR", "./previsioni/influmeter")


def write_github_output(**kwargs) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        # fuori da Actions (es. test locale): stampa soltanto
        for k, v in kwargs.items():
            print(f"{k}={v}")
        return
    with open(output_path, "a", encoding="utf-8") as fh:
        for k, v in kwargs.items():
            fh.write(f"{k}={v}\n")


def main() -> int:
    try:
        # sep=None + engine="python" autorileva il delimitatore (tab o virgola)
        df = pd.read_csv(FORECASTING_WEEKS_FILE, sep=None, engine="python")
    except FileNotFoundError:
        print(f"File non trovato: {FORECASTING_WEEKS_FILE}", file=sys.stderr)
        return 1

    required_cols = {"year", "week", "is_latest"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"Colonne mancanti in {FORECASTING_WEEKS_FILE}: {missing}", file=sys.stderr)
        return 1

    # is_latest puo' arrivare gia' come bool oppure come stringa "True"/"False"
    if df["is_latest"].dtype != bool:
        df["is_latest"] = df["is_latest"].astype(str).str.strip().str.lower() == "true"

    latest = df[df["is_latest"]]
    if latest.empty:
        print(f"Nessuna riga con is_latest=True in {FORECASTING_WEEKS_FILE}", file=sys.stderr)
        return 1

    years = latest["year"].unique()
    weeks = latest["week"].unique()
    if len(years) != 1 or len(weeks) != 1:
        print(
            "Le righe con is_latest=True non individuano un'unica settimana "
            f"(year={sorted(years)}, week={sorted(weeks)})",
            file=sys.stderr,
        )
        return 1

    year = int(years[0])
    week = int(weeks[0])
    year_week = f"{year}_{week:02d}"
    csv_path = f"{OUTPUT_DIR}/{year_week}_influmeter.csv"

    print(f"Settimana di forecasting corrente: year={year}, week={week} -> {year_week}")
    write_github_output(year_week=year_week, csv_path=csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
