#!/usr/bin/env python3
"""
validate_influmeter.py

Validatore per i file CSV "influmeter" prodotti settimanalmente e proposti
tramite pull request. Pensato per essere richiamato dal workflow GitHub
`validate_influmeter.yml`, che passa allo script due variabili d'ambiente:

  calling_actor  -> ${{ github.actor }}
  changed_files  -> ${{ steps.get_changed_files.outputs.all_changed_files }}

Il file di riferimento con l'elenco dei soggetti autorizzati
(authorized_users.json) è cercato accanto a questo script, salvo override
tramite la variabile d'ambiente AUTHORIZED_USERS_FILE.

Nessuna dipendenza esterna: solo libreria standard.

Contratto con il workflow (step id `authenticate`):
  Lo script scrive su $GITHUB_OUTPUT due output, letti dal workflow per
  decidere se procedere con l'auto-merge o commentare l'errore sulla PR:
    authenticate = "success" | "failure"
    message      = riepilogo (multilinea) degli errori, vuoto se success

  Il job `validate_request` deve SEMPRE completare con successo (exit 0)
  quando l'output GITHUB_OUTPUT è disponibile (cioè quando lo script gira
  dentro Actions): i job downstream `on_successful_validation` /
  `on_validation_failed` usano `if: needs.validate_request.outputs.is_valid
  == 'true'/'false'` SENZA `always()`/`failure()`, quindi se questo step
  fallisse (exit != 0) GitHub salterebbe entrambi i job downstream e la PR
  non riceverebbe alcun commento. L'esito di validazione va quindi
  comunicato solo tramite l'output `authenticate`, non tramite l'exit code.

  Quando lo script viene eseguito FUORI da Actions (GITHUB_OUTPUT non
  definita, es. test locali/CI di unit test) l'exit code torna a riflettere
  l'esito (0 = ok, 1 = errori), per comodità di scripting/test.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# --------------------------------------------------------------------------
# Schema / costanti derivate dal documento di specifica del formato CSV
# --------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "model_id",
    "horizon",
    "start_date",
    "end_date",
    "location_id",
    "target",
    "p_baseline",
    "p_low",
    "p_medium",
    "p_high",
    "p_very_high",
    "influmeter_index",
]

VALID_MODEL_IDS = {"ensemble"}
VALID_TARGETS = {"ARI"}
VALID_HORIZONS = {1, 2, 3, 4}
VALID_LOCATIONS = {"IT"} | {f"{i:02d}" for i in range(1, 22)}  # IT + 01..21

PROB_COLUMNS = ["p_baseline", "p_low", "p_medium", "p_high", "p_very_high"]
PROB_SUM_TARGET = 100.0
PROB_SUM_TOLERANCE = 0.5  # punti percentuali

# Formato data confermato: anno a quattro cifre, es. 2026-07-24
DATE_FORMAT = "%Y-%m-%d"

# Soglie del bucket influmeter_index -> colonna di probabilità attesa come massima
# 0-20 Molto Basso, 20-40 Basso, 40-60 Medio, 60-80 Alto, 80-100 Molto Alto
INDEX_BUCKETS = [
    (0.0, 20.0, "p_baseline"),
    (20.0, 40.0, "p_low"),
    (40.0, 60.0, "p_medium"),
    (60.0, 80.0, "p_high"),
    (80.0, 100.0, "p_very_high"),
]

# Path convenzionale dei CSV nel repo dati: previsioni/influmeter/YYYY_WW.csv
FILE_PATTERN = re.compile(r"^previsioni/influmeter/(?P<year>\d{4})_(?P<week>\d{2})_influmeter\.csv$")

# DEFAULT_AUTHORIZED_USERS_FILE = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)), "authorized_users.json"
# )

# authorized_users.json vive nella cartella "sorella" request_authentication
# (.github/scripts/request_authentication/), non con questo script
# (.github/scripts/forecast_validation/), perché è una risorsa di autenticazione
# condivisa e non specifica della validazione influmeter.
DEFAULT_AUTHORIZED_USERS_FILE = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "request_authentication", "authorized_users.json",
    )
)


# --------------------------------------------------------------------------
# Modello degli esiti di validazione
# --------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str  # "error" | "warning"
    file: str
    message: str
    line: Optional[int] = None  # numero di riga nel CSV (1 = header), None per issue a livello file/globale

    def gh_annotation(self) -> str:
        kind = "error" if self.severity == "error" else "warning"
        loc = f"file={self.file}"
        if self.line is not None:
            loc += f",line={self.line}"
        return f"::{kind} {loc}::{self.message}"

    def human(self) -> str:
        loc = f"{self.file}"
        if self.line is not None:
            loc += f":{self.line}"
        return f"[{self.severity.upper()}] {loc} — {self.message}"


class IssueCollector:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def error(self, file: str, message: str, line: Optional[int] = None) -> None:
        self.issues.append(Issue("error", file, message, line))

    def warning(self, file: str, message: str, line: Optional[int] = None) -> None:
        self.issues.append(Issue("warning", file, message, line))

    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def report(self) -> None:
        if not self.issues:
            print("Nessun problema rilevato.")
            return
        for issue in self.issues:
            print(issue.human())
            print(issue.gh_annotation())

    def summary_message(self) -> str:
        """Riepilogo human-readable per il campo `message` esposto al workflow
        (usato per il commento sulla PR in caso di validazione fallita)."""
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        if not errors and not warnings:
            return "Validazione completata con successo."

        lines: list[str] = []
        if errors:
            lines.append(f"**Errori bloccanti ({len(errors)}):**")
            lines.extend(f"- {i.file}" + (f":{i.line}" if i.line is not None else "") + f" — {i.message}" for i in errors)
        if warnings:
            lines.append(f"**Warning non bloccanti ({len(warnings)}):**")
            lines.extend(f"- {i.file}" + (f":{i.line}" if i.line is not None else "") + f" — {i.message}" for i in warnings)
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Autorizzazione
# --------------------------------------------------------------------------

def load_authorized_users(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        users = data
    elif isinstance(data, dict) and isinstance(data.get("authorized_users"), list):
        users = data["authorized_users"]
    else:
        raise ValueError(
            f"Formato non riconosciuto in {path}: atteso un array JSON oppure "
            '{"authorized_users": [...]}.'
        )
    return [str(u) for u in users]


def check_authorization(calling_actor: str, authorized_users_file: str, collector: IssueCollector) -> bool:
    """Ritorna True se l'attore è autorizzato, False altrimenti (errore già registrato)."""
    try:
        authorized_users = load_authorized_users(authorized_users_file)
    except FileNotFoundError:
        collector.error(
            authorized_users_file,
            f"File degli utenti autorizzati non trovato: {authorized_users_file}",
        )
        return False
    except (ValueError, json.JSONDecodeError) as exc:
        collector.error(authorized_users_file, f"File degli utenti autorizzati non valido: {exc}")
        return False

    if calling_actor not in authorized_users:
        collector.error(
            "authorization",
            f"L'utente '{calling_actor}' non è tra i soggetti autorizzati a proporre "
            "file influmeter. Contatta i maintainer per essere aggiunto all'elenco.",
        )
        return False
    return True


