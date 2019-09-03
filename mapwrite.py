#!/usr/bin/env python3

import os
import sys
import gc
import math
import queue
import threading
import multiprocessing
import argparse
import subprocess
import logging.config
import psutil
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from tqdm import tqdm

import psycopg2
import psycopg2.extras
import osmium
import mercantile
import numpy
import shapely.wkb as shapelyWkb
import shapely.speedups
from shapely.geometry import MultiLineString, Polygon
from shapely.prepared import prep
from shapely.ops import transform, linemerge, cascaded_union, unary_union
from shapely.algorithms.polylabel import polylabel
from shapely.affinity import affine_transform

import configuration
import mappings
from encoder import encode
from util.core import Element
from util.database import MTilesDatabase
from util.geometry import wgs84_to_mercator, mercator_to_wgs84, clockwise
from util.osm import is_area
from util.osm.kind import is_place, is_building, get_kind
from util.osm.buildings import get_building_properties
from util.filters import filter_rings


logging.getLogger('shapely.geos').setLevel(logging.WARNING)

ProcessJob = namedtuple('ProcessJob', ['id', 'wkb', 'tags', 'mapping', 'simple_polygon'])
DBJob = namedtuple('DBJob', ['zoom', 'x', 'y', 'features'])
Feature = namedtuple('Feature', ['id', 'geometry', 'tags', 'kind', 'label', 'height', 'min_height', 'building_color', 'roof_color'])

wkbFactory = osmium.geom.WKBFactory()


