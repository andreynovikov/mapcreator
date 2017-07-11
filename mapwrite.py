#!/usr/bin/env python3

import os
import sys
import math
import threading
import multiprocessing
import argparse
import subprocess
import logging.config
from collections import defaultdict, namedtuple

from tqdm import tqdm

import psycopg2
import psycopg2.extras
import osmium
import mercantile
import numpy
import shapely.wkb as shapelyWkb
import shapely.speedups
from shapely import geometry
from shapely.prepared import prep
from shapely.ops import transform, linemerge, cascaded_union, unary_union, polylabel
from shapely.affinity import affine_transform

import configuration
import mappings
from encoder import encode
from util.database import MTilesDatabase
from util.geometry import wgs84_to_mercator, mercator_to_wgs84, clockwise
from util.osm import is_area
from util.osm.kind import get_kind
from util.osm.buildings import get_building_properties
from util.filters import filter_rings


ProcessJob = namedtuple('ProcessJob', ['id', 'wkb', 'tags', 'mapping', 'simple_polygon'])
DBJob = namedtuple('DBJob', ['zoom', 'x', 'y', 'features'])
Feature = namedtuple('Feature', ['geometry', 'tags', 'kind', 'label', 'height', 'min_height', 'building_color', 'roof_color'])

wkbFactory = osmium.geom.WKBFactory()


def deep_get(dictionary, *keys):
    for key in keys:
        if isinstance(dictionary, dict):
            dictionary = dictionary.get(key, {})
        else:
            return {}
    return dictionary


class Element():
    def __init__(self, id, geom, tags, mapping=None):
        self.id = id
        self.geom = geom # original geometry
        self.tags = tags
        self.mapping = mapping
        self.label = None
        self.area = None
        self.kind = None
        self.height = None
        self.min_height = None
        self.building_color = None
        self.roof_color = None
        self.geometry = None # tile processed temporary geometry

    def __str__(self):
        #geom = transform(mercator_to_wgs84, self.geom)
        #return "%s: %s\n%s\n%s\n" % (str(self.id), geom, self.tags, self.mapping)
        return "%s: %s\n%s\n%s\n" % (str(self.id), self.geom.__repr__(), self.tags, self.mapping)

    def clone(self, geom):
        el = Element(self.id, geom, self.tags, self.mapping)
        el.label = self.label
        el.area = self.area
        el.kind = self.kind
        el.height = self.height
        el.min_height = self.min_height
        el.building_color = self.building_color
        el.roof_color = self.roof_color
        return el


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, elements, logger):
        super(OsmFilter, self).__init__()
        self.elements = elements
        self.outlines = set()
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
                            continue
                    if 'adjust' in m:
                        v = m['adjust'](v)
                    if v is None:
                        continue
                    filtered_tags[k] = v
                    renderable = renderable or m.get('render', True)
                    for k in ('transform','union','union-zoom-max','calc-area','filter-area','buffer','enlarge','force-line','label','filter-type','clip-buffer'):
                        if k in m:
                            mapping[k] = m[k]
                    if 'zoom-min' in m:
                        if 'zoom-min' not in mapping or m['zoom-min'] < mapping['zoom-min']:
                            mapping['zoom-min'] = m['zoom-min']
        return renderable, filtered_tags, mapping

    def process(self, t, o):
        renderable, tags, mapping = self.filter(o.tags)
        if renderable:
            if t > 1:
                area = is_area(tags)
                if t == 2 and o.is_closed() and area:
                    return # will get it later in area handler
                if t == 3 and o.from_way() and not area:
                    return # have added it already in ways handler
            try:
                if t == 1:
                    id = o.id
                    wkb = wkbFactory.create_point(o)
                if t == 2:
                    id = o.id
                    wkb = wkbFactory.create_linestring(o)
                if t == 3:
                    id = o.orig_id()
                    wkb = wkbFactory.create_multipolygon(o)
                geom = transform(wgs84_to_mercator, shapelyWkb.loads(wkb, hex=True))
                if t == 3 and not o.is_multipolygon():
                    geom = geom[0] # simplify geometry
                if mapping.pop('force-line', False) and geom.type in ['Polygon', 'MultiPolygon']:
                    geom = geom.boundary
                if 'filter-type' in mapping and geom.type not in mapping.pop('filter-type', []):
                    return
                geom = clockwise(geom)
                self.elements.append(Element(id, geom, tags, mapping))
            except Exception as e:
                self.logger.error("%s %s" % (e, id))

    def node(self, n):
        self.process(1, n)

    def way(self, w):
        self.process(2, w)

    def area(self, a):
        self.process(3, a)

    def relation(self, r):
        t = None
        for tag in r.tags:
            if tag.k == 'type':
                t = tag.v
        if t == 'building':
            for member in r.members:
                if member.role == 'outline':
                    self.outlines.add(member.ref)

    def finish(self):
        if self.outlines:
            found = 0
            for element in self.elements:
                if element.id in self.outlines:
                    found = found + 1
                    element.tags['building:outline'] = 1
            self.logger.debug("    outlined %d of %d buildings" % (found, len(self.outlines)))
        self.logger.debug("    elements: %d" % len(self.elements))


