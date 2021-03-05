#!/bin/sh

import_shapefile(){
    rm "$2/$2-merc.shp"
    ogr2ogr -wrapdateline -t_srs EPSG:3857 "$2/$2-merc.shp" "$2/$2.shp"
    shp2pgsql -dID -s 3857 -W "$1" -g geom "$2/$2-merc.shp" "$2" | psql gis
}

import_shapefile LATIN1 ne_50m_lakes
import_shapefile LATIN1 ne_10m_lakes
import_shapefile LATIN1 ne_50m_rivers_lake_centerlines
import_shapefile LATIN1 ne_10m_rivers_lake_centerlines
import_shapefile LATIN1 ne_10m_lakes_europe
import_shapefile LATIN1 ne_10m_lakes_north_america
import_shapefile LATIN1 ne_10m_urban_areas
