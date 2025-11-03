#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
import pandas as pd

REQUIRED_COLS = {
    "anno", "settimana", "luogo", "tipo_valore",
    "id_valore", "orizzonte", "valore", "target",
}

# chiavi per dup
DUP_KEYS = ["anno", "settimana", "luogo", "target", "orizzonte", "tipo_valore", "id_valore"]

def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [f"Impossibile leggere {path.name}: {e}"]

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        errors.append(f"{path.name}: colonne mancanti: {sorted(missing)}")
        return errors  # gli altri controlli non hanno senso

    # 1) DUPLICATI
    dup_mask = df.duplicated(subset=DUP_KEYS, keep=False)
    if dup_mask.any():
        dups = (
            df.loc[dup_mask, DUP_KEYS]
              .drop_duplicates()
              .sort_values(DUP_KEYS)
              .to_string(index=False)
        )
        errors.append(
            f"{path.name}: record duplicati per chiavi {DUP_KEYS}:\n{dups}"
        )

    # 2) CONSISTENZA NOME FILE (YYYY_WW.csv)
    stem = path.stem
    try:
        y_str, w_str = stem.split("_", 1)
        y_file, w_file = int(y_str), int(w_str)
    except Exception:
        errors.append(f"{path.name}: nome file non conforme a 'YYYY_WW.csv'")
        y_file = w_file = None

    if y_file is not None:
        anni = sorted(df["anno"].unique())
        sett = sorted(df["settimana"].unique())
        if len(anni) != 1 or anni[0] != y_file:
            errors.append(
                f"{path.name}: colonna 'anno' {anni} non coincide con anno da filename {y_file}"
            )
        if len(sett) != 1 or sett[0] != w_file:
            errors.append(
                f"{path.name}: colonna 'settimana' {sett} non coincide con settimana da filename {w_file}"
            )

    # 3) MONOTONIA QUANTILI (non decrescente)
    qdf = df[df["tipo_valore"].str.lower() == "quantile"].copy()
    if not qdf.empty:
        bad_groups = []
        for keys, g in qdf.groupby(["anno", "settimana", "luogo", "target", "orizzonte"], sort=False):
            g_sorted = g.sort_values("id_valore")
            vals = g_sorted["valore"].to_numpy()
            if (vals[1:] < vals[:-1]).any():  # “non deve diminuire”
                bad_groups.append(keys)
        if bad_groups:
            pretty = "\n".join(f"  - anno={a}, settimana={s}, luogo={loc}, target={t}, orizzonte={h}"
                               for (a, s, loc, t, h) in bad_groups)
            errors.append(
                f"{path.name}: quantili non monotoni (valori decrescono all'aumentare di id_valore) nei gruppi:\n{pretty}"
            )

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator Influcast")
    ap.add_argument("files", nargs="+", help="CSV da validare (formato YYYY_WW.csv)")
    args = ap.parse_args()

    all_errors: list[str] = []
    for f in args.files:
        all_errors.extend(validate_file(Path(f)))

    if all_errors:
        print("\n\n".join(all_errors))
        return 1
    else:
        print("Tutti i file sono validi ✅")
        return 0


if __name__ == "__main__":
    sys.exit(main())
