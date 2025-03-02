import os
from typing import Dict

#minimum and maximum for each setting attribute
limits = {"results/search":{"min":1, "max":100},
          "results/page":{"min":1, "max": 100}}

#default values for the setting attributes
default = {"results/search":30, "results/page":10}


#for editting, viewing lines in the setup file
class SetupFile():
    def __init__(self, name, dir):
        self.name = name
        self.dir = dir
        self.path = os.path.join(self.dir, self.name)
        self.no_of_lines = len(default)


    #retrieves data from the setup file
    def get_data(self, make_txt: bool = True) -> Dict[str, str]:

        if (not make_txt):
            return {"results/search": default["results/search"],
                    "results/page": default["results/page"]}
        else:
            #open/create the file
            file = open(self.path, "a+")
            file.close()


            file = open(self.path, "r")
            file.seek(0)

            file_source = file.readlines()
            file.close()


            #if the file is just created or the file does not contain anything or has less lines than required
            if (len(file_source) < self.no_of_lines):
                file = open(self.path, "w")
                file.write(f"{default['results/search']}\n{default['results/page']}")
                file.close()
                return default

            else:
                data = {}
                valid_file = True

                #if the file contains more lines than required
                if (len(file_source) > self.no_of_lines):
                    file_source = file_source[:self.no_of_lines]

                #strip whitespaces to the left and right of each line
                for i in range(len(file_source)):
                    file_source[i] = file_source[i].strip()

                #check if the first 2 lines are either numbers from 1-20
                for i in range(2):
                    if (file_source[i].isnumeric() and int(file_source[i]) >= limits["results/search"]["min"] and int(file_source[i]) <= limits["results/search"]["max"]):
                        if (not i):
                            data["results/search"] = file_source[i]
                        else:
                            data["results/page"] = file_source[i]

                    else:
                        valid_file = False
                        if (not i):
                            data["results/search"] = default["results/search"]
                        else:
                            data["results/page"] = default["results/page"]


                #rewrite the file if it is invalid
                if (not valid_file):
                    self.change_data(data)

                return data


    #make changes to the setup file
    def change_data(self, data: Dict[str, str], make_txt: bool = True):
        if (make_txt):
            file = open(self.path, "w")
            data_keys = list(data.keys())

            for i in range(len(data_keys)):
                if (i < len(data_keys) - 1):
                    line = str(data[data_keys[i]]) + "\n"
                else:
                    line = str(data[data_keys[i]])

                file.write(line)

            file.close()
