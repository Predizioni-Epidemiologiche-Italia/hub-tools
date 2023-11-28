import os
import re
import json
import sys
from isoweek import Week
from pathlib import Path
from datetime import datetime


# local's
import authenticate_config as config

#
# Receives as an input through the env :
# User: the github user that is requesting changes
# Files: the list of changed files 
# Mapping file: the file to match against to verify user, team and path. If none, default is used 


# class authenticator 
class Authenticator () :

    def __init__(self, user, changes):
        self.user = user
        self.changes = changes
        self.mappings = self._defaultMappings()

        self.team = None
        self.models = None


        # 2 = Tuesday, 
        # self.submissionWeekDay = 2
        # 3 = Wednesday - for the very first week
        self.submissionWeekDay = 3

    #
    #
    def authenticate (self): 
        # verify user
        self._authenticateUser()

        if self.team is None:
            # handle invalid user mapping
            raise RuntimeError ("User not found. Can not authenticate")
        
        # check if submitted week matches the current submission window
        self._isInSubmissionWindow()

        #
        self._verifyPaths()
        
    # 
    # Verify that the actor of the PR is currently in the authorised db and 
    # map it back to its Team and Models
    def _authenticateUser (self):
        j_in = None
        
        # load mappings file
        with open(self.mappings) as f_json_input:
            j_in = json.load(f_json_input)
            
        if j_in is None :
            raise FileExistsError("Mapping file does not exist, can not authenticate")
        
        if not "teams" in j_in:
            raise KeyError("Invalid Mapping file, can not authenticate")
            
        # loop over teams to find current user
        teams = j_in['teams']

        for team in teams:
            if self.user in team['users']:
                #found
                self.team = team['name']
                self.models = team['models']
    
    #
    # Verify submission window
    def _isInSubmissionWindow (self):
        reference_isoweek = Week.thisweek() -2 if datetime.now().isocalendar().weekday <= self.submissionWeekDay else Week.thisweek() - 1
        for elem in self.changes :
            year, week = Path(elem).stem.split('_')

            uploading_week = Week.fromstring(year + "W" + week)
            if uploading_week == reference_isoweek:
                print ("Submission window ok")
            elif uploading_week < reference_isoweek:
                print ("trying to upload expired forecast")
                raise ValueError ("trying to upload forecasts outside the curren uploading window. Currently accepting week: {reference_isoweek}")
            else:
                print ("Performing an early upload")
                raise ValueError ("trying to upload forecasts outside the curren uploading window Currently accepting week: {reference_isoweek}")

    #
    #
    def _verifyPaths (self):

        matching_list = []
        for model in self.models :
            matching_list.append(os.path.join(config.default_saving_path, self.team + '-' + model))
        
        invalid_forcast_paths = [changed_file for changed_file in self.changes if not os.path.split(changed_file)[0] in matching_list]
        
        if invalid_forcast_paths:
            # handle trying to save an unauthorised path 
            raise PermissionError (f"Trying to mofify in a not authorised path {invalid_forcast_paths}. Team:{self.team}, models: {self.models}")
            
        print ("Paths look ok, check file name")

        # Pattern that matches a forecast file added to the data-processed folder.
        # Test this regex usiing this link: https://regex101.com/r/wmajJA/1
        forecast_fname_matching = re.compile(r"^previsioni/(.+)/\d\d\d\d_\d\d.csv$")    
        invalid_forcast_names = [changed_file for changed_file in self.changes if forecast_fname_matching.match(changed_file) is None]

        if invalid_forcast_names:
            # handle trying to save an unauthorised path 
            raise ValueError ("trying to save with an invalid file name")

        print ("Names look ok, go on")
  
    #
    #
    def _defaultMappings (self):
        return os.path.join(os.path.dirname(__file__), config.default_mapping_file)


def outputResults (result = True, result_msg = "" ):
    env_file = os.getenv('GITHUB_OUTPUT')    
    out_res = "success" if result else "failure"

    with open(env_file, "a") as outenv:
        print (f"Writing results to output auth: {out_res}, msg: {result_msg}")
        outenv.write (f"authenticate={out_res}\n")
        outenv.write (f"message={result_msg}")

#
def run ():

    actor = os.getenv("calling_actor")
    changes = os.getenv("changed_files")


    if actor is None or changes is None:
        outputResults(False, "Missing input! Abort")
        return
    
    authenticateObj = Authenticator(actor, changes.split(" "))

    try:

        authenticateObj.authenticate()
        outputResults()
        
    except Exception as e:
        outputResults(False, str(e))

    

if __name__ == "__main__":
    print ("### Testing tools_authenticate script")
    run()
