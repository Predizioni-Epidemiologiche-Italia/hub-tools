# main
import os
import re
import json
import sys

import validate_forecasts as v


def run ():
    print (">>>>>>>>> Running validation main")

    # res_data = {}
    # res_data['models'] = {}


    env_file = os.getenv('GITHUB_OUTPUT')    
    to_validate = os.getenv("changed_files")

    to_validate = to_validate.split(" ")

    for elem in to_validate:
        print ("Validating {}".format(elem))
        v.validate_csv_files("influcast_flu_forecast", elem)
        
        # team_model = tuple(os.path.basename(os.path.split(elem)[0]).split('_'))

        # # add the team. It is only one
        # if team_model[0] not in res_data:
        #     res_data['team'] = team_model[0]

        # if team_model[1] not in res_data['models'] :
        #    res_data['models'][team_model[1]] = [elem]
        # else:
        #    res_data['models'][team_model[1]].append(elem)    

    
    validated = True
    
    
    with open(env_file, "a") as outenv:
        print(f"Writing to out: validate: {validated}")
        outenv.write ("validation={}".format(validated))
        # outenv.write ("output_data={}".format(str(res_data)))


if __name__ == "__main__":
    print ("### Testing tools_validate script")
    run()
