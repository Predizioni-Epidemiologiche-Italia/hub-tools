# main
import os
import re
import json
import sys

from datetime import datetime, timedelta
from isoweek import Week

# list of days in a week
weekdaysList = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                'Friday', 'Saturday', 'Sunday']


import validate_forecasts as v


def outputResults (result = True, result_msg = "" ):
    env_file = os.getenv('GITHUB_OUTPUT')    
    out_res = "success" if result else "failure"

    with open(env_file, "a") as outenv:
        print (f"Writing results to output. Validate: {out_res}, msg: {result_msg}")
        outenv.write (f"validate={out_res}\n")
        outenv.write (f"message={result_msg}")

# This function returns the last weekday of input day by
# accepting the input day as argument
def getLastByDay  (inputDay):
    # Get today's date
    today = datetime.today()    
    # getting the last weetodaykday
    daysAgo = (today.weekday() - weekdaysList.index(inputDay)) % 7

    # Subtract the above number of days from the current date(start date)
    # to get the last week's date of the given day
    targetDate = today - timedelta(days=daysAgo)

    return targetDate

def is_in_submit_window (submitting_elem):

    print (f'verifying submission window for {submitting_elem}')
    
    # Calculate last Friday date
    last_friday = getLastByDay('Friday')

    # Calculate the current week's Tuesday
    this_tuesday = last_friday + timedelta(days=4)

    # Check if the date is between last Friday and this Thursday
    if not (last_friday <= datetime.today() <= this_tuesday):
        raise RuntimeError ("Submission time must be within accepted submission window for round.")

    
    reference_week = Week.withdate(last_friday) - 1
    # get forecasting year and week from the file name
    year_week = submitting_elem.split('/')[-1].split('.')[0].split('_')
    uploading_week = Week.fromstring(year_week[0] + "W" + year_week[1])

    if uploading_week != reference_week:
        raise RuntimeError ("Forecasting week must be within accepted submission window for round.")




def run ():

    env_file = os.getenv('GITHUB_OUTPUT')    
    to_validate = os.getenv("changed_files")

    to_validate = to_validate.split(" ")

    for elem in to_validate:
        print ("Validating {}".format(elem))

        try:
            # verify if still in the submission window
            is_in_submit_window (submitting_elem=elem)

            # then verify that forma is valid
            v.validate_csv_files("influcast_flu_forecast", elem)
            outputResults()

        except Exception as e:
            outputResults(False, str(e))
            break    
    

if __name__ == "__main__":
    print ("### Testing tools_validate script")
    run()
