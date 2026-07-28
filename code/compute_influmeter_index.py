"""
Compute the InfluMeter index and MEM activity band probabilities for each
region and forecast horizon, for a given Influcast forecasting week.

Standalone script: reads the ensemble forecast directly from the Influcast
GitHub repository and writes a CSV matching the Influcast dashboard data
schema (model_id, horizon, start_date, end_date, location_id, target,
p_baseline, p_low, p_medium, p_high, p_very_high, influmeter_index).

Usage:
    python compute_influmeter_index.py <forecasting_week> <output_path>

Example:
    python compute_influmeter_index.py 2026_09 ./output/2026_09_influmeter.csv
"""

import argparse
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

ENSEMBLE_URL = "https://raw.githubusercontent.com/Predizioni-Epidemiologiche-Italia/Influcast/refs/heads/main/previsioni/Influcast-Ensemble/{}.csv"

MODEL_ID = "ensemble"
TARGET = "ARI"
HORIZONS = [1, 2, 3, 4]

LEVELS = ["baseline", "low", "medium", "high", "very_high"]
WKS = [0., 20., 40., 60., 80., 100.]

# MEM thresholds, in casi per mille assistiti (same unit as forecasted incidence).
MEM_THRESHOLDS = {
    "2025-2026": {
        "baseline": [0., 7.22],
        "low": [7.22, 13.35],
        "medium": [13.35, 17.43],
        "high": [17.43, 19.61],
        "very_high": [19.61, float("inf")],
    },
}

# Full quantile spread published by the ensemble; treated as the entire
# probability mass (0% to 100%) when computing band probabilities.
QUANTILE_MIN = 0.01
QUANTILE_MAX = 0.99


def resolve_season(forecasting_week):
    """
    Resolve the surveillance season from a forecasting week id "YYYY_WW".

    Surveillance seasons start around week 40, so a week number greater
    than 35 is assigned to the season starting that year; otherwise it
    belongs to the season that started the previous year.
    """
    year_str, week_str = forecasting_week.split("_")
    year, week = int(year_str), int(week_str)
    if week > 35:
        return f"{year}-{year + 1}"
    return f"{year - 1}-{year}"


def get_influmeter_index(value, thresholds):
    """
    Map an incidence value to the InfluMeter index (0-100) and MEM level,
    via piecewise-linear interpolation within the matching MEM band.
    """
    for idx, level in enumerate(LEVELS):
        lo, hi = thresholds[level]
        if value >= lo and value < hi:
            if np.isinf(hi):
                return WKS[idx + 1], level
            frac = (value - lo) / (hi - lo)
            index = WKS[idx] + (WKS[idx + 1] - WKS[idx]) * frac
            return index, level
    # value below the lowest threshold's lower bound (shouldn't happen, lo=0)
    return WKS[0], LEVELS[0]


def compute_band_probabilities(quantiles, values, thresholds):
    """
    Compute the probability (%) of the true value falling in each MEM band,
    from a set of predictive quantiles.

    The quantile spread [QUANTILE_MIN, QUANTILE_MAX] is rescaled to
    represent the full [0, 1] probability mass, with no further tail
    adjustment.
    """
    quantiles = np.asarray(quantiles, dtype=float)
    values = np.asarray(values, dtype=float)

    mask = (quantiles >= QUANTILE_MIN) & (quantiles <= QUANTILE_MAX)
    quantiles, values = quantiles[mask], values[mask]

    order = np.argsort(quantiles)
    quantiles, values = quantiles[order], values[order]

    cdf = (quantiles - QUANTILE_MIN) / (QUANTILE_MAX - QUANTILE_MIN)

    def F(x):
        if np.isinf(x):
            return 1.0
        return float(np.interp(x, values, cdf, left=0.0, right=1.0))

    probs = {}
    for level in LEVELS:
        lo, hi = thresholds[level]
        probs[level] = max(0.0, (F(hi) - F(lo)) * 100)

    total = sum(probs.values())
    if total > 0:
        probs = {level: p * 100 / total for level, p in probs.items()}
    return probs


def target_week_dates(year, week, horizon):
    """
    Compute the start (Monday) and end (Sunday) dates of the target week,
    i.e. `horizon` ISO weeks after the forecasting round's issue week.
    """
    issue_monday = date.fromisocalendar(year, week, 1)
    target_monday = issue_monday + timedelta(weeks=horizon)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday.isoformat(), target_sunday.isoformat()


def fetch_ensemble(forecasting_week):
    url = ENSEMBLE_URL.format(forecasting_week)
    try:
        return pd.read_csv(url)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load ensemble forecast for round '{forecasting_week}' from {url}: {exc}"
        ) from exc


def compute_influmeter(forecasting_week):
    season = resolve_season(forecasting_week)
    if season not in MEM_THRESHOLDS:
        raise ValueError(
            f"No MEM thresholds defined for season '{season}' "
            f"(resolved from forecasting week '{forecasting_week}'). "
            f"Available seasons: {list(MEM_THRESHOLDS.keys())}"
        )
    thresholds = MEM_THRESHOLDS[season]

    df = fetch_ensemble(forecasting_week)
    df = df[
        (df["target"] == TARGET)
        & (df["tipo_valore"] == "quantile")
        & (df["orizzonte"].isin(HORIZONS))
    ]

    rows = []
    for (location, horizon), group in df.groupby(["luogo", "orizzonte"]):
        year = int(group["anno"].iloc[0])
        week = int(group["settimana"].iloc[0])
        start_date, end_date = target_week_dates(year, week, int(horizon))

        median_rows = group[group["id_valore"] == 0.5]
        if median_rows.empty:
            continue
        median_value = median_rows["valore"].iloc[0]
        influmeter_index, _ = get_influmeter_index(median_value, thresholds)

        probs = compute_band_probabilities(
            group["id_valore"].values, group["valore"].values, thresholds
        )

        rows.append({
            "model_id": MODEL_ID,
            "horizon": int(horizon),
            "start_date": start_date,
            "end_date": end_date,
            "location_id": location,
            "target": TARGET,
            "p_baseline": round(probs["baseline"], 2),
            "p_low": round(probs["low"], 2),
            "p_medium": round(probs["medium"], 2),
            "p_high": round(probs["high"], 2),
            "p_very_high": round(probs["very_high"], 2),
            "influmeter_index": round(influmeter_index, 2),
        })

    result = pd.DataFrame(rows, columns=[
        "model_id", "horizon", "start_date", "end_date", "location_id",
        "target", "p_baseline", "p_low", "p_medium", "p_high",
        "p_very_high", "influmeter_index",
    ])
    result.sort_values(by=["location_id", "horizon"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute the InfluMeter index and MEM band probabilities for a forecasting round."
    )
    parser.add_argument("forecasting_week", help="Forecasting round id, e.g. 2026_09")
    parser.add_argument("output_path", help="Path to write the output CSV to")
    args = parser.parse_args()

    try:
        df = compute_influmeter(args.forecasting_week)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    df.to_csv(args.output_path, index=False)
    print(f"Wrote {len(df)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