# --------------------------------------------------------------------------
# Selezione dei file da validare
# --------------------------------------------------------------------------

def parse_changed_files(raw: str) -> list[str]:
    if not raw:
        return []
    # tj-actions/changed-files espone i path separati da spazio (default output_renamer)
    parts = raw.replace("\n", " ").split()
    return [p.strip().strip('"').lstrip("./") for p in parts if p.strip()]


def select_influmeter_files(changed_files: list[str]) -> list[str]:
    return [f for f in changed_files if FILE_PATTERN.match(f)]


# --------------------------------------------------------------------------
# Validazione di un singolo file
# --------------------------------------------------------------------------

def parse_date(value: str) -> Optional[date]:
    try:
        from datetime import datetime

        return datetime.strptime(value, DATE_FORMAT).date()
    except (ValueError, TypeError):
        return None


def validate_file(path: str, collector: IssueCollector) -> None:
    match = FILE_PATTERN.match(path)
    assert match is not None
    file_year = int(match.group("year"))
    file_week = int(match.group("week"))

    try:
        reference_monday = date.fromisocalendar(file_year, file_week, 1)
    except ValueError:
        collector.error(
            path,
            f"Anno/settimana nel nome file non validi: {file_year}_{file_week:02d}",
        )
        reference_monday = None

    if not os.path.isfile(path):
        collector.error(path, f"File non trovato nel checkout: {path}")
        return

    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []

        missing_cols = [c for c in EXPECTED_COLUMNS if c not in header]
        extra_cols = [c for c in header if c not in EXPECTED_COLUMNS]
        if missing_cols:
            collector.error(path, f"Colonne mancanti nell'header: {missing_cols}", line=1)
        if extra_cols:
            collector.warning(path, f"Colonne non attese nell'header: {extra_cols}", line=1)
        if missing_cols:
            # senza le colonne minime non ha senso proseguire con questo file
            return

        rows = list(reader)

    if not rows:
        collector.error(path, "Il file non contiene righe di dati (solo header o vuoto).")
        return

    seen_combos: dict[tuple[str, int], int] = {}
    rows_by_location: dict[str, dict[int, dict]] = {}

    for idx, row in enumerate(rows):
        line_no = idx + 2  # +1 header, +1 per indicizzazione 1-based
        _validate_row(path, line_no, row, reference_monday, seen_combos, rows_by_location, collector)

    _validate_completeness(path, seen_combos, collector)
    _validate_cross_horizon_consistency(path, rows_by_location, collector)


