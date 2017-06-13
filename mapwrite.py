#!/usr/bin/python3

import os
import sys
import math
import queue
import threading
import argparse
import subprocess
import logging.config
from collections import defaultdict, namedtuple
from functools import partial

import pyproj
import osmium
import mercantile
import numpy
import shapely.wkb as shapelyWkb
import shapely.speedups
from shapely import geometry
from shapely.prepared import prep
from shapely.ops import transform, cascaded_union, unary_union
from shapely.affinity import affine_transform

import OSciMap4

import configuration
import mappings
import landextraction
from util.database import MTilesDatabase
from util.osm import is_area


DBJob = namedtuple('DBJob', ['tile', 'features'])

wkbFactory = osmium.geom.WKBFactory()

project = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:4326'), # source coordinate system
        pyproj.Proj(init='epsg:3857')) # destination coordinate system


def deep_get(dictionary, *keys):
    for key in keys:
        if isinstance(dictionary, dict):
            dictionary = dictionary.get(key, {})
        else:
            return {}
    return dictionary


class Element():
    def __init__(self, id, geom, tags, mapping=None, label=None, area=None):
        self.id = id
        self.geom = geom # original geometry
        self.tags = tags
        self.mapping = mapping
        self.label = label
        self.area = area
        self.geometry = None # tile processed temporary geometry

    def __str__(self):
        return "%d: %s\n%s\n%s\n" % (self.id, self.geom.__repr__(), self.tags, self.mapping)

    def clone(self, geom):
        return Element(self.id, geom, self.tags, self.mapping, self.label, self.area)


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, elements, logger):
        super(OsmFilter, self).__init__()
        self.elements = elements
        self.logger = logger

    def filter(self, tags):
        filtered_tags = {}
        mapping = {}
        renderable = False
        for tag in tags:
            if tag.k in mappings.tags.keys():
                m = mappings.tags[tag.k].get('__any__', None)
                if m is None:
                    m = mappings.tags[tag.k].get(tag.v, None)
                if m is not None: #empty dictionaries should be also accounted
                    k = tag.k
                    v = tag.v
                    if 'rewrite-key' in m or 'rewrite-value' in m:
                        k = m.get('rewrite-key', k)
                        v = m.get('rewrite-value', v)
                        m = mappings.tags.get(k, {}).get(v, {})
                    if 'one-of' in m:
                        if v not in m['one-of']:
                            return False, None, None
                    filtered_tags[k] = v
                    renderable = renderable or m.get('render', True)
                    for k in ('transform','union','area','filter-area','buffer','force-line'):
                        if k in m:
                            mapping[k] = m[k]
                    if 'zoom-min' in m:
                        if 'zoom-min' not in mapping or m['zoom-min'] < mapping['zoom-min']:
                            mapping['zoom-min'] = m['zoom-min']
        # if element is subject to uniting construct union key hash in advance
        if 'union' in mapping:
            pattern = [x.strip() for x in mapping['union'].split(',')]
            values = [filtered_tags[k] for k in sorted(set(pattern) & set(filtered_tags.keys()))]
            mapping['union-key'] = hash(tuple(values))
        return renderable, filtered_tags, mapping

    def node(self, n):
        renderable, tags, mapping = self.filter(n.tags)
        if renderable:
            try:
                wkb = wkbFactory.create_point(n)
                geom = transform(project, shapelyWkb.loads(wkb, hex=True))
                self.elements.add(Element(n.id, geom, tags, mapping))
            except Exception as e:
                self.logger.error("%s %s" % (e, n.id))

    def way(self, w):
        renderable, tags, mapping = self.filter(w.tags)
        if renderable:
            try:
                wkb = wkbFactory.create_linestring(w)
                geom = transform(project, shapelyWkb.loads(wkb, hex=True))
                self.elements.add(Element(w.id, geom, tags, mapping))
            except Exception as e:
                self.logger.error("%s %s" % (e, w.id))

    def area(self, a):
        renderable, tags, mapping = self.filter(a.tags)
        if renderable:
            try:
                wkb = wkbFactory.create_multipolygon(a)
                geom = transform(project, shapelyWkb.loads(wkb, hex=True))
                self.elements.add(Element(a.id, geom, tags, mapping))
            except Exception as e:
                self.logger.error("%s %s" % (e, a.id))

    def finish(self):
        self.logger.debug("    elements: %d" % len(self.elements))


