#!/bin/sh
#
# After unpacking the contents of each zip archive, pipe this script to psql.
#

shp2pgsql -dID -s 3857 -W UTF-8 -g geometry "data/water-polygons-split-3857/water_polygons.shp" "osmd_water"
shp2pgsql -dID -s 3857 -W UTF-8 -g geometry "data/simplified-water-polygons-complete-3857/simplified_water_polygons.shp" "osmd_water_z7"