def _validate_row(
    path: str,
    line_no: int,
    row: dict,
    reference_monday: Optional[date],
    seen_combos: dict[tuple[str, int], int],
    rows_by_location: dict[str, dict[int, dict]],
    collector: IssueCollector,
) -> None:
    def err(msg: str) -> None:
        collector.error(path, msg, line=line_no)

    def warn(msg: str) -> None:
        collector.warning(path, msg, line=line_no)

    model_id = (row.get("model_id") or "").strip()
    if model_id not in VALID_MODEL_IDS:
        err(f"model_id non valido: '{model_id}' (atteso uno tra {sorted(VALID_MODEL_IDS)})")

    target = (row.get("target") or "").strip()
    if target not in VALID_TARGETS:
        err(f"target non valido: '{target}' (atteso uno tra {sorted(VALID_TARGETS)})")

    location_id = (row.get("location_id") or "").strip()
    if location_id not in VALID_LOCATIONS:
        err(f"location_id non valido: '{location_id}'")

    horizon_raw = (row.get("horizon") or "").strip()
    horizon: Optional[int] = None
    try:
        horizon = int(horizon_raw)
        if horizon not in VALID_HORIZONS:
            err(f"horizon fuori range: {horizon} (atteso uno tra {sorted(VALID_HORIZONS)})")
            horizon = None
    except ValueError:
        err(f"horizon non è un intero valido: '{horizon_raw}'")

    start_date = parse_date((row.get("start_date") or "").strip())
    end_date = parse_date((row.get("end_date") or "").strip())
    if start_date is None:
        err(f"start_date non valida o formato errato (atteso {DATE_FORMAT}): '{row.get('start_date')}'")
    if end_date is None:
        err(f"end_date non valida o formato errato (atteso {DATE_FORMAT}): '{row.get('end_date')}'")

    if start_date is not None and end_date is not None:
        if end_date <= start_date:
            err(f"end_date ({end_date}) non successiva a start_date ({start_date})")
        elif (end_date - start_date).days != 6:
            err(
                f"end_date - start_date = {(end_date - start_date).days} giorni, "
                "atteso 6 (settimana completa)"
            )

    probs: dict[str, float] = {}
    for col in PROB_COLUMNS:
        raw_val = (row.get(col) or "").strip()
        try:
            value = float(raw_val)
            if not (0.0 <= value <= 100.0):
                err(f"{col} fuori range [0,100]: {value}")
            probs[col] = value
        except ValueError:
            err(f"{col} non è un numero valido: '{raw_val}'")

    if len(probs) == len(PROB_COLUMNS):
        total = sum(probs.values())
        if abs(total - PROB_SUM_TARGET) > PROB_SUM_TOLERANCE:
            err(
                f"Somma probabilità = {total:.2f}, attesa {PROB_SUM_TARGET} "
                f"± {PROB_SUM_TOLERANCE}"
            )

    influmeter_index: Optional[float] = None
    raw_index = (row.get("influmeter_index") or "").strip()
    try:
        influmeter_index = float(raw_index)
        if not (0.0 <= influmeter_index <= 100.0):
            err(f"influmeter_index fuori range [0,100]: {influmeter_index}")
    except ValueError:
        err(f"influmeter_index non è un numero valido: '{raw_index}'")

    if influmeter_index is not None and len(probs) == len(PROB_COLUMNS):
        expected_col = None
        for low, high, col in INDEX_BUCKETS:
            if (low <= influmeter_index < high) or (influmeter_index == 100.0 and high == 100.0):
                expected_col = col
                break
        if expected_col is not None:
            max_col = max(probs, key=probs.get)
            if max_col != expected_col:
                warn(
                    f"influmeter_index={influmeter_index} suggerisce fascia '{expected_col}', "
                    f"ma la probabilità massima è su '{max_col}' ({probs[max_col]:.1f}%)"
                )

    # Coerenza settimana di riferimento (da nome file) vs start_date atteso per l'horizon
    if reference_monday is not None and horizon is not None and start_date is not None:
        expected_start = reference_monday + timedelta(days=7 * horizon)
        if start_date != expected_start:
            warn(
                f"start_date ({start_date}) non coincide con quanto atteso dal nome file "
                f"per horizon={horizon} (atteso {expected_start}); verificare la convenzione "
                "di riferimento tra settimana del filename e horizon."
            )

    # Duplicati / raccolta per controlli successivi
    if horizon is not None and location_id in VALID_LOCATIONS:
        combo = (location_id, horizon)
        seen_combos[combo] = seen_combos.get(combo, 0) + 1
        if seen_combos[combo] > 1:
            err(f"Riga duplicata per combinazione location_id={location_id}, horizon={horizon}")
        rows_by_location.setdefault(location_id, {})[horizon] = {
            "start_date": start_date,
            "end_date": end_date,
        }


