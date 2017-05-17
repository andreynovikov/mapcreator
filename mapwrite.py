#!/usr/bin/python3

import os
import sys
import argparse
import subprocess
import logging.config

import configuration
import landextraction

class MapWriter:

    def __init__(self, data_dir, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.logger = logging.getLogger("mapcreator")
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.simplification = 0.0
        self.landExtractor = landextraction.LandExtractor(self.data_dir, self.dry_run)
        self.landExtractor.downloadLandPolygons()

    def createMap(self, x, y, intermediate=False, keep=False, from_file=False):
        map_path = self.map_path(x, y)
        self.logger.info("Creating map: %s" % map_path)

        land_path = self.landExtractor.extractLandPolygons(7, x, y, self.simplification)

        """
        data_size = PATH.getsize(source_pbf_path)
        land_size = PATH.getsize(land_path)
        if data_size < 210 and (y > 91 or land_size < 100):
            self.logger.debug("   skip - water")
        """

        lllt = self.landExtractor.num2deg(x, y, 7)
        llrb = self.landExtractor.num2deg(x+1, y+1, 7)

        # paths are created by land extractor
        log_path = self.log_path(x, y)
        logfile = open(log_path, 'a')

        osmosis_call = [configuration.OSMOSIS_PATH]
        if self.verbose:
            osmosis_call += ['-v', '1']
        osmosis_call += ['--read-pgsql', '--dataset-bounding-box']
        osmosis_call += ['bottom=%.4f' % llrb[0]]
        osmosis_call += ['left=%.4f' % lllt[1]]
        osmosis_call += ['top=%.4f' % lllt[0]]
        osmosis_call += ['right=%.4f' % llrb[1]]
        osmosis_call += ['completeWays=yes', 'completeRelations=yes']
        osmosis_call += ['--rx', 'file=%s' % land_path]
        osmosis_call += ['--sort', '--merge']

        mem_type = 'ram'

        if intermediate or from_file:
            pbf_path = self.pbf_path(x, y)
            if not os.path.exists(pbf_path):
                self.logger.info("  Creating intermediate file: %s" % pbf_path)
                if from_file:
                    # create upper intermediate file (z=3) to optimize processing of adjacent areas
                    ax = x >> 4
                    ay = y >> 4
                    upper_pbf_path = self.pbf_path(ax, ay, 3)
                    if not os.path.exists(upper_pbf_path) or os.path.getmtime(upper_pbf_path) < os.path.getmtime(configuration.SOURCE_PBF):
                        upper_pbf_dir = os.path.dirname(upper_pbf_path)
                        if not os.path.exists(upper_pbf_dir):
                            os.makedirs(upper_pbf_dir)
                        osmosis_call = [configuration.OSMCONVERT_PATH, configuration.SOURCE_PBF]
                        alllt = self.landExtractor.num2deg(ax, ay, 3)
                        allrb = self.landExtractor.num2deg(ax+1, ay+1, 3)
                        osmosis_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (alllt[1],allrb[0],allrb[1],alllt[0])]
                        osmosis_call += ['--complex-ways', '-o=%s' % upper_pbf_path]
                        self.logger.debug("    calling: %s", " ".join(osmosis_call))
                        if not self.dry_run:
                            subprocess.check_call(osmosis_call)
                        else:
                            subprocess.check_call(['touch', upper_pbf_path])
                    # extract area data from upper intermediate file
                    osmosis_call = [configuration.OSMCONVERT_PATH, upper_pbf_path]
                    osmosis_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (lllt[1],llrb[0],llrb[1],lllt[0])]
                    osmosis_call += ['--complex-ways', '-o=%s' % pbf_path]
                else:
                    osmosis_call += ['--wb', pbf_path, 'omitmetadata=true']
                try:
                    self.logger.debug("    calling: %s", " ".join(osmosis_call))
                    if not self.dry_run:
                        subprocess.check_call(osmosis_call, stderr=logfile)
                    else:
                        subprocess.check_call(['touch', pbf_path])
                except Exception as e:
                    logfile.close()
                    raise e
            # prepare for second step
            self.logger.info("  Processing intermediate file: %s" % pbf_path)
            if os.path.getsize(pbf_path) > configuration.DATA_SIZE_LIMIT:
                mem_type = 'hd'
            osmosis_call = [configuration.OSMOSIS_PATH]
            if self.verbose:
                osmosis_call += ['-v']
            osmosis_call += ['--rb', pbf_path]
            if from_file:
                osmosis_call += ['--rx', 'file=%s' % land_path]
                osmosis_call += ['--sort', '--merge']

        osmosis_call += ['--mw','file=%s' % map_path]
        osmosis_call += ['type=%s' % mem_type] # hd type is currently unsupported
        osmosis_call += ['map-start-zoom=%s' % configuration.MAP_START_ZOOM]
        osmosis_call += ['preferred-languages=%s' % configuration.PREFERRED_LANGUAGES]
        osmosis_call += ['zoom-interval-conf=%s' % configuration.ZOOM_INTERVAL]
        osmosis_call += ['bbox=%.4f,%.4f,%.4f,%.4f' % (llrb[0],lllt[1],lllt[0],llrb[1])]
        osmosis_call += ['way-clipping=false']
        osmosis_call += ['tag-conf-file=%s' % configuration.TAG_MAPPING]

        try:
            self.logger.debug("    calling: %s", " ".join(osmosis_call))
            if not self.dry_run:
                subprocess.check_call(osmosis_call, stderr=logfile)
            else:
                subprocess.check_call(['touch', map_path])
        except Exception as e:
            raise e
        finally:
            logfile.close()

        self.logger.info("Finished map: %s" % map_path)

        size = os.path.getsize(map_path)
        if not self.dry_run and size == 0:
            raise Exception("Resulting map file size for %s is zero, keeping old map file" % map_path)

        # remove intermediate pbf file and log on success
        if intermediate and not keep:
            self.logger.debug("    removing intermediate file %s", pbf_path)
            os.remove(pbf_path)
            self.logger.debug("    removing log file %s", log_path)
            os.remove(log_path)

        return map_path

    def map_path_base(self, x, y, z=7):
        """
        returns path to map file but without extension
        """
        return os.path.join(self.data_dir, str(z), str(x), '%d-%d' % (x, y))

    def pbf_path(self, x, y, z=7):
        """
        returns path to intermediate pbf file
        """
        return self.map_path_base(x, y, z) + ".osm.pbf"

    def map_path(self, x, y):
        """
        returns path to destination map file
        """
        return self.map_path_base(x, y) + ".map"

    def log_path(self, x, y):
        """
        returns path to log file
        """
        return self.map_path_base(x, y) + ".map.log"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek map writer')
    parser.add_argument('-p', '--data-path', default='data', help='base path for data files')
    parser.add_argument('-d', '--dry-run', action='store_true', help='do not generate any files')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose logging')
    parser.add_argument('-i', '--intermediate', action='store_true', help='create intermediate osm.pbf file')
    parser.add_argument('-k', '--keep', action='store_true', help='do not remove intermediate osm.pbf file on success')
    parser.add_argument('-f', '--from-file', action='store_true', help='use file instead of database as data source')
    parser.add_argument('x', type=int, help='tile X')
    parser.add_argument('y', type=int, help='tile Y')
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
        mapWriter = MapWriter(args.data_path, args.dry_run, args.verbose)
        mapWriter.createMap(args.x, args.y, args.intermediate, args.keep, args.from_file)
    except Exception as e:
        print("An error occurred:")
        print(e)
