import pandas as pd 
import numpy as np 
import os
from isoweek import Week
from datetime import date
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--season')
parser.add_argument('--target_name', default="incidenza")
parser.add_argument('--symmetrize', default=True)
parser.add_argument('--nsamples', default=10000)
parser.add_argument('--horizon', default=4)
parser.add_argument('--team_abbr', default="Influcast")
parser.add_argument('--model_abbr', default="quantileBaseline")

args = parser.parse_args()
season = str(args.season)
horizon = int(args.horizon)
symmetrize = bool(args.symmetrize)
nsamples = int(args.nsamples)
team_abbr = str(args.team_abbr)
model_abbr = str(args.model_abbr)
target_name = str(args.target_name)


path = f"https://raw.githubusercontent.com/Predizioni-Epidemiologiche-Italia/Influcast/main/sorveglianza/{season}/latest/"

basin_ids = {'italia': "IT",
            'abruzzo': "01",
            'basilicata': "02",
            'calabria': "03",
            'campania': "04",
            'emilia_romagna': "05",
            'friuli_venezia_giulia': "06",
            'lazio': "07", 
            'liguria': "08", 
            'lombardia': "09", 
            'marche': "10",
            'molise': "11",
            'pa_bolzano': "12",
            'pa_trento': "13",
            'piemonte': "14",
            'puglia': "15",
            'sardegna': "16",
            'sicilia': "17",
            'toscana': "18",
            'umbria': "19",
            'valle_d_aosta': "20",
            'veneto': "21"}

def quantile_baseline(data : np.ndarray, 
                      nsamples : int, 
                      horizon : int, 
                      symmetrize : bool = True, 
                      include_training : bool = True) -> np.ndarray:
    
    """
    Compute baseline forecasts

    Parameters:
    - data (np.ndarray): training data 
    - nsamples (int): number of forecasting samples
    - horizon (int): forecasting horizon in steps 
    - symmetrize (bool): if True one-step differences are symmetrized. (Defaults to True).
    - include_training (bool): if True includes also training data in returned array. (Defaults to True).

    Returns:
    -  np.ndarray: forecast samples.
    """

    # compute one step changes 
    diffs = np.diff(data)

    if symmetrize  == True: 
        diffs = np.concatenate((diffs, -diffs))

    # resample forecasts
    if include_training == True:
        forecast_samples = np.zeros((nsamples, len(data) + horizon))
    else:
        forecast_samples = np.zeros((nsamples, horizon))

    for i in range(nsamples): 
        sampled_diffs = diffs[np.random.randint(0, len(diffs), size=horizon)]
        forecasts = np.cumsum(sampled_diffs)
        forecasts += data[-1]

        # fix negative values
        forecasts[forecasts<0] = 0 

        if include_training:
            forecast_samples[i] = np.concatenate((data, forecasts))
        else:
            forecast_samples[i] = forecasts

    return forecast_samples


def compute_quantiles(samples : np.ndarray, 
                      quantiles: np.ndarray = np.arange(0.01, 1.0, 0.01)) -> pd.DataFrame:
    """
    Compute quantiles and aggregated measures from the given samples.

    Parameters:
    - samples (np.ndarray): Array of samples.
    - quantiles (np.ndarray): Array of quantiles to compute. Default is np.arange(0.01, 1.0, 0.01).

    Returns:
    - pd.DataFrame: DataFrame containing the computed quantiles and aggregated measures.
    """

    df_samples = pd.DataFrame() 
    for q in quantiles:
        df_samples[str(np.round(q, 2))] = np.quantile(samples, axis=0, q=np.round(q, 2))
    
    # additional quantiles and aggregated measures
    df_samples["0.025"] = np.quantile(samples, axis=0, q=0.025)
    df_samples["0.975"] = np.quantile(samples, axis=0, q=0.975)
    df_samples["min"] = np.min(samples, axis=0)
    df_samples["max"] = np.max(samples, axis=0)

    return df_samples


def generate_baseline_quantile_forecast(training_data, 
                                        nsamples, 
                                        horizon, 
                                        symmetrize, 
                                        include_training=False):
    """
    Run full pipeline for quantile baseline forecast

    Parameters:
    - training_data: training data
    - nsamples (int): number of forecasting samples
    - horizon (int): forecasting horizon in steps 
    - symmetrize (bool): if True one-step differences are symmetrized. (Defaults to True).
    - include_training (bool): if True includes also training data in returned array. (Defaults to True).

    Returns:
    - pd.DataFrame: DataFrame containing the computed quantiles and aggregated measures.
    """

    # generate forecasts
    forecast_samples = quantile_baseline(training_data, nsamples, horizon, symmetrize, include_training=include_training)

    # compute quantiles
    forecast_quantiles = compute_quantiles(forecast_samples)
    return forecast_quantiles


