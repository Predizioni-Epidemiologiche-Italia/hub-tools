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

models = ["comunipd-mobnetSI2R",
          "CSL_PoliTo-metaFlu", 
          "EpiQMUL-ARIMA_QMUL", 
          "EpiQMUL-SEIR_QMUL",
          "EpiQMUL-SEIRaugment_QMUL", 
          "ISI-FluABCaster", 
          "ISI-FluBcast",
          "ISI-GLEAM", 
          "ISI-IPSICast", 
          "ev_and_modelers-DeepRE",
          "FBK_HE-REST_HE", 
          "UNIPD_NEIDE-SEEIIRS_MCMC"]

# compute year_week 
iso_year, iso_week, _ = date.today().isocalendar()
week = Week(iso_year, iso_week) - 2
if week.week < 10: 
    year_week = str(week.year) + "_0" + str(week.week)
else: 
    year_week = str(week.year) + "_" + str(week.week)

model_predictions = pd.DataFrame() 
for model in models: 
    try: 
        df_model = pd.read_csv(os.path.join(path, model, year_week + ".csv"))
        df_model["model"] = model
        model_predictions = pd.concat((model_predictions, df_model), ignore_index=True)
    except: 
        print("Not found: ", model)

# ensemble_predictions = model_predictions.groupby(["anno", "settimana", "luogo", 
#                                                   "tipo_valore", "id_valore", 
#                                                   "orizzonte", "target"], as_index=False).mean()

ensemble_predictions = model_predictions.groupby(["anno", "settimana", "luogo",
                                                  "tipo_valore", "id_valore",
                                                  "orizzonte", "target"], as_index=False).mean(numeric_only=True)

ensemble_predictions.to_csv(f"./repo/previsioni/{team_abbr}-{model_abbr}/{year_week}.csv", index=False)


unique_horizons = model_predictions.orizzonte.unique()
unique_regions = model_predictions.luogo.unique()
unique_targets = model_predictions.target.unique()

ensemble_members = [{"target": []}]
for target in unique_targets:
    temp_dict_target = {}
    temp_dict_target["id"] = target  
    temp_dict_target["regions"] = []  

    for region in unique_regions:
        temp_dict_reg = {}
        temp_dict_reg["id"] = region
        temp_dict_reg["members"] = []
        for horizon in unique_horizons:
            temp_dict_reg["members"].append({"horizon": int(horizon), 
                                             "models": list(model_predictions.loc[(model_predictions.luogo == region) & \
                                                                                  (model_predictions.orizzonte == horizon) & \
                                                                                  (model_predictions.target == target)].model.unique())})
        temp_dict_target["regions"].append(temp_dict_reg)
              
    ensemble_members[0]["target"].append(temp_dict_target)


with open(f"./repo/.github/logs/ensemble-members/{year_week}.json", "w") as file:
    json.dump(ensemble_members, file)


env_file = os.getenv('GITHUB_OUTPUT')
with open(env_file, "a") as outenv:
   outenv.write (f"ensemble_file={year_week}.csv")
