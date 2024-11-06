import os
import json
from typing import List, Dict
from pathlib import Path
    

def storeForecasts (forecasts, isEnsemble = False):
           
    team = os.path.basename(os.path.split(forecasts[0])[0]).split('-')[0]
    if not team:
     raise Exception(f"invalid input data  {forecasts}\n")

    out_data = {}    
    out_data['team'] = team
    out_data['models'] = []

    for forecast in forecasts:

        #get the model name from path
        model = tuple(os.path.basename(os.path.split(forecast)[0]).split('-'))[1]

        model_entry = next((item for item in out_data['models'] if item["model"] == model), None)
        if model_entry is None:
            out_data['models'].append({"model" : model, "changes": [forecast]})            
        else:
            model_entry["changes"].append(forecast)

    if out_data['models']:
        db_path = os.path.join(os.getcwd(), "repo/.github/data-storage" + os.path.sep + ("ensemble_db.json" if isEnsemble else "changes_db.json"))
        print(f"DB path: {db_path}")
        updateForecastsJson(db_path, out_data)
    

def updateForecastsJson(json_file_path, changes):

    json_data = None

    team = changes.get("team")
    n_entries = changes.get("models")

    # Step 1: Read the existing data from the JSON file
    try:
        with open (json_file_path, 'r') as fdb:
            json_data = json.load(fdb)            
    except FileNotFoundError:
        # If the file doesn't exist, handle error
        raise Exception(f"Json file not found {json_file_path}\n")

    # Check if the "team" key exists and is a list
    if team not in json_data:
        # if brand new, just save commits
        json_data[team] = n_entries

    else:
        #get the list of previous saved data for this team
        j_records = json_data[team]

        for entry in n_entries:
                
            j_model = [j_record for j_record in j_records if j_record.get("model") == entry.get("model")]
            if j_model == [] :
                j_records.append(entry)
            else:
                j_model[0]["changes"] += set(entry["changes"]).difference (j_model[0]["changes"])

    try:
        with open(json_file_path, 'w') as fdb:
            json.dump(json_data, fdb, indent=4)
    except:
        # If the file doesn't exist, handle error
        raise Exception(f"Error writing  {json_data} \n to json file: {json_file_path}\n")
        


def get_the_season (file_path, parent_folder):
    folders = os.path.normpath(file_path).split(os.path.sep)

    # Find season folder
    season = None
    path_found = False
    
    for folder in folders:
        if folder == parent_folder:
            path_found = True
        elif path_found and folder:
            season = folder
            break  # when season found

    return season


##
def storeSurveillance (data: List[str], db_file: str):

    print ("Storing Surveillance data")

    changes_list = List[Dict]
    
    db_path = os.path.join(os.getcwd(), "repo/.github/data-storage/", db_file)
    print(f"DB path: {db_path}")

    # get the season
    season = get_the_season (data[0], "sorveglianza")

    for change in data :
        target = Path(change).stem.split('-')[2]
        target_entry = next((item for item in changes_list if item['name'] == target ), None)
        if target_entry is None:
            changes_list.append({'name': target, 'changes': [change]})
        else:
            target_entry['changes'].append(change)


    updateSurveillanceJson(db_path = db_path, season = season, new_items = changes_list)


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

        elif fchanged.startswith("sorveglianza" + os.path.sep) and not '-latest-' in fchanged:
            # save target-data
            targetdata_changes.append(fchanged)
        else :
            # unknown just discard
            print (f'Unkown or unsupported file submitted {fchanged}! Skip it')


    if model_changes:
        print (f"{len(model_changes)} changes in model-output")
        storeForecasts(model_changes)

    if ensemble_changes:
        print (f"{len(ensemble_changes)} changes in hub ensemble")
        storeForecasts(ensemble_changes, isEnsemble = True)

    if targetdata_changes:
        print (f"{len(targetdata_changes)} changes in targetdata")
        storeSurveillance(targetdata_changes, "target_db.json")



if __name__ == "__main__":
    
    store_data = os.getenv("data")        
    jchanges = json.loads(store_data)     
    print (f"Changes: {jchanges}")
    
    store(jchanges["pr-changes"])