class Tile():
    RADIUS = 6378137
    CIRCUM = 2 * math.pi * RADIUS
    SIZE = 256
    SCALE = 4096
    INITIAL_RESOLUTION = CIRCUM / SIZE

    def __init__(self, zoom, x, y, elements=None):
        self.zoom = zoom
        self.x = x
        self.y = y
        self.elements = elements if elements else []
        self.pixelWidth = self.INITIAL_RESOLUTION / 2 ** self.zoom
        self.bounds = mercantile.xy_bounds(x, y, zoom)
        self.matrix = [Tile.SCALE / (self.bounds.right - self.bounds.left), 0, 0,
                       Tile.SCALE / (self.bounds.top - self.bounds.bottom), -self.bounds.left * Tile.SCALE / (self.bounds.right - self.bounds.left),
                       -self.bounds.bottom * Tile.SCALE / (self.bounds.top - self.bounds.bottom)]
        self.bbox = geometry.Polygon([[self.bounds.left, self.bounds.bottom], [self.bounds.left, self.bounds.top],
                                      [self.bounds.right, self.bounds.top], [self.bounds.right, self.bounds.bottom]])

    def __str__(self):
        return "%d/%d/%d" % (self.zoom, self.x, self.y)


class BBoxCache(defaultdict):
    def __init__(self, tile):
        self.tile = tile

    def __missing__(self, key):
        if key == 0:
            bbox = self.tile.bbox
        else:
            bbox = self.tile.bbox.buffer(self.tile.pixelWidth * key)
        self[key] = bbox
        return bbox


def process_element(geom, tags, mapping):
    kind = get_kind(tags)
    #TODO process only if kind is building
    height, min_height, color, roof_color = get_building_properties(tags)
    label = None
    if mapping.get('label', False):
        if geom.type == 'Polygon':
            label = polylabel(geom, 1.194) # pixel width at zoom 17
        elif geom.type == 'MultiPolygon':
            #TODO in future allow multiple polygons have their own labels
            area = 0
            polygon = None
            for p in geom:
                if p.area > area:
                    area = p.area
                    polygon = p
            if polygon:
                label = polylabel(polygon, 1.194)
        else:
            pass
    area = None
    if mapping.get('calc-area', False):
        area = geom.area
    return (kind, area, label, height, min_height, color, roof_color)


