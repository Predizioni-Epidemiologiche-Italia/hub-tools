import os
import json
from typing import List, Dict
from pathlib import Path
from collections import defaultdict
    

def process_csv_paths(csv_paths, isEnsemble = False):

    db_path = os.path.join(os.getcwd(), "repo/.github/data-storage" + os.path.sep + ("ensemble_db.json" if isEnsemble else "changes_db.json"))

    # Caricare dati esistenti se il file changes.json esiste
    if os.path.exists(db_path):
        with open(db_path, "r") as json_file:
            try:
                data = json.load(json_file)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    
    # Convertire in defaultdict per facilitare gli aggiornamenti
    data = defaultdict(list, data)
    
    for path in csv_paths:
        try:
            # Estrarre informazioni dal path
            parts = path.split('/')
            filename = parts[-1]
            team_model = parts[1]
            team_name, model_name = team_model.split('-')
            
            # Controlla se il modello esiste già per il team
            existing_models = {entry["model"]: entry for entry in data[team_name]}
            
            if model_name in existing_models:
                if path not in existing_models[model_name]["changes"]:
                    existing_models[model_name]["changes"].append(path)
            else:
                data[team_name].append({
                    "model": model_name,
                    "changes": [path]
                })
        
        except ValueError:
            print(f"Errore nel parsing del path: {path}")
    
    # Scrittura su file JSON aggiornato
    with open(db_path, "w") as json_file:
        json.dump(data, json_file, indent=4)


##
def get_the_season (file_path, parent_folder):
    # Divide il percorso in parti
    path_parts = file_path.split(os.sep)
    
    # Cerca l'indice del parent_folder nel percorso
    try:
        parent_index = path_parts.index(parent_folder)
        
        # Check if secondo level subfolder exists
        if parent_index + 2 < len(path_parts):
            return path_parts[parent_index + 2]
        else:
            return None  # If there is no second level subfolder 
        
    except ValueError:
        return None  # if parent_folder does not exists 
    

##
def storeSurveillance (data: List[str], db_file: str):

    print ("Storing Surveillance data")

    changes_list = []
    
    db_path = os.path.join(os.getcwd(), "repo/.github/data-storage/", db_file)
    print(f"DB path: {db_path}")

    # get the season
    season = get_the_season (data[0], "sorveglianza")

    if season is None:
         # If can not find the season raise an exception
        raise Exception(f"Error parsing surveillance path {data[0]} \n. Season not found\n")

    for change in data :
        target = Path(change).stem.split('-')[2]
        target_entry = next((item for item in changes_list if item['name'] == target ), None)
        if target_entry is None:
            changes_list.append({'name': target, 'changes': [change]})
        else:
            target_entry['changes'].append(change)


    updateSurveillanceJson(jdb_path = db_path, season = season, new_items = changes_list)


## update Surveillance json db
## write the season and changes for each target 
def updateSurveillanceJson(jdb_path: str, season: str, new_items: List[Dict]):
    print ('Updating surveillance jdb')

    json_data = None

    # Step 1: Read the existing data from the JSON file
    try:
        with open (jdb_path, 'r') as fdb:
            json_data = json.load(fdb)
            print(f"JSON DB CONTENT: \n{json_data}")
            
    except FileNotFoundError:
        # If the file doesn't exist, handle error
        raise Exception(f"Json file not found {jdb_path}\n")


    if 'season' in json_data:
        # check that season has not changed, otherwise throw error
        if json_data['season'] != season:
            raise Exception(f"Different season data already exist! {json_data['season']} while uploading data relating to {season}\n")
        
    else:
        json_data['season'] = season

    
    if 'targets' not in json_data:
        json_data['targets'] = new_items
    else:
        
        #existing_items = json_data['targets']

        for new_item in new_items:

            # look for existing target
            for item in json_data['targets']:
                if item['name'] == new_item['name']:
                    # if exists, add items
                    item['changes'] += set(new_item['changes']).difference(item['changes'])
                    break

            else:
                json_data['targets'].append(new_item)
        
    try:
        with open(jdb_path, 'w') as fdb:
            json.dump(json_data, fdb, indent=4)
    except:
        # If the file doesn't exist, handle error
        raise Exception(f"Error writing  {json_data} \n to json file: {jdb_path}\n")
    
    
    
##
def updateJsonData (json_file_path, changes):

    json_data = None

    # Step 1: Read the existing data from the JSON file
    try:
        with open (json_file_path, 'r') as fdb:
            json_data = json.load(fdb)
            print(f"JSON DB CONTENT: \n{json_data}")
            
    except FileNotFoundError:
        # If the file doesn't exist, handle error
        raise Exception(f"Json file not found {json_file_path}\n")

    json_data["changes"] = changes if "changes" not in json_data else list(set(json_data["changes"] + changes))

    try:
        with open(json_file_path, 'w') as fdb:
            json.dump(json_data, fdb, indent=4)
    except:
        # If the file doesn't exist, handle error
        raise Exception(f"Error writing  {json_data} \n to json file: {json_file_path}\n")


def store(to_store):

    # Make a list out of the changed files
    fchanges = to_store.split(" ")

    # List should not be empty
    if not fchanges:
        raise Exception(f"Empty commit")
    
    model_changes = []
    ensemble_changes = []
    targetdata_changes = []
    
    # 
    for fchanged in fchanges:

        if fchanged.startswith("previsioni" + os.path.sep + "Influcast-Ensemble"  + os.path.sep) or fchanged.startswith("previsioni" + os.path.sep + "Influcast-quantileBaseline"  + os.path.sep):
            # add to ensemble
            ensemble_changes.append(fchanged)

        elif fchanged.startswith("previsioni" + os.path.sep):
            # save model output
            model_changes.append(fchanged)

        elif fchanged.startswith("sorveglianza" + os.path.sep) and not 'latest' in fchanged:
            # save target-data
            targetdata_changes.append(fchanged)
        else :
            # unknown just discard
            print (f'Unkown or unsupported file submitted {fchanged}! Skip it')


    if model_changes:
        print (f"{len(model_changes)} changes in model-output")
        process_csv_paths(model_changes)

    if ensemble_changes:
        print (f"{len(ensemble_changes)} changes in hub ensemble")
        process_csv_paths(ensemble_changes, isEnsemble = True)

    if targetdata_changes:
        print (f"{len(targetdata_changes)} changes in targetdata")
        storeSurveillance(targetdata_changes, "target_db.json")



if __name__ == "__main__":
    
    store_data = os.getenv("data")        
    jchanges = json.loads(store_data)     
    print (f"Changes: {jchanges}")
    
    store(jchanges["pr-changes"])
