#!/usr/bin/python3

OSMCONVERT_PATH = '/usr/bin/osmconvert'
#MAP_START_ZOOM = '8'
#PREFERRED_LANGUAGES = 'en,de,ru'

SOURCE_PBF = '/gis/data/planet-170807.osm.pbf'
SOURCE_PBF_TIMESTAMP = 1502064000 # 2017-08-07
MAP_TARGET_PATH = '/gis/maps'
LOGGING_PATH = '/var/log/mapcreator'
DATA_PATH = '/gis/data'
DATA_DB_DSN = 'dbname=gis'

MAP_DOWNLOAD_LOG = '/var/log/nginx/maps.log'
STATS_DB_DSN = 'dbname=gis'
