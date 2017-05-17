#!/usr/bin/python3

OSMOSIS_PATH = '/gis/osmosis/package/bin/osmosis'
OSMCONVERT_PATH = '/usr/bin/osmconvert'
ZOOM_INTERVAL = '10,8,11,14,12,20'
MAP_START_ZOOM = '8'
PREFERRED_LANGUAGES = 'en,de,ru'
TAG_MAPPING = '/gis/tag-mapping.xml'

SOURCE_PBF = '/gis/planet-161107.osm.pbf'
MAP_TARGET_PATH = '/gis/maps'
LOGGING_PATH = '/var/log/mapcreator'
DATA_PATH = '/gis/data'
DATA_SIZE_LIMIT = 157286400 # 150M

MAP_DOWNLOAD_LOG = '/var/log/nginx/maps.log'
STATS_DB_DSN = 'dbname=gis'