def deep_get(dictionary, *keys):
    for key in keys:
        if isinstance(dictionary, dict):
            dictionary = dictionary.get(key, {})
        else:
            return {}
    return dictionary


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, elements, basemap, logger):
        super(OsmFilter, self).__init__()
        self.elements = elements
        self.processors = set()
        self.outlines = set()
        self.logger = logger
        self.basemap = basemap
        self.ignorable = 0

    def filter(self, tags):
        filtered_tags = {}
        mapping = {}
        renderable = False
        ignorable = True
        modifiers = set()
        for tag in tags:
            if tag.k in mappings.tags.keys():
                m = mappings.tags[tag.k].get('__any__', None)
                if m is None:
                    m = mappings.tags[tag.k].get(tag.v, None)
                if m is not None: #empty dictionaries should be also accounted
                    k = tag.k.strip().lower()
                    v = tag.v
                    if 'rewrite-key' in m or 'rewrite-value' in m:
                        k = m.get('rewrite-key', k)
                        if m.get('rewrite-if-missing', False) and filtered_tags.get(k, None):
                            continue
                        v = m.get('rewrite-value', v)
                        m = mappings.tags[k].get(v, mappings.tags[k].get('__any__', {}))
                    if 'one-of' in m:
                        if v not in m['one-of']:
                            continue
                    if 'adjust' in m:
                        v = m['adjust'](v)
                    if v is None:
                        continue
                    if isinstance(v, str) and k not in ('name', 'name:en', 'name:de', 'name:ru', 'ref', 'icao', 'iata'):
                        v = v.strip().lower()
                        if ';' in v:
                            v = v.split(';')[0]
                    filtered_tags[k] = v
                    render = m.get('render', True)
                    renderable = renderable or render
                    ignorable = ignorable and (m.get('ignore', not render))
                    for k in ('transform','filter-area','buffer','enlarge','force-line','label','filter-type','clip-buffer', \
                              'keep-tags','basemap-label','basemap-keep-tags','basemap-filter-area'):
                        if k in m:
                            mapping[k] = m[k]
                    if 'union' in m:
                        if 'union' in mapping:
                            combined_union = {}
                            if type(mapping['union']) is dict:
                                combined_union = mapping['union']
                            else:
                                zoom = mapping.get('zoom-min', 0)
                                combined_union = {k: zoom for k in mapping['union'].split(',')}
                            if type(m['union']) is dict:
                                for k, v in m['union'].items():
                                    if k not in combined_union or combined_union[k] > v:
                                        combined_union[k] = v
                            else:
                                zoom = m.get('zoom-min', 0)
                                for k in m['union'].split(','):
                                    if k not in combined_union or combined_union[k] > zoom:
                                        combined_union[k] = zoom
                            mapping['union'] = combined_union
                        else:
                            mapping['union'] = m['union']
                    if 'check-meta' in m:
                        mapping['check-meta'] = m['check-meta'] or mapping.get('check-meta', False)
                    if 'union-zoom-max' in m:
                        if 'union-zoom-max' not in mapping or m['union-zoom-max'] < mapping['union-zoom-max']:
                            mapping['union-zoom-max'] = m['union-zoom-max']
                    if 'zoom-min' in m:
                        if 'zoom-min' not in mapping or m['zoom-min'] < mapping['zoom-min']:
                            mapping['zoom-min'] = m['zoom-min']
                    if 'zoom-max' in m:
                        if 'zoom-max' not in mapping or m['zoom-max'] > mapping['zoom-max']:
                            mapping['zoom-max'] = m['zoom-max']
                    if 'modify-mapping' in m:
                        modifiers.add(m['modify-mapping'])
                    if 'pre-process' in m:
                        self.processors.add(m['pre-process'])

        for modifier in modifiers:
            renderable, ignorable, mapping = modifier(filtered_tags, renderable, ignorable, mapping)
        if self.basemap and mapping.get('zoom-min', 0) > 7:
            renderable = False
        if renderable:
            tag_filter = None
            if self.basemap and 'basemap-keep-tags' in mapping:
                tag_filter = mapping['basemap-keep-tags']
            elif 'keep-tags' in mapping:
                tag_filter = mapping['keep-tags']
            if tag_filter:
                keep = [x.strip() for x in tag_filter.split(',')]
                filtered_tags = {k: filtered_tags[k] for k in set(keep) & set(filtered_tags.keys())}
            if ignorable:
                self.ignorable += 1
        return renderable, filtered_tags, mapping

    def process(self, t, o):
        if len(o.tags) == 0:
            return
        renderable, tags, mapping = self.filter(o.tags)
        if renderable:
            if t > 1:
                area = is_area(tags)
                if t == 2 and o.is_closed() and area:
                    return # will get it later in area handler
                if t == 3 and o.from_way() and not area:
                    return # have added it already in ways handler
            try:
                id = o.id
                if t == 1:
                    wkb = wkbFactory.create_point(o)
                if t == 2:
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
                # construct unique id
                if t == 3 and o.from_way():
                    t = 2
                id = (id << 2) + t
                self.elements.append(Element(id, geom, tags, mapping))
            except Exception as e:
                self.logger.error("%s: %s" % (id, e))

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
        if self.ignorable:
            if len(self.elements) == self.ignorable:
                self.elements.clear()
                self.logger.debug("    all elements are ignored")
                return
        if self.outlines:
            found = 0
            for element in self.elements:
                if element.id in self.outlines:
                    found = found + 1
                    element.tags['building:outline'] = 1
            self.logger.debug("    outlined %d of %d buildings" % (found, len(self.outlines)))
        return self.processors


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
        self.bbox = Polygon([[self.bounds.left, self.bounds.bottom], [self.bounds.left, self.bounds.top],
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


def process_element(geom, tags, mapping, basemap=False):
    kind = get_kind(tags)
    #TODO process only if kind is building
    if is_building(kind):
        height, min_height, color, roof_color = get_building_properties(tags)
    else:
        height, min_height, color, roof_color = (None, None, None, None)
    label = None
    if mapping.get('label', False) and (not basemap or mapping.get('basemap-label', False)):
        if geom.type == 'Polygon':
            label = polylabel(geom, 1.194) # pixel width at zoom 17
        elif geom.type == 'MultiPolygon':
            label = []
            area = 0
            for p in geom:
                l = polylabel(p, 1.194)
                if p.area > area: # we need to find largest polygon for main label
                    area = p.area
                    label.insert(0, l)
                else:
                    label.append(l)
        else:
            pass
    area = None
    if mapping.get('filter-area', None) or (basemap and mapping.get('basemap-filter-area', None)):
        area = geom.area
    return (kind, area, label, height, min_height, color, roof_color)


class MapWriter:

    def __init__(self, data_dir, dry_run=False, forbid_interactive=False):
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.interactive = not forbid_interactive and sys.__stdin__.isatty()

        try:
            # Enable C-based speedups available from 1.2.10+
            from shapely import speedups
            if speedups.available:
                self.logger.debug("Enabling Shapely speedups")
                speedups.enable()
        except:
            self.logger.warn("Upgrade Shapely for performance improvements")

    def createMap(self, x, y, intermediate=False, keep=False, from_file=False):
        self.stubmap = x == -2 and y == -2
        self.basemap = self.stubmap or (x == -1 and y == -1)

        if self.stubmap:
            mappings.mapType = mappings.MapTypes.Stub
        elif self.basemap:
            mappings.mapType = mappings.MapTypes.Base

        map_path = self.map_path(x, y)
        start_time = datetime.utcnow()
        self.logger.info("Creating map: %s" % map_path)

        log_path = self.log_path(x, y)
        #TODO redirect logger to file
        logfile = open(log_path, 'a')

        if not from_file:
            logfile.close()
            raise NotImplementedError('Loading data from database is not implemented yet')
        if intermediate or from_file:
            pbf_path = self.pbf_path(x, y)
            self.timestamp = os.path.getmtime(configuration.SOURCE_PBF)
            if not os.path.exists(pbf_path) or os.path.getmtime(pbf_path) < self.timestamp:
                if from_file:
                    source_pbf_path = configuration.SOURCE_PBF
                    if self.basemap:
                        self.generateBasemapFile(source_pbf_path)
                    else:
                        if intermediate:
                            # create upper intermediate files (zoom=3,5) to optimize processing of adjacent areas
                            source_pbf_path = self.generateIntermediateFile(source_pbf_path, x, y, 3, " upper")
                            source_pbf_path = self.generateIntermediateFile(source_pbf_path, x, y, 5, " middle")
                        self.generateIntermediateFile(source_pbf_path, x, y, 7, "")

        self.logger.info("  Processing file: %s" % pbf_path)

        elements = []
        handler = OsmFilter(elements, self.basemap, self.logger)
        handler.apply_file(pbf_path)
        processors = handler.finish()
        del handler
        gc.collect()

        process = psutil.Process(os.getpid())
        total = psutil.virtual_memory().total // 1048576
        used = process.memory_info().rss // 1048576
        self.logger.info("    memory used: {:,}M out of {:,}M".format(used, total))

        # process map only if it contains relevant data
        has_elements = bool(elements)
        if has_elements:
            self.multiprocessing = total / used > 4

            self.timestamp = int(self.timestamp / 3600 / 24)

            for processor in processors:
                self.logger.info("    calling pre-processor %s.%s" % (processor.__module__, processor.__name__))
                processor(elements, self.interactive)

            self.db = MTilesDatabase(map_path)
            if self.basemap:
                self.db.create("basemap", 'baselayer', '1', self.timestamp, 'maptrek')
            else:
                self.db.create("%d-%d" % (x, y), 'baselayer', '1', self.timestamp, 'maptrek')

            if self.multiprocessing:
                num_worker_threads = len(os.sched_getaffinity(0))
                if self.basemap and not self.stubmap:
                    # temporary hack
                    num_worker_threads = 2
                self.logger.info("    running in multiprocessing mode with %d workers" % num_worker_threads)
            else:
                num_worker_threads = 1
                self.logger.info("    running in single threaded mode")
            worker_threads = []

            pool = None
            if self.multiprocessing and len(elements) > 100:
                pool = multiprocessing.Pool(num_worker_threads)

            if self.interactive:
                self.proc_progress = tqdm(total=len(elements), desc="Processed", maxinterval=1.0)
            else:
                self.logger.info("    processing %d elements" % len(elements))

            results = []
            places = []
            # pre-process elements
            for idx, element in enumerate(elements):
                def process_result(result, index=idx):
                    el = elements[index]
                    el.kind, el.area, el.label, el.height, el.min_height, el.building_color, el.roof_color = result
                    # remove overlapping places (point and polygon)
                    # due to file processing logic we assume that points go first, if not - introduce sort
                    if el.id and is_place(el.kind):
                        if el.geom.type == 'Point':
                            places.append(el)
                        elif len(places):
                            for place in places:
                                if el.tags.get('place', '---') == place.tags.get('place', '===') \
                                   and el.tags.get('name', '---').split(' (')[0] == place.tags.get('name', '===').split(' (')[0] \
                                   and el.geom.contains(place.geom):
                                    # copy names to point and remove them from polygon
                                    if 'name:en' in el.tags:
                                        name = el.tags.pop('name:en', None)
                                        if 'name:en' not in place.tags:
                                            place.tags['name:en'] = name
                                    if 'name:de' in el.tags:
                                        name = el.tags.pop('name:de', None)
                                        if 'name:de' not in place.tags:
                                            place.tags['name:de'] = name
                                    if 'name:ru' in el.tags:
                                        name = el.tags.pop('name:ru', None)
                                        if 'name:ru' not in place.tags:
                                            place.tags['name:ru'] = name
                                    el.tags.pop('name', None)
                                    break
                    # if feature has name save it for future reference
                    if 'name' in el.tags:
                        self.db.putFeature(el.id, el.tags, el.kind, el.label, el.geom)
                        el.tags.pop('name:en', None)
                        el.tags.pop('name:de', None)
                        el.tags.pop('name:ru', None)
                        el.tags['id'] = el.id
                    if self.interactive:
                        self.proc_progress.update()
                if pool:
                    results.append(pool.apply_async(process_element, [element.geom, element.tags, element.mapping, self.basemap],
                                                    callback=process_result))
                else:
                    process_result(process_element(element.geom, element.tags, element.mapping, self.basemap))
            if pool:
                pool.close()

            extra_elements = []
            # get supplementary data while elements are processed
            with psycopg2.connect(configuration.DATA_DB_DSN) as c:
                if self.stubmap:
                    queries = mappings.stubmap_queries
                elif self.basemap:
                    queries = mappings.basemap_queries
                else:
                    queries = mappings.queries
                    bounds = mercantile.xy_bounds(x, y, 7)
                    expand = 1.194*4
                    left_expand = 0
                    right_expand = 0
                    if x > 0:
                        left_expand = expand
                    if x < 127:
                        right_expand = expand
                    bbox = "ST_MakeEnvelope({left}, {bottom}, {right}, {top}, 3857)" \
                           .format(left=(bounds.left - left_expand), bottom=(bounds.bottom - expand),
                                   right=(bounds.right + right_expand), top=(bounds.top + expand))
                for data in queries:
                    if self.basemap:
                        sql = "SELECT ST_AsBinary(geom) AS geometry, * FROM ({query}) AS data".format(query=data['query'])
                    else:
                        if data['srid'] != 3857:
                            qbbox = "ST_Transform({bbox}, {srid})".format(bbox=bbox, srid=data['srid'])
                        else:
                            qbbox = bbox
                        sql = "SELECT ST_AsBinary(geom) AS geometry, * FROM ({query}) AS data WHERE ST_Intersects(geom, {bbox})" \
                              .format(query=data['query'], bbox=qbbox)
                    try:
                        cur = c.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        cur.execute(str(sql)) # if str() is not used 'where' is lost for some weird reason
                        rows = cur.fetchall()
                        self.logger.debug("      %s", cur.query)
                        self.logger.debug("      fetched %d elements", len(rows))
                        for row in rows:
                            geom = shapelyWkb.loads(bytes(row['geometry']))
                            if data['srid'] != 3857: # we support only 3857 and 4326 projections
                                geom = transform(wgs84_to_mercator, geom)
                            tags, mapping = data['mapper'](row)
                            extra_elements.append(Element(None, geom, tags, mapping))
                    except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
                        self.logger.exception("Query error: %s" % sql)
                    except shapely.errors.WKBReadingError as e:
                        self.logger.error("Geometry error: %s" % bytes(row['geometry']).hex())
                    finally:
                        cur.close()

            if self.multiprocessing:
                # wait for results, look for errors
                for r in results:
                    r.get()
                del pool
                del results

            # add meta data to elements
            if not self.interactive:
                self.logger.info("      adding meta data")
            with psycopg2.connect(configuration.DATA_DB_DSN) as c:
                sql = "SELECT network FROM osm_features_meta WHERE id = %s"
                for element in elements:
                    if element.id and element.mapping.get('check-meta', False):
                        try:
                            cur = c.cursor(cursor_factory=psycopg2.extras.DictCursor)
                            cur.execute(sql, (element.id,))
                            row = cur.fetchone()
                            if row:
                                element.tags['route:network'] = row['network']
                        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
                            self.logger.exception("Query error: %s" % sql)
                        finally:
                            cur.close()

            if self.interactive:
                self.proc_progress.close()
            else:
                self.logger.info("    finished processing elements")

            gc.collect()

            if extra_elements:
                self.logger.info("    added %d extra elements" % len(extra_elements))
                elements += extra_elements

            used = process.memory_info().rss // 1048576
            self.logger.info("    memory used: {:,}M out of {:,}M".format(used, total))

            m = total / used > 4 and len(extra_elements) < 500000
            if self.multiprocessing and not m:
                self.multiprocessing = False
                num_worker_threads = 1
                self.logger.info("    running in single threaded mode")

            if self.interactive:
                r = range(1, 8)
                num_tiles = 0
                for z in r:
                    n = 4 ** z
                    num_tiles = num_tiles + n
                self.gen_progress = tqdm(total=num_tiles, desc="Generated")

            if self.multiprocessing:
                tile_queue = multiprocessing.JoinableQueue()
                db_queue = multiprocessing.JoinableQueue()
            else:
                tile_queue = queue.Queue()
                db_queue = queue.Queue()

            db_thread = threading.Thread(target=self.dbWorker, args=(db_queue,))
            db_thread.start()

            processes = []
            if self.multiprocessing:
                for i in range(num_worker_threads):
                    p = multiprocessing.Process(target=self.tileWorker, args=(tile_queue, db_queue))
                    p.start()
                    processes.append(p)
            else:
                t = threading.Thread(target=self.tileWorker, args=(tile_queue, db_queue))
                t.start()
                processes.append(t)

            if self.basemap:
                tile = Tile(0, 0, 0, elements)
            else:
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

            if self.multiprocessing:
                tile_queue.close()
                db_queue.close()

            self.db.finish()

            if self.interactive:
                self.gen_progress.close()

            used = process.memory_info().rss // 1048576
            self.logger.info("    memory used: {:,}M out of {:,}M".format(used, total))

        elapsed_time = datetime.utcnow() - start_time
        elapsed_time = elapsed_time - timedelta(microseconds=elapsed_time.microseconds)
        self.logger.info("Finished map: %s in %s" % (map_path, elapsed_time))

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
        if (self.basemap and tile.zoom > 0) or tile.zoom > 7:
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
                    try:
                        building_parts_geom = cascaded_union(building_parts)
                        building_parts_prepared = prep(building_parts_geom)
                    except Exception as e:
                        self.logger.error("Failed to dissolve building parts in tile %s" % tile)
                        building_parts_geom = None

            for element in tile.elements:
                if element.mapping.get('zoom-min', 0) > tile.zoom:
                    continue
                geom = element.geom
                united = 'union' in element.mapping and tile.zoom <= element.mapping.get('union-zoom-max', 14) \
                         and geom.type in ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']
                if tile.zoom < 14:
                    if element.area:
                        if self.basemap and 'basemap-filter-area' in element.mapping:
                            area = (element.mapping.get('basemap-filter-area', 0) * (2 << (tile.zoom))) ** 2
                        else:
                            area = element.mapping.get('filter-area', 1)
                        if element.area < pixelArea * area:
                            continue
                    if 'buffer' in element.mapping:
                        geom = geom.buffer(tile.pixelWidth * element.mapping.get('buffer', 1))
                    if not united:
                        simple_geom = geom.simplify(tile.pixelWidth * element.mapping.get('simplify', 1))
                        if simple_geom.is_valid:
                            geom = simple_geom
                        if geom.type in ['LineString', 'MultiLineString']:
                            # todo: it's a quick hack, replace with bounding box analysis
                            if geom.length < tile.pixelWidth:
                                continue
                else:
                    if 'enlarge' in element.mapping:
                        geom = geom.buffer(tile.pixelWidth * element.mapping.get('enlarge', 1))
                    if 'building' in element.tags and not 'building:outline' in element.tags and not 'building:part' in element.tags:
                        #if building_parts_geom is None or not building_parts_prepared.intersects(element.geom) or building_parts_geom.intersection(element.geom).area == 0:
                        if building_parts_geom is None or not building_parts_prepared.covers(element.geom):
                            element.tags['building:part'] = element.tags['building']
                if united:
                    if type(element.mapping['union']) is dict:
                        pattern = [k for k, v in element.mapping['union'].items() if tile.zoom >= v]
                    else:
                        pattern = [x.strip() for x in element.mapping['union'].split(',')]
                    values = [element.tags[k] for k in sorted(set(pattern) & set(element.tags.keys()))]
                    key = hash(tuple(values))
                    if len(values):
                        element.geometry = geom
                        if geom.type in ['LineString', 'MultiLineString']:
                            merges[key].append(element)
                        else:
                            unions[key].append(element)
                        continue
                    else:
                        self.logger.warn("Empty union key for %s, pattern: %s" % (element.osm_id(), pattern))
                if tile.zoom < 14:
                    if 'transform' in element.mapping:
                        if element.mapping.get('transform') == 'filter-rings':
                            geom = filter_rings(geom, pixelArea)
                    if 'buffer' in element.mapping:
                        geom = geom.buffer(tile.pixelWidth * -element.mapping.get('buffer', 1))
                geometry = affine_transform(geom, tile.matrix)
                if geometry.is_empty:
                    continue
                labels = None
                if element.label:
                    if isinstance(element.label, list):
                        for label in element.label:
                            if prepared_clip.contains(label):
                                if labels is None:
                                    labels = []
                                labels.append(affine_transform(label, tile.matrix))
                    elif prepared_clip.contains(element.label):
                        labels = affine_transform(element.label, tile.matrix)
                features.append(Feature(element.id, geometry, element.tags, element.kind, labels,
                                        element.height, element.min_height, element.building_color, element.roof_color))

            #TODO combine union and merge to one logical block
            for union in unions:
                try:
                    first = unions[union][0]
                    # create united geometry
                    united_geom = cascaded_union([el.geometry for el in unions[union]])
                    # simplify after union
                    simple_geom = united_geom.simplify(tile.pixelWidth * first.mapping.get('simplify', 1))
                    if simple_geom.is_valid:
                        unitid_geom = simple_geom
                    if type(first.mapping['union']) is dict:
                        pattern = [k for k, v in first.mapping['union'].items() if tile.zoom >= v]
                    else:
                        pattern = [x.strip() for x in first.mapping['union'].split(',')]
                    # get united tags
                    united_tags = {k: v for k, v in first.tags.items() if k in pattern}
                    if len(united_tags) == 0:
                        self.logger.error("Empty tags")
                        for el in unions[union]:
                            self.logger.error(str(el))
                    # transform geometry
                    if tile.zoom < 14:
                        if 'transform' in first.mapping:
                            if first.mapping.get('transform') == 'filter-rings':
                                united_geom = filter_rings(united_geom, pixelArea)
                        if 'buffer' in first.mapping:
                            united_geom = united_geom.buffer(tile.pixelWidth * -first.mapping.get('buffer', 1))
                    geometry = affine_transform(united_geom, tile.matrix)
                    if not geometry.is_empty:
                        features.append(Feature(None, geometry, united_tags, None, None, None, None, None, None))
                except Exception as e:
                    self.logger.error("Failed to process union %s in tile %s" % (first.mapping['union'], tile))

            for merge in merges:
                first = merges[merge][0]
                try:
                    # create united geometry
                    lines = []
                    for el in merges[merge]:
                        if el.geometry.type == 'LineString':
                            lines.append(el.geometry)
                        else:
                            lines.extend(el.geometry.geoms)
                    united_geom = linemerge(lines)
                    # simplify after merge
                    united_geom = united_geom.simplify(tile.pixelWidth)
                    # remove too short segments
                    if united_geom.type == 'MultiLineString':
                        united_geom = MultiLineString([line for line in united_geom.geoms if line.length > tile.pixelWidth])
                    if united_geom.is_empty:
                        continue
                    if type(first.mapping['union']) is dict:
                        pattern = [k for k, v in first.mapping['union'].items() if tile.zoom >= v]
                    else:
                        pattern = [x.strip() for x in first.mapping['union'].split(',')]
                    # get united tags
                    united_tags = {k: v for k, v in first.tags.items() if k in pattern}
                    if 'id' in first.tags:
                        united_tags['id'] = first.tags['id']
                    geometry = affine_transform(united_geom, tile.matrix)
                    if not geometry.is_empty:
                        features.append(Feature(None, geometry, united_tags, None, None, None, None, None, None))
                except Exception as e:
                    self.logger.error("Failed to process merge %s in tile %s" % (first.mapping['union'], tile))

            encoded = encode(features, mappings.tags)
            self.dbQueue.put(DBJob(tile.zoom, tile.x, tile.y, encoded))

        # propagate elements to lower zoom
        if (not self.basemap and tile.zoom < 14) or tile.zoom < 7:
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
            if element.mapping.get('zoom-max', 14) < zoom:
                continue
            if prepared_clip.covers(element.geom):
                subtile.elements.append(element)
            elif prepared_clip.intersects(element.geom):
                try:
                    subtile.elements.append(element.clone(clipCache[element.mapping.get('clip-buffer', 4)].intersection(element.geom)))
                except Exception as e:
                    self.logger.exception("Error clipping element for tile %s" % subtile)
                    self.logger.error("Element was: %s" % element)
        self.tileQueue.put(subtile)


    def generateIntermediateFile(self, source_pbf_path, x, y, z, name):
        ax = x >> (7 - z)
        ay = y >> (7 - z)
        target_pbf_path = self.pbf_path(ax, ay, z)
        if not os.path.exists(target_pbf_path) or os.path.getmtime(target_pbf_path) < self.timestamp:
            self.logger.info("  Creating%s intermediate file: %s" % (name, target_pbf_path))
            pbf_dir = os.path.dirname(target_pbf_path)
            if not os.path.exists(pbf_dir):
                os.makedirs(pbf_dir)
            if os.path.exists(target_pbf_path):
                os.remove(target_pbf_path)
            bbox = mercantile.bounds(ax, ay, z)
            osmconvert_call = [configuration.OSMCONVERT_PATH, source_pbf_path]
            osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (bbox.west,bbox.south,bbox.east,bbox.north)]
            osmconvert_call += ['--complete-ways', '--complete-multipolygons', '--complete-boundaries', '-o=%s' % target_pbf_path]
            self.logger.debug("    calling: %s", " ".join(osmconvert_call))
            if not self.dry_run:
                subprocess.check_call(osmconvert_call)
            else:
                subprocess.check_call(['touch', target_pbf_path])
        return target_pbf_path


    def map_path_base(self, x, y, zoom=7):
        """
        returns path to map file but without extension
        """
        if self.basemap:
            if not self.dry_run and not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir)
            if self.stubmap:
                name = 'stubmap'
            else:
                name = 'basemap'
            return os.path.join(self.data_dir, name)
        else:
            output_dir = os.path.join(self.data_dir, str(zoom), str(x))
            if not self.dry_run and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            return os.path.join(output_dir, '%d-%d' % (x, y))

    def pbf_path(self, x, y, zoom=7):
        """
        returns path to intermediate osm file
        """
        if self.basemap:
            return self.map_path_base(x, y, zoom) + ".o5m"
        else:
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
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    parser.add_argument('-n', '--noninteractive', action='store_true', help='forbid interactive mode')
    parser.add_argument('-i', '--intermediate', action='store_true', help='create intermediate osm.pbf file')
    parser.add_argument('-k', '--keep', action='store_true', help='do not remove intermediate osm.pbf file on success')
    parser.add_argument('-f', '--from-file', action='store_true', help='use file instead of database as data source')
    parser.add_argument('x', type=int, help='tile X')
    parser.add_argument('y', type=int, help='tile Y')
    args = parser.parse_args()

    if not args.from_file:
        print("Database source is currently not supported")
        exit(1)

    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        print("Invalid log level: %s" % args.log)
        exit(1)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s - %(message)s')
    logging.getLogger("shapely").setLevel(logging.ERROR)
    logger = logging.getLogger(__name__)
    # during a dry run the console should receive all logs
    if args.dry_run:
        logger.setLevel(logging.DEBUG)

    try:
        mapWriter = MapWriter(args.data_path, args.dry_run, args.noninteractive)
        mapWriter.createMap(args.x, args.y, args.intermediate, args.keep, args.from_file)
    except Exception as e:
        logger.exception("An error occurred:")
