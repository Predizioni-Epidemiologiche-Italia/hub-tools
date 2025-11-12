#!/usr/bin/env python3
# tools/code/validate_extras.py
from __future__ import annotations
import csv
from collections import Counter, defaultdict
from pathlib import Path
import re
from typing import List, Dict, Tuple

# Colonne coinvolte nei tre controlli
COL_YEAR = "anno"
COL_WEEK = "settimana"
COL_LOC  = "luogo"
COL_TVAL = "tipo_valore"   # "quantile" o altro
COL_Q    = "id_valore"     # es. 0.025, 0.5, 0.975
COL_H    = "orizzonte"
COL_VAL  = "valore"
COL_TGT  = "target"

# chiavi che identificano univocamente un record di previsione
DUP_KEYS = [COL_YEAR, COL_WEEK, COL_LOC, COL_TGT, COL_H, COL_TVAL, COL_Q]

# filename: accetto .../qualcosa/2025_06.csv oppure prefissi/suffissi (prendo la prima occorrenza)
FILENAME_WEEK_RE = re.compile(r"(?P<year>\d{4})_(?P<week>\d{2})")

def _read_csv(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = [h.strip() for h in (r.fieldnames or [])]
        for i, row in enumerate(r, start=2):  # dati da riga 2
            yield i, {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

def _parse_week_from_filename(path: Path) -> Tuple[int, int]:
    m = FILENAME_WEEK_RE.search(path.name)
    if not m:
        raise ValueError(f"{path.name}: nome file non contiene pattern 'YYYY_WW'")
    return int(m.group("year")), int(m.group("week"))

def _as_float(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def _as_int(x):
    try:
        return int(str(x))
    except Exception:
        return None

def run_extra_checks(path_str: str) -> List[str]:
    """Ritorna lista di errori. Lista vuota = OK."""
    p = Path(path_str)
    errors: List[str] = []

    # --- 1) coerenza anno/settimana con filename ---
    try:
        y_file, w_file = _parse_week_from_filename(p)
    except ValueError as e:
        errors.append(str(e))
        # continuiamo comunque per dare altri errori utili
        y_file = w_file = None

    anni, settimane = set(), set()

    # per duplicati
    dup_counter: Counter = Counter()
    dup_lines: defaultdict = defaultdict(list)

    # per monotonia quantili
    q_groups: defaultdict = defaultdict(list)  # key -> list[(q, value, line)]

    # leggi righe
    try:
        rows = list(_read_csv(p))
    except Exception as e:
        return [f"{p.name}: lettura CSV fallita: {e}"]

    # loop righe
    for line_no, row in rows:
        y = _as_int(row.get(COL_YEAR))
        w = _as_int(row.get(COL_WEEK))
        if y is None:
            errors.append(f"{p.name}: riga {line_no}: '{COL_YEAR}' non intero: {row.get(COL_YEAR)!r}")
        if w is None:
            errors.append(f"{p.name}: riga {line_no}: '{COL_WEEK}' non intero: {row.get(COL_WEEK)!r}")
        if y is not None:
            anni.add(y)
        if w is not None:
            settimane.add(w)

        key = (
            str(row.get(COL_YEAR)),
            str(row.get(COL_WEEK)),
            row.get(COL_LOC),
            row.get(COL_TGT),
            str(row.get(COL_H)),
            (row.get(COL_TVAL) or "").lower(),
            str(row.get(COL_Q)),
        )
        dup_counter[key] += 1
        dup_lines[key].append(line_no)

        if (row.get(COL_TVAL) or "").lower() == "quantile":
            q = _as_float(row.get(COL_Q))
            v = _as_float(row.get(COL_VAL))
            if q is None:
                errors.append(f"{p.name}: riga {line_no}: '{COL_Q}' per quantile non numerico: {row.get(COL_Q)!r}")
                continue
            if v is None:
                errors.append(f"{p.name}: riga {line_no}: '{COL_VAL}' non numerico: {row.get(COL_VAL)!r}")
                continue
            gkey = (row.get(COL_YEAR), row.get(COL_WEEK), row.get(COL_LOC), row.get(COL_TGT), str(row.get(COL_H)))
            q_groups[gkey].append((q, v, line_no))

    # coerenza con filename (solo se il filename era valido)
    if y_file is not None and w_file is not None:
        if len(anni) != 1 or y_file not in anni:
            errors.append(f"{p.name}: 'anno' nel CSV {sorted(anni)} diverso dall'anno nel filename {y_file}")
        if len(settimane) != 1 or w_file not in settimane:
            errors.append(f"{p.name}: 'settimana' nel CSV {sorted(settimane)} diversa dalla settimana nel filename {w_file}")

    # --- 2) duplicati ---
    dups = [k for k, c in dup_counter.items() if c > 1]
    if dups:
        lines_desc = "\n".join(
            f"  - {dict(zip(['anno','settimana','luogo','target','orizzonte','tipo_valore','id_valore'], k))}  (righe: {dup_lines[k]})"
            for k in dups
        )
        errors.append(f"{p.name}: record duplicati per chiavi [anno,settimana,luogo,target,orizzonte,tipo_valore,id_valore]:\n{lines_desc}")

    # --- 3) monotonia quantili (non decrescente) ---
    bad_groups = []
    for gkey, triples in q_groups.items():
        triples.sort(key=lambda x: x[0])  # ordina per quantile
        vals = [v for _, v, _ in triples]
        for i in range(1, len(vals)):
            if vals[i] < vals[i - 1]:
                bad_groups.append((gkey, triples))
                break

    if bad_groups:
        buf = []
        for (a, s, loc, tgt, oriz), triples in bad_groups:
            seq = ", ".join(f"q={q:g}->v={v:g}[r{ln}]" for q, v, ln in triples)
            buf.append(f"  - anno={a}, settimana={s}, luogo={loc}, target={tgt}, orizzonte={oriz}\n    sequenza: {seq}")
        errors.append(f"{p.name}: quantili non monotoni (valori decrescono all'aumentare del quantile) nei gruppi:\n" + "\n".join(buf))

    return errors