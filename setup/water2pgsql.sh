#!/bin/sh
#
# After unpacking the contents of each zip archive, pipe this script to psql.
#

shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-split-3857/water_polygons.shp" "osmd_water"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z8.shp" "osmd_water_z8"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z7.shp" "osmd_water_z7"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z6.shp" "osmd_water_z6"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z5.shp" "osmd_water_z5"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z4.shp" "osmd_water_z4"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z3.shp" "osmd_water_z3"
shp2pgsql -dID -s 3857 -W UTF-8 -g geom "data/water-polygons-generalized-3857/water_polygons_z2.shp" "osmd_water_z2"