class Tile():
    RADIUS = 6378137
    CIRCUM = 2 * math.pi * RADIUS
    SIZE = 256
    SCALE = 4096
    INITIAL_RESOLUTION = CIRCUM / SIZE

    def __init__(self, zoom, x, y, elements):
        self.zoom = zoom
        self.x = x
        self.y = y
        self.elements = elements
        self.pixelWidth = self.INITIAL_RESOLUTION / 2 ** self.zoom
        bb = mercantile.xy_bounds(x, y, zoom)
        self.matrix = [Tile.SCALE / (bb.right - bb.left), 0, 0, 0, Tile.SCALE / (bb.top - bb.bottom), 0, 0, 0,
                       1, -bb.left * Tile.SCALE / (bb.right - bb.left), -bb.bottom * Tile.SCALE / (bb.top - bb.bottom), 0]
        #[Tile.SCALE / (bb.right - bb.left), 0, 0, Tile.SCALE / (bb.top - bb.bottom), -bb.left * Tile.SCALE / (bb.right - bb.left), -bb.bottom * Tile.SCALE / (bb.top - bb.bottom)]
        #print(str(self.matrix))

    def bbox(x, y, zoom):
        bb = mercantile.xy_bounds(x, y, zoom)
        return geometry.Polygon([[bb.left, bb.bottom], [bb.left, bb.top], [bb.right, bb.top], [bb.right, bb.bottom]])

    def __str__(self):
        return "%d/%d/%d" % (self.zoom, self.x, self.y)


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
        #self.landExtractor.downloadLandPolygons()
        self.tileQueue = queue.Queue()

        try:
            # Enable C-based speedups available from 1.2.10+
            from shapely import speedups
            if speedups.available:
                self.logger.info("Enabling Shapely speedups")
                speedups.enable()
        except:
            self.logger.warn("Upgrade Shapely for performance improvements")

    def createMap(self, x, y, intermediate=False, keep=False, from_file=False):
        map_path = self.map_path(x, y)
        self.logger.info("Creating map: %s" % map_path)

        #land_path = self.landExtractor.extractLandPolygons(7, x, y, self.simplification)

        lllt = self.landExtractor.num2deg(x, y, 7)
        llrb = self.landExtractor.num2deg(x+1, y+1, 7)

        # paths are created by land extractor
        log_path = self.log_path(x, y)
        logfile = open(log_path, 'a')

        if intermediate or from_file:
            pbf_path = self.pbf_path(x, y)
            if not os.path.exists(pbf_path):
                self.logger.info("  Creating intermediate file: %s" % pbf_path)
                if from_file:
                    # create upper intermediate file (zoom=3) to optimize processing of adjacent areas
                    ax = x >> 4
                    ay = y >> 4
                    upper_pbf_path = self.pbf_path(ax, ay, 3)
                    if not os.path.exists(upper_pbf_path) or os.path.getmtime(upper_pbf_path) < os.path.getmtime(configuration.SOURCE_PBF):
                        upper_pbf_dir = os.path.dirname(upper_pbf_path)
                        if not os.path.exists(upper_pbf_dir):
                            os.makedirs(upper_pbf_dir)
                        osmconvert_call = [configuration.OSMCONVERT_PATH, configuration.SOURCE_PBF]
                        alllt = self.landExtractor.num2deg(ax, ay, 3)
                        allrb = self.landExtractor.num2deg(ax+1, ay+1, 3)
                        osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (alllt[1],allrb[0],allrb[1],alllt[0])]
                        osmconvert_call += ['--complex-ways', '-o=%s' % upper_pbf_path]
                        self.logger.debug("    calling: %s", " ".join(osmconvert_call))
                        if not self.dry_run:
                            subprocess.check_call(osmconvert_call)
                        else:
                            subprocess.check_call(['touch', upper_pbf_path])
                    # extract area data from upper intermediate file
                    osmconvert_call = [configuration.OSMCONVERT_PATH, upper_pbf_path]
                    osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (lllt[1],llrb[0],llrb[1],lllt[0])]
                    osmconvert_call += ['--complex-ways', '-o=%s' % pbf_path]
                    try:
                        self.logger.debug("    calling: %s", " ".join(osmconvert_call))
                        if not self.dry_run:
                            subprocess.check_call(osmconvert_call, stderr=logfile)
                        else:
                            subprocess.check_call(['touch', pbf_path])
                    except Exception as e:
                        logfile.close()
                        raise e
                else:
                    logfile.close()
                    raise NotImplementedError('Loading data from database is not implemented yet')

        self.logger.info("  Processing file: %s" % pbf_path)

        elements = set()
        handler = OsmFilter(elements, self.logger)
        handler.apply_file(pbf_path)
        handler.finish()

        # process map only if it contains relevant data
        has_elements = bool(elements)
        if has_elements:
            for element in elements:
                #print(str(element))
                #TODO: fix geometries, do other transforms
                #self.logger.debug("ma: %s" % element.mapping.get('area', False))
                if element.mapping.get('force-line', False):
                    if isinstance(element.geom, geometry.Polygon) or isinstance(element.geom, geometry.MultiPolygon):
                        element.geom = element.geom.boundary
                elif isinstance(element.geom, geometry.LineString):
                    #TODO change to is_ring
                    if element.geom.coords[0] == element.geom.coords[-1] and is_area(element):
                        polygon = geometry.Polygon(element.geom)
                        if polygon.is_valid:
                            element.geom = polygon
                if element.mapping.get('calc-area', False):
                    element.area = element.geom.area

            self.dbQueue = queue.Queue()
            self.tileQueue = queue.Queue()

            db_thread = threading.Thread(target=self.dbWorker, kwargs={'map_path': map_path, 'map_name': "%d-%d" % (x, y)})
            db_thread.start()

            tile_threads = []
            num_worker_threads = len(os.sched_getaffinity(0))
            self.logger.debug("    number of threads: %d" % num_worker_threads)

            for i in range(num_worker_threads):
                t = threading.Thread(target=self.tileWorker)
                t.start()
                tile_threads.append(t)

            tile = Tile(7, x, y, elements)
            self.tileQueue.put(tile)

            # block until all tasks are done
            self.tileQueue.join()
            self.dbQueue.join()

            # stop workers
            for i in range(num_worker_threads):
                self.tileQueue.put(None)
            for t in tile_threads:
                t.join()
            self.dbQueue.put(None)
            db_thread.join()

        """
        osmosis_call += ['--mw','file=%s' % map_path]
        osmosis_call += ['type=%s' % mem_type] # hd type is currently unsupported
        osmosis_call += ['map-start-zoom=%s' % configuration.MAP_START_ZOOM]
        osmosis_call += ['preferred-languages=%s' % configuration.PREFERRED_LANGUAGES]
        osmosis_call += ['zoom-interval-conf=%s' % configuration.ZOOM_INTERVAL]
        osmosis_call += ['bbox=%.4f,%.4f,%.4f,%.4f' % (llrb[0],lllt[1],lllt[0],llrb[1])]
        osmosis_call += ['way-clipping=false']
        osmosis_call += ['tag-conf-file=%s' % configuration.TAG_MAPPING]
        """

        self.logger.info("Finished map: %s" % map_path)

        if not self.dry_run and has_elements:
            if os.path.getsize(map_path) == 0:
                raise Exception("Resulting map file size for %s is zero, keeping old map file" % map_path)

        # remove intermediate pbf file and log on success
        if intermediate and not keep:
            self.logger.debug("    removing intermediate file %s", pbf_path)
            os.remove(pbf_path)
            self.logger.debug("    removing log file %s", log_path)
            os.remove(log_path)

        if has_elements:
            return map_path
        else:
            return None

    def dbWorker(self, map_path=None, map_name=None):
        db = MTilesDatabase(map_path)
        db.create(map_name, 'baselayer', '1', 'maptrek')
        while True:
            job = self.dbQueue.get()
            if job is None:
                break
            self.logger.debug("    saving tile %s with %d features" % (job.tile, len(job.features)))
            for feature in job.features:
                #if name is not None:
                #    putFeature(options.mbtiles_output, feature, putName(options.mbtiles_output, name))
                #    feature.get('properties').pop('name', None)
                pass
            encoded = OSciMap4.encode(job.features)
            db.putTile(job.tile.zoom, job.tile.x, job.tile.y, encoded)
            self.dbQueue.task_done()
        db.finish()

    def tileWorker(self):
        while True:
            tile = self.tileQueue.get()
            if tile is None:
                break
            self.generateTile(tile)
            self.tileQueue.task_done()

    def generateTile(self, tile):
        if tile.zoom > 7:
            self.logger.debug("    generating tile %s with %d elements" % (tile, len(tile.elements)))

            unions = defaultdict(list)
            features = []
            pixelArea = tile.pixelWidth * tile.pixelWidth

            for element in tile.elements:
                if element.mapping.get('zoom-min', 0) > tile.zoom:
                    continue
                geom = element.geom
                if tile.zoom < 14:
                    if element.area and element.area < pixelArea * element.mapping.get('filter-area', 1):
                        continue
                    if element.mapping.get('buffer', False):
                        geom = geom.buffer(tile.pixelWidth)
                    simple_geom = geom.simplify(tile.pixelWidth)
                    if simple_geom.is_valid:
                        geom = simple_geom
                if 'union-key' in element.mapping:
                    key = element.mapping['union-key']
                    element.geometry = geom
                    unions[key].append(element)
                    continue
                element.geometry = affine_transform(geom, tile.matrix)
                features.append(element)

            for union in unions:
                # create united geometry
                united_geom = cascaded_union([el.geometry for el in unions[union]])
                first = unions[union][0]
                pattern = [x.strip() for x in first.mapping['union'].split(',')]
                # get united tags
                united_tags = {k: v for k, v in first.tags.items() if k in pattern}
                # transform geometry
                #if tile.zoom < 14:
                #    united_geom = united_geom.simplify(tile.pixelWidth)
                if 'transform' in first.mapping:
                    pass
                element = Element(None, united_geom, united_tags)
                element.geometry = affine_transform(element.geom, tile.matrix)
                features.append(element)

            self.dbQueue.put(DBJob(tile, features))

        # propagate elements to lower zoom
        if tile.zoom < 14:
            nx = tile.x << 1
            ny = tile.y << 1
            nz = tile.zoom + 1
            self.generateSubtiles(nx,   ny,   nz, tile)
            self.generateSubtiles(nx,   ny+1, nz, tile)
            self.generateSubtiles(nx+1, ny,   nz, tile)
            self.generateSubtiles(nx+1, ny+1, nz, tile)

    def generateSubtiles(self, x, y, zoom, tile):
        # https://stackoverflow.com/a/43105613/488489 - indexing
        clip = Tile.bbox(x, y, zoom)
        prepared_clip = prep(clip)
        elements = [element.clone(clip.intersection(element.geom)) for element in tile.elements if prepared_clip.intersects(element.geom)]
        self.tileQueue.put(Tile(zoom, x, y, elements))

    def map_path_base(self, x, y, zoom=7):
        """
        returns path to map file but without extension
        """
        return os.path.join(self.data_dir, str(zoom), str(x), '%d-%d' % (x, y))

    def pbf_path(self, x, y, zoom=7):
        """
        returns path to intermediate pbf file
        """
        return self.map_path_base(x, y, zoom) + ".osm.pbf"

    def map_path(self, x, y):
        """
        returns path to destination map file
        """
        return self.map_path_base(x, y) + ".mtiles"

    def log_path(self, x, y):
        """
        returns path to log file
        """
        return self.map_path_base(x, y) + ".log"


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

    if not args.from_file:
        print("Database source is currently not supported")
        exit(1)

    logging.getLogger("shapely").setLevel(logging.ERROR)
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
