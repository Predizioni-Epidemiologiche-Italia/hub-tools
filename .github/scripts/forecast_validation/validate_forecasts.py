import json
import os
import csv

# Config
reference_file = os.path.join(os.path.dirname(__file__), 'format_reference.json')

from validation_functions import (validate_float, validate_quantile, validate_year, validate_week,
                                  validate_location, validate_horizon, validate_quantile_label)

with open(reference_file, "r") as file:
    format_mapping = json.load(file)

# Main funct
def validate_csv_files(file_format, csv_file):

    print("validating {}".format(csv_file))
  
    assert file_format in format_mapping, f"Unknown file format: {file_format} not found in mapping."

    file_fields = format_mapping[file_format]['fields']
    validation_funcs = format_mapping[file_format]['functions']

    with open(csv_file, "r") as in_file:
        print ("File opened ok")
      
        reader = csv.reader(in_file)

        # get forecasting year and week from the file name
        year, week = csv_file.split('/')[-1].split('.')[0].split('_')

        for rec in reader:
          print ("validating record {} ...".format(rec))

          if reader.line_num == 1:
              assert rec == file_fields
              continue

          # check that the forecast year and week are consistent with those in the file name
          if not (rec[0] == year and rec[1] == week):
            raise Exception(f"Invalid record in line {reader.line_num} of file {csv_file} Forecasting year and week {rec[0]}_{rec[1]} not consistent with file scope {year}_{week}.")

          
          is_valid = True
          for ck in zip(validation_funcs, rec, file_fields):
              is_valid = is_valid and eval(ck[0])(ck[1])

              if not is_valid:
                  raise Exception(f"Invalid record in line {reader.line_num} of file {csv_file} Value {ck[1]} not acceptable for field {ck[2]}.")

    return 'OK'
