import pandas as pd 
from datetime import datetime, timedelta
from isoweek import Week
import os
import argparse

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--hub_path')
args = parser.parse_args()

horizon_range = [-1,0,1,2,3,4]

# read last file
df = pd.read_csv(os.path.join(args.hub_path, "supporting-files/forecasting_weeks.csv"))

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
                                          "forecast_round": forecast_round})
# last format and concat
df["is_latest"] = False 
df_final = pd.concat((df_forecasting_weeks, df))
df_final.to_csv(os.path.join(args.hub_path, "supporting-files/forecasting_weeks.csv"), index=False)