def _validate_completeness(
    path: str, seen_combos: dict[tuple[str, int], int], collector: IssueCollector
) -> None:
    missing = []
    for location_id in sorted(VALID_LOCATIONS):
        for horizon in sorted(VALID_HORIZONS):
            if (location_id, horizon) not in seen_combos:
                missing.append((location_id, horizon))
    if missing:
        preview = ", ".join(f"({loc},h{h})" for loc, h in missing[:10])
        more = f" e altre {len(missing) - 10}" if len(missing) > 10 else ""
        collector.error(
            path,
            f"Combinazioni location_id x horizon mancanti ({len(missing)} su "
            f"{len(VALID_LOCATIONS) * len(VALID_HORIZONS)} attese): {preview}{more}",
        )


def _validate_cross_horizon_consistency(
    path: str, rows_by_location: dict[str, dict[int, dict]], collector: IssueCollector
) -> None:
    for location_id, by_horizon in rows_by_location.items():
        horizons = sorted(by_horizon.keys())
        for h1, h2 in zip(horizons, horizons[1:]):
            if h2 != h1 + 1:
                continue  # confrontiamo solo horizon consecutivi effettivamente presenti
            s1 = by_horizon[h1]["start_date"]
            s2 = by_horizon[h2]["start_date"]
            if s1 is not None and s2 is not None and (s2 - s1).days != 7:
                collector.error(
                    path,
                    f"location_id={location_id}: start_date per horizon={h2} ({s2}) non è "
                    f"7 giorni dopo horizon={h1} ({s1})",
                )


# --------------------------------------------------------------------------
# Output verso GitHub Actions (step id: authenticate)
# --------------------------------------------------------------------------

def write_github_output(authenticate: str, message: str) -> None:
    """Scrive gli output `authenticate` e `message` su $GITHUB_OUTPUT, se
    presente (cioè quando lo script gira dentro un job di GitHub Actions)."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    delimiter = f"EOF_{uuid.uuid4().hex}"
    with open(output_path, "a", encoding="utf-8") as fh:
        fh.write(f"authenticate={authenticate}\n")
        fh.write(f"message<<{delimiter}\n{message}\n{delimiter}\n")


def running_in_actions() -> bool:
    return bool(os.environ.get("GITHUB_OUTPUT"))


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> int:
    calling_actor = os.environ.get("calling_actor", "")
    changed_files_raw = os.environ.get("changed_files", "")
    authorized_users_file = os.environ.get("AUTHORIZED_USERS_FILE", DEFAULT_AUTHORIZED_USERS_FILE)

    collector = IssueCollector()

    def finish() -> int:
        """Riporta l'esito, scrive gli output per il workflow e determina
        l'exit code (sempre 0 dentro Actions, si veda il docstring del modulo)."""
        collector.report()
        success = not collector.has_errors()
        write_github_output("success" if success else "failure", collector.summary_message())
        if running_in_actions():
            return 0
        return 0 if success else 1

    if not calling_actor:
        collector.error("input", "Variabile d'ambiente 'calling_actor' mancante o vuota.")
        return finish()

    if not check_authorization(calling_actor, authorized_users_file, collector):
        return finish()

    changed_files = parse_changed_files(changed_files_raw)
    influmeter_files = select_influmeter_files(changed_files)

    if not influmeter_files:
        collector.error(
            "input",
            "Nessun file CSV nel path atteso 'previsioni/influmeter/YYYY_WW.csv' tra i "
            f"file modificati dalla PR. File modificati: {changed_files or '(nessuno)'}",
        )
        return finish()

    for path in influmeter_files:
        validate_file(path, collector)

    return finish()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - salvaguardia per errori inattesi
        # Anche in caso di bug/eccezione imprevista nello script, comunichiamo
        # l'esito come "failure" invece di lasciare il job in stato crashed,
        # così i job downstream del workflow (che dipendono dagli output, non
        # dall'exit code) possono comunque girare e commentare la PR.
        write_github_output("failure", f"Errore interno nello script di validazione: {exc}")
        sys.exit(0 if running_in_actions() else 1)
