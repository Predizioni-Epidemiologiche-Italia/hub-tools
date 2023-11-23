# main
import os
import re
import json
import sys

import validate_forecasts as v


def outputResults (result = True, result_msg = "" ):
    env_file = os.getenv('GITHUB_OUTPUT')    
    out_res = "success" if result else "failure"

    with open(env_file, "a") as outenv:
        print (f"Writing results to output. Validate: {out_res}, msg: {result_msg}")
        outenv.write (f"validate={out_res}\n")
        outenv.write (f"message={result_msg}")


def run ():

    env_file = os.getenv('GITHUB_OUTPUT')    
    to_validate = os.getenv("changed_files")

    to_validate = to_validate.split(" ")

    for elem in to_validate:
        print ("Validating {}".format(elem))

        try:
            v.validate_csv_files("influcast_flu_forecast", elem)
            outputResults()

        except Exception as e:
            outputResults(False, str(e))
            break    
    

if __name__ == "__main__":
    print ("### Testing tools_validate script")
    run()
