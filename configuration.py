#!/usr/bin/python3

OSMCONVERT_PATH = '/usr/bin/osmconvert'
OSMFILTER_PATH = '/usr/bin/osmfilter'

# Important! File modification date should be equal to OSM data timestamp
SOURCE_PBF = '/gis/data/planet-latest.o5m'
MAP_TARGET_PATH = '/gis/maps'
LOGGING_PATH = '/var/log/mapcreator'
DATA_PATH = '/gis/data'
DATA_DB_DSN = 'dbname=gis'
FILTERS_PATH = '/gis/mapcreator/filters'
FROM_FILE = False

MAP_DOWNLOAD_LOG = '/var/log/nginx/maps.log'
STATS_DB_DSN = 'dbname=gis'

HILLSHADE_VERSION = 1
HILLSHADE_TILES_DB = '/gis/data/hillshade/hillshade.mbtiles'
HILLSHADE_TARGET_PATH = '/gis/hillshade'
