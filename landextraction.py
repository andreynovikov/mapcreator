#!/usr/bin/python3

import os
import math
import sys
import argparse
import subprocess
import logging.config


class LandExtractor:

    def __init__(self, data_dir, dry_run = False):
        self.dry_run = dry_run
        self.logger = logging.getLogger("mapcreator")
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.landfiles = "land-polygons-split-4326"

    def downloadLandPolygons(self):
        if not self.dry_run:
            path = os.path.join(self.data_dir, self.landfiles + ".zip")
            if not os.path.exists(path):
                import urllib
                import zipfile
                self.logger.info("Retrieving new land files")
                urllib.request.urlretrieve("http://data.openstreetmapdata.com/" + self.landfiles + ".zip", path)
                zfile = zipfile.ZipFile(path)
                zfile.extractall(self.data_dir)
                self.logger.info("Retrieved new land files")

    def extractLandPolygons(self, z, x, y, simplify=0):
        land_polygon_path = self.land_polygon_path(z, x, y)
        self.logger.info("Making land polygons for %d/%d/%d in %s" % (z, x, y, land_polygon_path))
        output_path = self.land_polygon_dir(z, x, y)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        land_path = self.land_path(z, x, y)
        if os.path.exists(land_path):
            self.logger.debug("    land exists, skip")
            return land_path

        data_path = os.path.join(self.data_dir, os.path.join(self.landfiles, "land_polygons.shp"))
        lllt = self.num2deg(x, y, z)
        llrb = self.num2deg(x+1, y+1, z)

        ogr_call = ["ogr2ogr", "-overwrite", "-skipfailures", "-clipsrc", format(lllt[1], '.4f'), format(llrb[0], '.4f'), format(llrb[1], '.4f'), format(lllt[0], '.4f')]
        if simplify > 0:
            ogr_call += ["-simplify", str(simplify)]
        ogr_call += [output_path, data_path]
        self.logger.debug("calling: %s"," ".join(ogr_call))
        if not self.dry_run:
            subprocess.call(ogr_call)

        ogr2osm_call = ["ogr2osm/ogr2osm.py", "--add-version", "--add-timestamp", "-t", "mapsforge", "-f", "-o", land_path, land_polygon_path]
        self.logger.debug("calling: %s"," ".join(ogr2osm_call))
        if not self.dry_run:
            subprocess.call(ogr2osm_call)

        return land_path

    def land_polygon_dir(self, z, x, y):
        return os.path.join(self.data_dir, str(z), str(x), str(y))

    def land_polygon_path(self, z, x, y):
        """
        path to the shapefile containing the land polygons
        """
        return os.path.join(self.land_polygon_dir(z, x, y), "land_polygons.shp")

    def land_path_base(self, z, x, y):
        """
        returns path to land file but without the numbers and extension
        """
        return os.path.join(self.data_dir, str(z), str(x), '%d-%d-land' % (x, y))

    def land_path(self, z, x, y):
        """
        returns path to land file with first extension, which should be sufficient
        """
        return self.land_path_base(z, x, y) + ".osm"

    def num2deg(self, xtile, ytile, zoom):
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Land polygons extractor')
    parser.add_argument('-s', '--simplify', default=0, help='simplification factor (default: %(default).0f)')
    parser.add_argument('-p', '--data-path', default='data', help='base path for data files (default: %(default)s)')
    parser.add_argument('-d', '--dry-run', action='store_true', help='do not generate any files')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose logging')
    parser.add_argument('x', type=int, help='tile X')
    parser.add_argument('y', type=int, help='tile Y')
    parser.add_argument('z', nargs='?', default=7, help='tile zoom (default: %(default)d)')
    args = parser.parse_args()

    sh = logging.StreamHandler()
    logger = logging.getLogger("mapcreator")
    formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    # during a dry run the console should receive all logs
    if args.dry_run or args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        landExtractor = LandExtractor(args.data_path, args.dry_run)
        landExtractor.downloadLandPolygons()
        landExtractor.extractLandPolygons(args.z, args.x, args.y, args.simplify)
    except Exception as e:
        print("An error occurred: \n%s" % e)