class MapWriter:

    def __init__(self, data_dir, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.simplification = 0.0
        self.interactive = not verbose and sys.__stdin__.isatty()

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

        log_path = self.log_path(x, y)
        #TODO redirect logger to file
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
                        bbox = mercantile.bounds(ax, ay, 3)
                        osmconvert_call = [configuration.OSMCONVERT_PATH, configuration.SOURCE_PBF]
                        osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (bbox.west,bbox.south,bbox.east,bbox.north)]
                        osmconvert_call += ['--complex-ways', '-o=%s' % upper_pbf_path]
                        self.logger.debug("    calling: %s", " ".join(osmconvert_call))
                        if not self.dry_run:
                            subprocess.check_call(osmconvert_call)
                        else:
                            subprocess.check_call(['touch', upper_pbf_path])
                    # extract area data from upper intermediate file
                    bbox = mercantile.bounds(x, y, 7)
                    osmconvert_call = [configuration.OSMCONVERT_PATH, upper_pbf_path]
                    osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (bbox.west,bbox.south,bbox.east,bbox.north)]
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

        elements = []
        handler = OsmFilter(elements, self.logger)
        handler.apply_file(pbf_path)
        handler.finish()

        # process map only if it contains relevant data
        has_elements = bool(elements)
        if has_elements:
            self.db = MTilesDatabase(map_path)
            self.db.create("%d-%d" % (x, y), 'baselayer', '1', 'maptrek')

            num_worker_threads = len(os.sched_getaffinity(0))
            self.logger.debug("    number of threads: %d" % num_worker_threads)
            worker_threads = []
            pool = multiprocessing.Pool(num_worker_threads)

            if self.interactive:
                self.proc_progress = tqdm(total=len(elements), desc="Processed", maxinterval=1.0)

            results = []
            # pre-process elements
            for idx, element in enumerate(elements):
                def process_result(result, index=idx):
                    el = elements[index]
                    el.kind, el.area, el.label, el.height, el.min_height, el.building_color, el.roof_color = result
                    if 'name' in el.tags:
                        el.tags['id'] = el.id
                        self.db.putFeature(el.id, el.tags['name'], el.kind, el.label, el.geom)
                    if self.interactive:
                        self.proc_progress.update()
                results.append(pool.apply_async(process_element, [element.geom, element.tags, element.mapping], callback=process_result))
            pool.close()

            extra_elements = []
            # get supplementary data while elements are processed
            with psycopg2.connect(configuration.DATA_DB_DSN) as c:
                bounds = mercantile.xy_bounds(x, y, 7)
                bbox = "ST_Expand(ST_MakeEnvelope({left}, {bottom}, {right}, {top}, 3857), {expand})" \
                       .format(left=bounds.left, bottom=bounds.bottom, right=bounds.right, top=bounds.top, expand=1.194*4)
                for data in mappings.queries:
                    if data['srid'] != 3857:
                        qbbox = "ST_Transform({bbox}, {srid})".format(bbox=bbox, srid=data['srid'])
                    else:
                        qbbox = bbox
                    sql = "SELECT ST_AsBinary(geom) AS geometry, * FROM ({query}) AS data WHERE ST_Intersects(geom, {bbox})".format(query=data['query'], bbox=qbbox)
                    try:
                        cur = c.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        cur.execute(str(sql)) # if str() is not used 'where' is lost for some weird reason
                        rows = cur.fetchall()
                        self.logger.debug("      %s", cur.query)
                        for row in rows:
                            geom = shapelyWkb.loads(bytes(row['geometry']))
                            if data['srid'] != 3857: # we support only 3857 and 4326 projections
                                geom = transform(wgs84_to_mercator, geom)
                            tags, mapping = data['mapper'](row)
                            extra_elements.append(Element(None, geom, tags, mapping))
                    except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
                        logger.exception("Query error: %s" % sql)
                    finally:
                        cur.close()

            # wait for results, look for errors
            for r in results:
                r.get()

            if self.interactive:
                self.proc_progress.close()

            self.logger.debug("    finished pre-processing elements")

            if extra_elements:
                self.logger.debug("    extra elements: %d" % len(extra_elements))
                elements += extra_elements

            if self.interactive:
                num_tiles = 0
                for z in range(1, 15-7):
                    n = 4 ** z
                    num_tiles = num_tiles + n
                self.gen_progress = tqdm(total=num_tiles, desc="Generated")

            tile_queue = multiprocessing.JoinableQueue()
            db_queue = multiprocessing.JoinableQueue()

            db_thread = threading.Thread(target=self.dbWorker, args=(db_queue,))
            db_thread.start()

            processes = []
            for i in range(num_worker_threads):
                p = multiprocessing.Process(target=self.tileWorker, args=(tile_queue, db_queue))
                p.start()
                processes.append(p)

            tile = Tile(7, x, y, elements)
            tile_queue.put(tile)

            self.db.commit()

            # block until all tasks are done
            tile_queue.join()
            db_queue.join()

            # stop workers
            for i in range(num_worker_threads):
                tile_queue.put(None)
            for p in processes:
                p.join()
            db_queue.put(None)
            db_thread.join()

            tile_queue.close()
            db_queue.close()

            self.db.finish()

            if self.interactive:
                self.gen_progress.close()

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

    def dbWorker(self, queue):
        while True:
            job = queue.get()
            if job is None:
                queue.task_done()
                break
            self.db.putTile(job.zoom, job.x, job.y, job.features)
            queue.task_done()
            if self.interactive:
                self.gen_progress.update()

    def tileWorker(self, tile_queue, db_queue):
        self.tileQueue = tile_queue
        self.dbQueue = db_queue
        while True:
            tile = tile_queue.get()
            if tile is None:
                tile_queue.task_done()
                break
            try:
                self.generateTile(tile)
            except Exception as e:
                self.logger.exception("Error generating tile %s" % tile)
            tile_queue.task_done()

    def generateTile(self, tile):
        if tile.zoom > 7:
            if len(tile.elements) > 0:
                self.logger.debug("    generating tile %s with %d elements" % (tile, len(tile.elements)))

            unions = defaultdict(list)
            merges = defaultdict(list)
            features = []
            pixelArea = tile.pixelWidth * tile.pixelWidth
            prepared_clip = prep(tile.bbox)

            building_parts_geom = None
            building_parts_prepared = None
            if tile.zoom == 14:
                building_parts = [element.geom for element in tile.elements if 'building:part' in element.tags and 'building' not in element.tags]
                if building_parts:
                    building_parts_geom = cascaded_union(building_parts)
                    building_parts_prepared = prep(building_parts_geom)

            for element in tile.elements:
                if element.mapping.get('zoom-min', 0) > tile.zoom:
                    continue
                geom = element.geom
                if tile.zoom < 14:
                    if element.area and element.area < pixelArea * element.mapping.get('filter-area', 1):
                        continue
                    if 'buffer' in element.mapping:
                        geom = geom.buffer(tile.pixelWidth * element.mapping.get('buffer', 1))
                    simple_geom = geom.simplify(tile.pixelWidth)
                    if simple_geom.is_valid:
                        geom = simple_geom
                else:
                    if 'enlarge' in element.mapping:
                        geom = geom.buffer(tile.pixelWidth * element.mapping.get('enlarge', 1))
                    if 'building' in element.tags and not 'building:outline' in element.tags and not 'building:part' in element.tags:
                        #if building_parts_geom is None or not building_parts_prepared.intersects(element.geom) or building_parts_geom.intersection(element.geom).area == 0:
                        if building_parts_geom is None or not building_parts_prepared.covers(element.geom):
                            element.tags['building:part'] = element.tags['building']
                if 'union' in element.mapping and tile.zoom <= element.mapping.get('union-zoom-max', 14) and geom.type in ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']:
                    if type(element.mapping['union']) is dict:
                        pattern = [k for k, v in element.mapping['union'].items() if tile.zoom >= v]
                    else:
                        pattern = [x.strip() for x in element.mapping['union'].split(',')]
                    values = [element.tags[k] for k in sorted(set(pattern) & set(element.tags.keys()))]
                    key = hash(tuple(values))
                    element.geometry = geom
                    if geom.type in ['LineString', 'MultiLineString']:
                        merges[key].append(element)
                    else:
                        unions[key].append(element)
                    continue
                if tile.zoom < 14 and 'transform' in element.mapping:
                    if element.mapping.get('transform') == 'filter-rings':
                        geom = filter_rings(geom, pixelArea)
                geometry = affine_transform(geom, tile.matrix)
                label = None
                if element.label and prepared_clip.contains(element.label):
                    label = affine_transform(element.label, tile.matrix)
                features.append(Feature(geometry, element.tags, element.kind, label, element.height, element.min_height, element.building_color, element.roof_color))

            #TODO combine union and merge to one logical block
            for union in unions:
                # create united geometry
                united_geom = cascaded_union([el.geometry for el in unions[union]])
                first = unions[union][0]
                if type(first.mapping['union']) is dict:
                    pattern = [k for k, v in first.mapping['union'].items() if tile.zoom >= v]
                else:
                    pattern = [x.strip() for x in first.mapping['union'].split(',')]
                # get united tags
                united_tags = {k: v for k, v in first.tags.items() if k in pattern}
                # transform geometry
                if tile.zoom < 14 and 'transform' in first.mapping:
                    if first.mapping.get('transform') == 'filter-rings':
                        united_geom = filter_rings(united_geom, pixelArea)
                geometry = affine_transform(united_geom, tile.matrix)
                features.append(Feature(geometry, united_tags, None, None, None, None, None, None))

            for merge in merges:
                first = merges[merge][0]
                # create united geometry
                lines = []
                for el in merges[merge]:
                    if el.geometry.type == 'LineString':
                        lines.append(el.geometry)
                    else:
                        lines.extend(el.geometry.geoms)
                united_geom = linemerge(lines)
                # simplify once more after merge
                united_geom = united_geom.simplify(tile.pixelWidth)
                if type(first.mapping['union']) is dict:
                    pattern = [k for k, v in first.mapping['union'].items() if tile.zoom >= v]
                else:
                    pattern = [x.strip() for x in first.mapping['union'].split(',')]
                # get united tags
                united_tags = {k: v for k, v in first.tags.items() if k in pattern}
                if 'id' in first.tags:
                    united_tags['id'] = first.tags['id']
                geometry = affine_transform(united_geom, tile.matrix)
                features.append(Feature(geometry, united_tags, None, None, None, None, None, None))

            encoded = encode(features, mappings.tags)
            self.dbQueue.put(DBJob(tile.zoom, tile.x, tile.y, encoded))

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
        subtile = Tile(zoom, x, y)
        # https://stackoverflow.com/a/43105613/488489 - indexing
        prepared_clip = prep(subtile.bbox.buffer(1.194 * 4))
        clipCache = BBoxCache(subtile)
        for element in tile.elements:
            if prepared_clip.covers(element.geom):
                subtile.elements.append(element)
            elif prepared_clip.intersects(element.geom):
                subtile.elements.append(element.clone(clipCache[element.mapping.get('clip-buffer', 4)].intersection(element.geom)))
        self.tileQueue.put(subtile)

    def map_path_base(self, x, y, zoom=7):
        """
        returns path to map file but without extension
        """
        output_dir = os.path.join(self.data_dir, str(zoom), str(x))
        if not self.dry_run and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return os.path.join(output_dir, '%d-%d' % (x, y))

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

    logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s - %(message)s')
    logging.getLogger("shapely").setLevel(logging.ERROR)
    logger = logging.getLogger(__name__)
    # during a dry run the console should receive all logs
    if args.dry_run or args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        mapWriter = MapWriter(args.data_path, args.dry_run, args.verbose)
        mapWriter.createMap(args.x, args.y, args.intermediate, args.keep, args.from_file)
    except Exception as e:
        logger.exception("An error occurred:")
