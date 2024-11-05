import re

locations = ('IT', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
             '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21')

targets = ('ILI', 'ILI+_FLU_A', 'ILI+_FLU_B')

# def validate_integer(value):
#     return isinstance(value, int)
#
# def validate_string(value):
#     return isinstance(value, str)

def validate_float(value):
    try:
        float(value)
        return True
    except:
        return False

def validate_quantile(value):
    try:
        return 0 < float(value) < 1
    except:
        return False

def validate_year(value):
    return re.match("\d{4}$", value) is not None

def validate_week(value):
    try:
        return 1 <= int(value) <= 53
    except:
        return False

def validate_location(value):
    return value in locations

def validate_horizon(value):
    return value in ('-1', '0', '1', '2', '3', '4')

def validate_quantile_label(value):
    return value == 'quantile'

def validate_target (value):
    return value in targets