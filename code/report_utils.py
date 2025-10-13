import pandas as pd
from datetime import date
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import TwoSlopeNorm

regions = {"IT": "Italy", 
            "01": "Abruzzo",
            "02": "Basilicata",
            "03": "Calabria",
            "04": "Campania",
            "05": "Emilia-Romagna",
            "06": "Friuli-Venezia Giulia",
            "07": "Lazio",
            "08": "Liguria",
            "09": "Lombardia",
            "10": "Marche",
            "11": "Molise",
            "12": "P.A. Bolzano",
            "13": "P.A. Trento",
            "14": "Piemonte",
            "15": "Puglia",
            "16": "Sardegna",
            "17": "Sicilia",
            "18": "Toscana",
            "19": "Umbria",
            "20": "Valle d'Aosta",
            "21": "Veneto"}


def compute_leaderboard(scores_rel: pd.DataFrame, 
                        target_name: str, 
                        location_code: str = "IT", 
                        groupby_round: bool = False) -> pd.DataFrame:
    df = scores_rel.query("target == @target_name and location == @location_code").copy()
    if groupby_round:
        df = df.groupby(["model", "forecast_week"], as_index=False).mean(numeric_only=True)
        
    df = df.groupby(["model"], as_index=False)\
                .agg({"rel_wis": "median",
                      "rel_ae_median": "median",
                      "interval_coverage_50": "mean",
                      "interval_coverage_90": "mean",
                    })

    df["rel_wis"] = df["rel_wis"].round(3)
    df["rel_ae_median"] = df["rel_ae_median"].round(3)
    df["interval_coverage_50"] = (100 * df["interval_coverage_50"]).round(1)
    df["interval_coverage_90"] = (100 * df["interval_coverage_90"]).round(1)
    df.rename(columns={"model": "Model", 
                        "rel_wis": "Rel. WIS",
                        "rel_ae_median": "Rel. MAE",
                        "interval_coverage_50": "Cov. (50%)",
                        "interval_coverage_90": "Cov. (90%)",
                        }, inplace=True)
    return df.sort_values("Rel. WIS", ascending=True).reset_index(drop=True)


def plot_performance_by_forecast_week(scores_rel: pd.DataFrame, 
                                      target_name: str, 
                                      location_code: str = "IT", 
                                      metric: str = "rel_wis",
                                      ax: plt.Axes = None, 
                                      styles: dict = None, 
                                      default_style: dict = None, 
                                      title: str = None, 
                                      xlabel: str = "Forecast Week", 
                                      ylabel: str = None, 
                                      use_log_scale: bool = True):
    # locate scores for target and location
    scores_target = scores_rel.loc[(scores_rel.location == location_code) & \
                                   (scores_rel.target == target_name)]
    # group by forecast week and model
    scores_weeks = scores_target.groupby(["model", "forecast_week"], 
                                         as_index=False).mean(numeric_only=True)
    scores_weeks.sort_values(by="forecast_week", inplace=True, ignore_index=True, ascending=True)

    # isolate submitting models to compute average 
    scores_weeks_models = scores_target.loc[~scores_target.model.isin(["Influcast-quantileBaseline", "Influcast-Ensemble"])]
    scores_weeks_models = scores_weeks_models.groupby("forecast_week", as_index=False).mean(numeric_only=True)
    scores_weeks_models.sort_values(by="forecast_week", inplace=True, ignore_index=True, ascending=True)

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    if styles is None:
        styles = {"Influcast-quantileBaseline": {"color": "coral", "alpha": 1.0, "linestyle": "--", "label": "Baseline"},
                  "Influcast-Ensemble": {"color": "#028A0F", "alpha": 1.0, "linestyle": "solid", "label": "Ensemble"}, 
                  "Other Models Average": {"color": "k", "alpha": 0.8, "linestyle": "dotted", "label": "Other Models Average"}}
    if default_style is None:
        default_style = {"color": "grey", "alpha": 0.1, "linestyle": "solid", "label": None}

    for model in scores_weeks.model.unique():
        style = styles.get(model, default_style)
        sns.lineplot(x="forecast_week", y=metric, data=scores_weeks[scores_weeks.model == model], 
                    label=style["label"], ax=ax, color=style["color"], 
                    alpha=style["alpha"], linestyle=style["linestyle"])

    sns.lineplot(x="forecast_week", y=metric, data=scores_weeks_models, 
                label=styles["Other Models Average"]["label"], ax=ax, color="k", 
                alpha=styles["Other Models Average"]["alpha"], linestyle=styles["Other Models Average"]["linestyle"])
    
    ax.set_title(title if title else f"{metric} by Forecast Week", x=0, ha="left", weight="bold")
    ax.set_xlabel(xlabel if xlabel else "Forecast Week")
    ax.set_ylabel(ylabel if ylabel else f"{metric}")
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.5, axis="y", linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False)
    
    if use_log_scale:
        ax.set_yscale("log")


def plot_performance_by_region(scores_rel: pd.DataFrame, 
                               target_name: str = "ILI", 
                               metric: str = "rel_wis",
                               title: str = None, 
                               ax: plt.Axes = None, 
                               groupby_round: bool = False):

    scores_regions = scores_rel.query("location != 'IT' and target == @target_name")

    if groupby_round:
        scores_regions = scores_regions.groupby(["model", "forecast_week", "location"], as_index=False).mean(numeric_only=True)

    scores_regions = scores_regions.groupby(["model", "location"], as_index=False).median(numeric_only=True)
    scores_pivot = scores_regions.pivot(index="model", columns="location", values="rel_wis")

    # rename regions
    scores_pivot.rename(index=regions, columns=regions, inplace=True)

    # Order models (rows) and locations (cols) by their average performance (ascending = better first)
    row_order = scores_pivot.median(axis=1, skipna=True).sort_values(ascending=True).index
    col_order = scores_pivot.median(axis=0, skipna=True).sort_values(ascending=True).index
    scores_pivot_ord = scores_pivot.loc[row_order, col_order]

    norm = TwoSlopeNorm(
        vmin=scores_pivot.min().min(),
        vcenter=1.0,            
        vmax=scores_pivot.max().max()
    )

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 3), dpi=300)
    sns.heatmap(scores_pivot_ord, cmap="coolwarm", annot=True, fmt=".1f", cbar=False, norm=norm, ax=ax)
    ax.set_title(title if title else f"Relative {metric} by Region ({target_name})", x=0, ha="left", weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis='x', rotation=90)


def plot_wis_components(scores_aggr, model, location, target, ax=None):
    scores_aggr_plot = scores_aggr.loc[(scores_aggr.location == location) & \
                                       (scores_aggr.target == target) & \
                                       (scores_aggr.model == model)]

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 8), dpi=300)

    scores_aggr_plot.set_index('model')[["overprediction", 
                                         "underprediction", 
                                          "dispersion"]].plot(kind='bar', stacked=True, cmap="Paired", ax=ax)

    ax.set_title(f"WIS Components for {model} ({target}, {location})", weight="bold", x=0, ha="left")
    ax.set_xlabel("")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.7)