def format_filename(file, 
                    run_name, 
                    season, 
                    div="_", 
                    extension=".csv"):
    year_week = file.replace(run_name + "_" + season + "_", "").split("_")[0]
    filename = year_week[:4] + div + year_week[4:] + extension
    return filename

def format_file(anno_forecast, 
                settimana_forecast,
                data_forecast,
                basin_id,
                quantiles = [0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3,
                             0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 
                             0.75, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99]):
    
    data_forecast.sort_values(by="data_inizio", inplace=True, ascending=True)	

    anno, settimana, luogo, tipo_valore, id_valore, orizzonte, valore = [], [], [], [], [], [], []
    for q in quantiles:
        for horizon in [0, 1, 2, 3]:

            anno.append(int(anno_forecast))
            settimana.append(int(settimana_forecast))
            luogo.append(basin_id)
            tipo_valore.append("quantile")
            id_valore.append(q)
            orizzonte.append(horizon + 1)
            valore.append(data_forecast[str(q)].values[horizon])

    df_formatted = pd.DataFrame(data={"anno": anno, 
                                      "settimana": settimana, 
                                      "luogo": luogo, 
                                      "tipo_valore": tipo_valore, 
                                      "id_valore": id_valore, 
                                      "orizzonte": orizzonte, 
                                      "valore": valore})

    return df_formatted


def generate_baseline_forecast_fullpipeline(season, 
                                            year_forecast, 
                                            week_forecast, 
                                            basin_name,
                                            target_name="incidenza", 
                                            nsamples=1000,
                                            horizon=4,
                                            symmetrize=True): 
    
    # read ground truth data and weeks
    isoweeks = pd.read_csv(f"https://raw.githubusercontent.com/Predizioni-Epidemiologiche-Italia/Influcast/main/previsioni/settimane_{season}.csv")
    truth_data = pd.read_csv(os.path.join(path, basin_name + "-latest.csv"))

    if truth_data.shape[0] <= 1: 
        return pd.DataFrame()
    
    # generate baseline forecast
    baseline_forecast = generate_baseline_quantile_forecast(training_data=truth_data[target_name].values, 
                                                            nsamples=nsamples, 
                                                            horizon=horizon, 
                                                            symmetrize=symmetrize)
    
    # add weeks
    start_idx = isoweeks.loc[(isoweeks.anno == truth_data.anno.values[-1]) & \
                             (isoweeks.settimana == truth_data.settimana.values[-1])].index[0]
    baseline_forecast = pd.merge(left=baseline_forecast, 
                                 right=isoweeks.iloc[start_idx+1:start_idx+1+4].reset_index(drop=True), 
                                 left_index=True, right_index=True)
    
    # format file
    baseline_forecast_formatted = format_file(anno_forecast=year_forecast, 
                                              settimana_forecast=week_forecast,
                                              data_forecast=baseline_forecast, 
                                              basin_id=basin_ids[basin_name])
    return baseline_forecast_formatted


# get date
iso_year, iso_week, _ = date.today().isocalendar()
week = Week(iso_year, iso_week) - 2

# compute quantile baseline
baseline_forecast_formatted = pd.DataFrame()
for region in basin_ids.keys():
    baseline_reg = generate_baseline_forecast_fullpipeline(
                                            season=season, 
                                            year_forecast=week.year, 
                                            week_forecast=week.week, 
                                            basin_name=region,
                                            target_name=target_name, 
                                            nsamples=nsamples,
                                            horizon=horizon,
                                            symmetrize=symmetrize)
    
    baseline_forecast_formatted = pd.concat((baseline_forecast_formatted, baseline_reg), ignore_index=False)

if week.week < 10: 
    year_week = str(week.year) + "_0" + str(week.week)
else: 
    year_week = str(week.year) + "_" + str(week.week)
baseline_forecast_formatted.to_csv(f"./repo/previsioni/{team_abbr}-{model_abbr}/{year_week}.csv", index=False)

env_file = os.getenv('GITHUB_OUTPUT')
with open(env_file, "a") as outenv:
   outenv.write (f"baseline_file={year_week}.csv")

