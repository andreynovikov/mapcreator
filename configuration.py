#!/usr/bin/python3

OSMCONVERT_PATH = '/gis/bin/osmconvert'

# Important! File modification date should be equal to OSM data timestamp
SOURCE_PBF = '/gis/data/planet-latest.o5m'
MAP_TARGET_PATH = '/gis/maps'
LOGGING_PATH = '/var/log/mapcreator'
DATA_PATH = '/gis/data'
DATA_DB_DSN = 'dbname=gis'

MAP_DOWNLOAD_LOG = '/var/log/nginx/maps.log'
STATS_DB_DSN = 'dbname=gis'
