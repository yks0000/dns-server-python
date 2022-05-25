import json

zone_info = {}

ALLOWED_ZONES = ['yogeshsharma.me']


def load_zones(zone_file_path):
    with open(zone_file_path, 'r') as file:
        data = json.load(file)
    return data


def init():
    global zone_info
    zone_info = load_zones("zones/yogeshsharma.me.json")
