import json
from glob import glob
import os

import constants

zone_info = {}


def load_zones(zone_file_path):
    with open(zone_file_path, "r") as file:
        data = json.load(file)
    return data


def read_files():
    path = 'zones/'
    zones = list(glob(os.path.join(path, "*.json")))
    for zone in zones:
        file_name = zone.split("/")[-1]
        zone_name = ".".join(file_name.split(".")[:-1])
        if zone_name not in constants.ALLOWED_ZONES:
            zones.remove(zone)
    return zones


def init():
    global zone_info
    # TODO: Support for multiple Zones
    zone_info = load_zones(read_files()[0])
