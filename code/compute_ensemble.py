import os
import pandas as pd 
import os 
import json
from datetime import date
from isoweek import Week
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--team_abbr', default="Influcast")
parser.add_argument('--model_abbr', default="Ensemble")

args = parser.parse_args()
model_abbr = str(args.model_abbr)
team_abbr = str(args.team_abbr)

path = "https://raw.githubusercontent.com/Predizioni-Epidemiologiche-Italia/Influcast/main/previsioni/"

models = ["CSL_PoliTo-metaFlu", 
          "EpiQMUL-ARIMA_QMUL", 
          "EpiQMUL-SEIR_QMUL", 
          "ISI-FluABCaster", 
          "ISI-GLEAM", 
          "ISI-IPSICast", 
          "Richards_pmf-glm_rich", 
          "ev_and_modelers-DeepRE"]

# compute year_week 
iso_year, iso_week, _ = date.today().isocalendar()
week = Week(iso_year, iso_week) - 2
if week.week < 10: 
    year_week = str(week.year) + "_0" + str(week.week)
else: 
    year_week = str(week.year) + "_" + str(week.week)

#year_week = "2023_46"
model_predictions = pd.DataFrame() 
for model in models: 
    try: 
        df_model = pd.read_csv(os.path.join(path, model, year_week + ".csv"))
        df_model["model"] = model
        model_predictions = pd.concat((model_predictions, df_model), ignore_index=True)
    except: 
        print("Not found: ", model)

ensemble_predictions = model_predictions.groupby(["anno", "settimana", "luogo", 
                                                  "tipo_valore", "id_valore", 
                                                  "orizzonte"], as_index=False).mean()
ensemble_predictions.to_csv(f"./repo/previsioni/{team_abbr}-{model_abbr}/{year_week}.csv", index=False)
                                Influcast-Ensemble


unique_horizons = model_predictions.orizzonte.unique()
unique_regions = model_predictions.luogo.unique()

ensemble_members = [{"regions": []}]

for region in unique_regions:
    temp_dict_reg = {}
    temp_dict_reg["id"] = region
    temp_dict_reg["members"] = []
    for horizon in unique_horizons:
        temp_dict_reg["members"].append({"horizon": int(horizon), 
                                         "models": list(model_predictions.loc[(model_predictions.luogo == region) & \
                                                                              (model_predictions.orizzonte == horizon)].model.unique())})
        
    ensemble_members[0]["regions"].append(temp_dict_reg)


with open(f"./repo/.github/logs/ensemble_members/{year_week}.json", "w") as file:
    json.dump(ensemble_members, file)


env_file = os.getenv('GITHUB_OUTPUT')
with open(env_file, "a") as outenv:
   outenv.write (f"ensemble_file={year_week}.csv")
