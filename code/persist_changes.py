import os
import json

        

def storeStdData (data, db_file):
    print ("Storing data")
    #"/home/runner/work/the-hub/the-hub/./repo/.github/data-storage/" + db_file
    db_path = os.path.join(os.getcwd(), "./repo/.github/data-storage/", db_file)
    print(f"DB path: {db_path}")
    updateJsonData(db_path, data)


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
    

    evaluation_changes = []

    
    # 
    for fchanged in fchanges:
                
        # needed for different deepness of paths
        if fchanged.startswith("model-evaluation") and not 'latest-' in fchanged:
            # save evaluation-data
            evaluation_changes.append(fchanged)
        else :
            # unknown just discard
            print (f'Unkown file submitted {fchanged}! Skip it')


    if evaluation_changes:
        print (f"{len(evaluation_changes)} changes in evaluations")
        storeStdData(evaluation_changes, "evaluation_db.json")


if __name__ == "__main__":

    store_data = os.getenv("data")        
    store(store_data)