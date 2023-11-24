import os


# class authenticator 
class SurveillanceAuthenticator () :

    def __init__(self, user, changes):
        self.user = user
        self.changes = changes
        self.root_container = "sorveglianza"


    ##
    def authenticate (self): 
        # verify user
        self._authenticateUser()        
        self._verifyPaths()


    ##
    def _authenticateUser (self):
        # nothing to do here for the time being 
        return True


    ##
    def _verifyPaths(self, changes, root_folder):

        # Se la lista è vuota, restituisci True
        if not changes:
            return True
                
        # Verify all the paths are root subfolders
        if not all(os.path.commonpath([root_folder, f]) == root_folder for f in changes):
            raise PermissionError (f"Trying to submit changes outside the authorised root path - {root_folder}")

        return True






def outputResults (result = True, result_msg = "" ):
    env_file = os.getenv('GITHUB_OUTPUT')    
    out_res = "success" if result else "failure"

    with open(env_file, "a") as outenv:
        print (f"Writing results to output auth: {out_res}, msg: {result_msg}")
        outenv.write (f"authenticate={out_res}\n")
        outenv.write (f"message={result_msg}")



def run ():

    actor = os.getenv("calling_actor")
    changes = os.getenv("changed_files")


    if actor is None or changes is None:
        outputResults(False, "Missing input! Abort")
        return
    
    authenticateObj = SurveillanceAuthenticator(actor, changes.split(" "))

    try:

        authenticateObj.authenticate()
        outputResults()
        
    except Exception as e:
        outputResults(False, str(e))


if __name__ == "__main__":
    print ("### Authenticate surveillance script")
    run()
