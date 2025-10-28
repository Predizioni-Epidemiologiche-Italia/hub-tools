import pandas as pd 
from datetime import datetime, timedelta
from isoweek import Week
import os
import argparse

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--hub_path')
parser.add_argument('--season', type=str, default="2025-2026", help='Season')
parser.add_argument('--horizon_range', type=int, nargs='+', default=[-1, 0, 1, 2, 3, 4], help='Horizon range')

args = parser.parse_args()

# get input parameters
season = args.season
horizon_range = args.horizon_range

fw_file_path = os.path.join(args.hub_path, "supporting-files/forecasting_weeks.csv")

# read last file
df = pd.read_csv(fw_file_path)

# get year, week of last observation
year_last, week_last = df.loc[df.is_latest == True][["year", "week"]].iloc[0]

# get forecasting round of last observation
forecast_round_last = df.loc[df.is_latest == True]["forecast_round"].iloc[0]

# get next iso week 
iso_week = Week(year=int(year_last), week=int(week_last)) + 1
iso_week_end = iso_week.days()[-1]
year, week = iso_week.year, iso_week.week

# create dataframe
years, weeks, horizons, horizon_end_dates, is_latest, forecast_round = [], [], [], [], [], []
for horizon in horizon_range:
    years.append(year)
    weeks.append(week)
    horizons.append(horizon)
    horizon_end_dates.append(iso_week_end + timedelta(days=7*horizon))
    is_latest.append(True)
    forecast_round.append(forecast_round_last + 1)

df_forecasting_weeks = pd.DataFrame(data={"year": year, 
                                          "week": week, 
                                          "horizon": horizons, 
                                          "horizon_end_date": horizon_end_dates, 
                                          "is_latest": is_latest, 
                                          "forecast_round": forecast_round, 
                                          "season": season})
# last format and concat
df["is_latest"] = False 
df_final = pd.concat((df_forecasting_weeks, df))
df_final.to_csv(fw_file_path, index=False)
