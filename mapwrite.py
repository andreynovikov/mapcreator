#!/usr/bin/env python3
import os
import sys
import gc
import math
import time
import queue
import threading
import multiprocessing
import argparse
import subprocess
import logging.config
import psutil
import setproctitle
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from tqdm import tqdm

import psycopg2
import psycopg2.extras
import osmium
import mercantile
import shapely.wkb as shapely_wkb
from shapely.geometry import MultiLineString, Polygon
from shapely.prepared import prep
from shapely.ops import transform, linemerge, cascaded_union
from shapely.affinity import affine_transform
from shapely.errors import WKBReadingError

import configuration
import mappings
from encoder import encode
from util.core import Element
from util.database import MTilesDatabase
from util.geometry import wgs84_to_mercator, clockwise, polylabel
from util.osm import is_area
from util.osm.kind import is_place, is_building, get_kind_and_type
from util.osm.buildings import get_building_properties
from util.filters import filter_rings


logging.getLogger('shapely.geos').setLevel(logging.WARNING)

ProcessJob = namedtuple('ProcessJob', ['id', 'wkb', 'tags', 'mapping', 'simple_polygon'])
DBJob = namedtuple('DBJob', ['zoom', 'x', 'y', 'features'])
Feature = namedtuple('Feature', ['id', 'geometry', 'area', 'tags', 'kind', 'type', 'label', 'building'])

wkbFactory = osmium.geom.WKBFactory()


def deep_get(dictionary, *keys):
    for key in keys:
        if isinstance(dictionary, dict):
            dictionary = dictionary.get(key, {})
        else:
            return {}
    return dictionary


class OsmFilter:
    def __init__(self, elements, basemap, logger):
        self.elements = elements
        self.processors = set()
        self.logger = logger
        self.basemap = basemap
        self.ignorable = 0

    def tag_iterator(self, tags):
        return tags.items()

    def filter(self, tags):
        filtered_tags = {}
        mapping = {}
        renderable = False
        ignorable = True
        modifiers = set()
        for key, value in self.tag_iterator(tags):
            key = key.strip().lower()
            if key in mappings.tags:
                m = mappings.tags[key].get('__any__', None)
                if m is None:
                    m = mappings.tags[key].get(value, None)
                if m is not None:  # empty dictionaries should be also accounted
                    if 'rewrite-key' in m or 'rewrite-value' in m:
                        key = m.get('rewrite-key', key)
                        if m.get('rewrite-if-missing', False) and filtered_tags.get(key, None):
                            continue
                        value = m.get('rewrite-value', value)
                        if 'add-tags' in m and 'rewrite-key' in m:  # preserve original setting
                            add = mapping.get('add-tags', {})
                            mapping['add-tags'] = {**add, **m['add-tags']}
                        if 'keep-for' in m and 'rewrite-key' in m:  # preserve original setting
                            keep = mapping.get('keep-for', {})
                            keep[key] = m['keep-for']
                            mapping['keep-for'] = keep
                        if 'zoom-min' in m:  # account original setting
                            if 'zoom-min' not in mapping or m['zoom-min'] < mapping['zoom-min']:
                                mapping['zoom-min'] = m['zoom-min']
                        render = m.get('render', False)  # account original render flag if it is explicitly set
                        renderable = renderable or render
                        m = mappings.tags[key].get(value, mappings.tags[key].get('__any__', {}))
                    if 'one-of' in m:
                        if value not in m['one-of']:
                            continue
                    if 'adjust' in m:
                        value = m['adjust'](value)
                    if value is None:
                        if key in mapping.get('keep-for', {}):
                            del mapping['keep-for'][key]
                        continue
                    if isinstance(value, str) and key not in ('name', 'name:en', 'name:de', 'name:ru',
                                                              'ref', 'icao', 'iata', 'addr:housenumber',
                                                              'opening_hours', 'wikipedia', 'website'):
                        value = value.strip().lower()
                        if ';' in value:
                            value = value.split(';')[0]
                    filtered_tags[key] = value
                    render = m.get('render', True)
                    renderable = renderable or render
                    ignorable = ignorable and (m.get('ignore', not render))
                    if 'keep-for' in m:
                        keep = mapping.get('keep-for', {})
                        keep[key] = m['keep-for']
                        mapping['keep-for'] = keep
                    for k in ('filter-area', 'buffer', 'enlarge', 'simplify', 'force-line', 'label',
                              'filter-type', 'clip-buffer', 'keep-tags', 'basemap-label',
                              'basemap-keep-tags', 'basemap-filter-area'):
                        if k in m:
                            mapping[k] = m[k]
                    if 'union' in m:
                        if 'union' in mapping:
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
                    transform_exclusive = m.get('transform-exclusive', False)
                    if 'transform' in m:
                        # apply exclusive transform only if this is the first match
                        if not transform_exclusive or mapping.get('transform-exclusive', None) is None:
                            mapping['transform'] = m['transform']
                        elif transform_exclusive:
                            transform_exclusive = False
                    if render:
                        if mapping.get('transform-exclusive', False):
                            # if there was previous exclusive transform remove it
                            if 'transform' not in m or transform_exclusive:
                                del mapping['transform']
                        mapping['transform-exclusive'] = transform_exclusive
                    # if 'check-meta' in m:
                    #     mapping['check-meta'] = m['check-meta'] or mapping.get('check-meta', False)
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
            if 'add-tags' in mapping:
                for k, v in mapping['add-tags'].items():
                    filtered_tags[k] = v
            if 'keep-for' in mapping:
                for k, v in mapping['keep-for'].items():
                    keep = [x.strip() for x in v.split(',')]
                    if not set(keep) & set(filtered_tags.keys()):
                        del filtered_tags[k]
            tag_filter = None
            if self.basemap and 'basemap-keep-tags' in mapping:
                tag_filter = mapping['basemap-keep-tags']
            elif 'keep-tags' in mapping:
                tag_filter = mapping['keep-tags']
            if tag_filter:
                # noinspection PyUnresolvedReferences
                keep = [x.strip() for x in tag_filter.split(',')]
                filtered_tags = {k: filtered_tags[k] for k in set(keep) & set(filtered_tags.keys())}
            if ignorable:
                self.ignorable += 1
        return renderable, filtered_tags, mapping

    def get_osm_id(self, t, o):
        return abs(o.id)

    def get_osm_ref(self, t, o):
        if t == 1:
            st = 'node'
        elif t == 2 or self.from_way(o):
            st = 'way'
        else:
            st = 'relation'
        osm_id = self.get_osm_id(t, o)
        return '{}/{}'.format(st, osm_id)

    def skip(self, t, o, tags):
        return False

    def wkb(self, t, o):
        return o.wkb

    def simplify(self, t, o, geom):
        if geom.geom_type == 'MultiPolygon' and len(geom.geoms) == 1:
            return geom[0]
        return geom

    def validate(self, t, o, geom):
        return geom

    def from_way(self, o):
        return o.id > 0

    def process(self, srid, t, o):
        if len(o.tags) == 0:
            return
        if o.names:
            for k, v in o.names.items():
                o.tags['name:{}'.format(k) if k else 'name'] = v
        renderable, tags, mapping = self.filter(o.tags)
        if renderable:
            if self.skip(t, o, tags):
                return
            try:
                geom = shapely_wkb.loads(self.wkb(t, o), hex=True)
                if srid != 3857:  # we support only 3857 and 4326 projections
                    geom = transform(wgs84_to_mercator, geom)
                geom = self.simplify(t, o, geom)
                if mapping.pop('force-line', False) and geom.type in ['Polygon', 'MultiPolygon']:
                    geom = geom.boundary
                if 'filter-type' in mapping and geom.type not in mapping.pop('filter-type', []):
                    return
                geom = clockwise(geom)
                geom = self.validate(t, o, geom)
                # construct unique id
                if t == 3 and self.from_way(o):
                    t = 2
                osm_id = self.get_osm_id(t, o)
                el_id = (osm_id << 2) + t
                self.elements.append(Element(el_id, geom, tags, mapping))
            except Exception as ex:
                ref = self.get_osm_ref(t, o)
                self.logger.error("   %s: %s", ref, ex)

    def finish(self):
        if self.ignorable:
            if len(self.elements) <= self.ignorable:  # it can be less as closed ways from file are processed twice
                self.elements.clear()
                self.logger.debug("    all elements are ignored")
                return
        return self.processors


class OsmFileFilter(osmium.SimpleHandler, OsmFilter):
    def __init__(self, elements, basemap, logger):
        osmium.SimpleHandler.__init__(self)
        OsmFilter.__init__(self, elements, basemap, logger)
        self.outlines = set()

    def tag_iterator(self, tags):
        for tag in tags:
            yield tag.k, tag.v

    def get_osm_id(self, t, o):
        if t == 3:
            return o.orig_id()
        else:
            return o.id

    def skip(self, t, o, tags):
        if t > 1:
            area = is_area(tags)
            if t == 2 and o.is_closed() and area:
                return True  # will get it later in area handler
            if t == 3 and o.from_way() and not area:
                return True  # have added it already in ways handler
        return False

    def wkb(self, t, o):
        if t == 1:
            return wkbFactory.create_point(o)
        elif t == 2:
            return wkbFactory.create_linestring(o)
        elif t == 3:
            return wkbFactory.create_multipolygon(o)
        else:  # can not happen but is required by lint
            return None

    def simplify(self, t, o, geom):
        if t == 3 and not o.is_multipolygon():
            return geom[0]  # simplify geometry
        else:
            return geom

    def validate(self, t, o, geom):
        if not geom.is_valid:
            geom = geom.buffer(0)
            ref = self.get_osm_ref(t, o)
            if geom.is_valid:
                logging.warning(" invalid geom %s fixed", ref)
            else:
                logging.warning(" invalid geom %s NOT fixed", ref)
        return geom

    def from_way(self, o):
        return o.from_way()

    def node(self, n):
        self.process(4326, 1, n)

    def way(self, w):
        self.process(4326, 2, w)

    def area(self, a):
        self.process(4326, 3, a)

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
        result = super(OsmFileFilter, self).finish()
        if result and self.outlines:
            found = 0
            for element in self.elements:
                if element.id in self.outlines:
                    found = found + 1
                    element.tags['building:outline'] = 1
            self.logger.debug("    outlined %d of %d buildings" % (found, len(self.outlines)))
        return result


class Tile:
    RADIUS = 6378137  # this R is calculated from circumference defined in org.oscim.core.MercatorProjection
    CIRCUMFERENCE = 2 * math.pi * RADIUS
    SIZE = 512
    SCALE = 4096
    INITIAL_RESOLUTION = CIRCUMFERENCE / SIZE

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
        ll = mercantile.lnglat((self.bounds.right + self.bounds.left) / 2, (self.bounds.top + self.bounds.bottom) / 2, False)
        self.groundScale = math.cos(ll.lat * (math.pi / 180)) * self.pixelWidth

    def __str__(self):
        return "%d/%d/%d" % (self.zoom, self.x, self.y)


class BBoxCache(defaultdict):
    def __init__(self, tile):
        super().__init__()
        self.tile = tile

    def __missing__(self, key):
        if key == 0:
            bbox = self.tile.bbox
        else:
            bbox = self.tile.bbox.buffer(self.tile.pixelWidth * key)
        self[key] = bbox
        return bbox


def element_processing_initializer(proc_name):
    name = "{} element processor {}".format(proc_name, multiprocessing.current_process().name.split('-')[1])
    multiprocessing.current_process().name = name
    setproctitle.setproctitle(name)


def process_element(geom, tags, mapping, basemap=False):
    kind, el_type = get_kind_and_type(tags)
    if is_building(kind):
        building = get_building_properties(tags)
    else:
        building = None

    area = None
    label = None

    if el_type or (mapping.get('label', False) and (not basemap or mapping.get('basemap-label', False))):
        if building is not None:
            label, area = polylabel(geom)
        else:
            if geom.type in ('Polygon', 'MultiPolygon'):
                area = geom.area
                label = geom.centroid
                if not geom.contains(label):
                    label = geom.representative_point()

    if area is None and 'transform' in mapping and mapping.get('transform') == 'point':
        area = geom.area

    if area is None and (mapping.get('filter-area', None) or (basemap and mapping.get('basemap-filter-area', None))):
        area = geom.area

    if area:
        # convert area to true meters
        if label:
            point = label
        else:
            point = geom.representative_point()
        if isinstance(point, list):
            point = point[0]
        # https://en.wikipedia.org/wiki/Mercator_projection#Area_scale
        k = math.cosh(point.y / Tile.RADIUS)
        area = area / math.pow(k, 2)

    return kind, el_type, area, label, building


# noinspection PyPep8Naming
class MapWriter:
    def __init__(self, data_dir, dry_run=False, forbid_interactive=False, single_thread=False):
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.interactive = not forbid_interactive and sys.__stdin__.isatty()
        self.stubmap = False
        self.basemap = False
        self.timestamp = None
        self.db = None
        self.tile_queue = None
        self.db_queue = None
        self.proc_name = "mapwrite"
        if single_thread:
            self.worker_threads = 1
        else:
            self.worker_threads = 6  # hardcoded maximum, can be any positive value
        self.proc_progress = None
        self.gen_progress = None

        try:
            # Enable C-based speedups available from 1.2.10+
            from shapely import speedups
            if speedups.available:
                self.logger.debug("Enabling Shapely speedups")
                speedups.enable()
        except ImportError:
            self.logger.warning("Upgrade Shapely for performance improvements")

    def createMap(self, x, y, timeout=0, intermediate=False, keep=False, from_file=False, bbox_override=None):
        self.stubmap = x == -2 and y == -2
        self.basemap = self.stubmap or (x == -1 and y == -1)

        if self.stubmap:
            mappings.mapType = mappings.MapTypes.Stub
            self.proc_name = "mapwrite stub"
        elif self.basemap:
            mappings.mapType = mappings.MapTypes.Base
            self.proc_name = "mapwrite base"
        else:
            self.proc_name = "mapwrite {} {}".format(x, y)
        setproctitle.setproctitle(self.proc_name)

        log_path = self.log_path(x, y)
        log_file_handler = logging.FileHandler(log_path)
        log_file_handler.setFormatter(logging.getLogger().handlers[0].formatter)
        logging.getLogger().addHandler(log_file_handler)

        map_path = self.map_path(x, y)
        self.logger.info("Creating map: %s" % map_path)

        if from_file:
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

        start_time = datetime.utcnow()

        elements = []
        if from_file:
            # noinspection PyUnboundLocalVariable
            self.logger.info("  Processing file: %s" % pbf_path)
            handler = OsmFileFilter(elements, self.basemap, self.logger)
            handler.apply_file(pbf_path)
            processors = handler.finish()
            del handler
        else:
            self.logger.info("  Processing elements from database")
            handler = OsmFilter(elements, self.basemap, self.logger)
            with psycopg2.connect(configuration.DATA_DB_DSN, cursor_factory=psycopg2.extras.NamedTupleCursor) as c:
                psycopg2.extras.register_hstore(c)
                with c.cursor() as cur:
                    cur.execute("SELECT extract(epoch from importdate) FROM osm_replication_status")
                    self.logger.debug(cur.query)
                    if cur.rowcount > 0:
                        self.timestamp = cur.fetchone()[0]
                    else:
                        raise RuntimeError("Database has no replication data")
                if self.stubmap:
                    queries = mappings.stubmap_queries
                elif self.basemap:
                    queries = mappings.basemap_queries
                else:
                    queries = mappings.queries
                    if bbox_override:
                        bbox = "ST_MakeEnvelope({}, {}, {}, {}, 3857)".format(*bbox_override.split(','))
                    else:
                        bounds = mercantile.xy_bounds(x, y, 7)
                        expand = 1.194 * 4
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
                        sql = data['query']
                    else:
                        if data['srid'] != 3857:
                            qbbox = "ST_Transform({bbox}, {srid})".format(bbox=bbox, srid=data['srid'])
                        else:
                            qbbox = bbox
                        sql = "{query} WHERE ST_Intersects(geom, {bbox})" \
                            .format(query=data['query'], bbox=qbbox)
                    with c.cursor('large') as cur:
                        try:
                            n = 0
                            cur.itersize = 1000
                            cur.execute(sql)
                            self.logger.debug("   %s", cur.query.decode())
                            for row in cur:
                                handler.process(data['srid'], data['type'], row)
                                n += 1
                            self.logger.debug("   fetched %d elements", n)
                        except (psycopg2.ProgrammingError, psycopg2.InternalError):
                            self.logger.exception("Query error: %s" % sql)
            processors = handler.finish()
            del handler

        gc.collect()

        process = psutil.Process(os.getpid())
        used = process.memory_info().rss // 1048576
        available = psutil.virtual_memory().available // 1048576 + used
        self.worker_threads = max(1, min(self.worker_threads, int(available / used / 2), len(os.sched_getaffinity(0))))
        self.logger.info("    memory used: {:,}M out of {:,}M".format(used, available))

        # process map only if it contains relevant data
        has_elements = bool(elements)
        if has_elements:
            self.timestamp = int(self.timestamp / 3600 / 24)

            for processor in processors:
                self.logger.info("    calling pre-processor %s.%s" % (processor.__module__, processor.__name__))
                processor(elements, self.interactive)

            self.db = MTilesDatabase(map_path)
            if self.basemap:
                self.db.create("basemap", 'baselayer', self.timestamp, 'maptrek')
            else:
                self.db.create("%d-%d" % (x, y), 'baselayer', self.timestamp, 'maptrek')

            used = process.memory_info().rss // 1048576
            available = psutil.virtual_memory().available // 1048576 + used
            self.worker_threads = min(self.worker_threads, max(1, int(available / used / 2)))
            self.logger.info("    memory used: {:,}M out of {:,}M".format(used, available))

            if self.basemap and not self.stubmap:
                # temporary hack
                self.worker_threads = min(2, self.worker_threads)
            if self.worker_threads > 1:
                self.logger.info("    running in multiprocessing mode with %d workers" % self.worker_threads)
            else:
                self.logger.info("    running in single threaded mode")

            pool = None
            if self.worker_threads > 1 and len(elements) > 100:
                pool = multiprocessing.Pool(self.worker_threads, initializer=element_processing_initializer, initargs=(self.proc_name,))

            if self.interactive:
                self.proc_progress = tqdm(total=len(elements), desc="Processed", maxinterval=1.0)
            else:
                self.logger.info("    processing %d elements" % len(elements))

            results = []
            places = defaultdict(list)
            # pre-process elements
            for idx, element in enumerate(elements):
                def process_result(result, index=idx):
                    el = elements[index]
                    el.kind, el.type, el.area, el.label, el.building = result
                    # remove overlapping places (point and polygon)
                    # we assume that points go first, if not - introduce sort
                    if el.id and is_place(el.kind):
                        if el.geom.type == 'Point':
                            key = '{}@{}'.format(el.tags.get('place', '---'), el.tags.get('name', '---').split(' (')[0])
                            places[key].append(el)
                        elif len(places):
                            key = '{}@{}'.format(el.tags.get('place', '==='), el.tags.get('name', '===').split(' (')[0])
                            for place in places[key]:
                                if el.geom.contains(place.geom):
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
                                    el.tags.pop('place', None)
                                    el.merged = True
                                    break

                    if 'transform' in el.mapping:
                        if el.mapping.get('transform') == 'point' and el.geom.type != 'Point':
                            if el.label:
                                if isinstance(el.label, list):
                                    el.geom = el.label[0]
                                else:
                                    el.geom = el.label
                            else:
                                el.geom = el.geom.representative_point()

                    # if feature has type or name save it for future reference
                    if el.type or 'name' in el.tags:
                        self.db.putFeature(el.id, el.tags, el.kind, el.type, el.label, el.geom)
                        el.tags.pop('name:en', None)
                        el.tags.pop('name:de', None)
                        el.tags.pop('name:ru', None)
                        el.tags.pop('opening_hours', None)
                        el.tags.pop('website', None)
                        el.tags.pop('phone', None)
                        el.tags.pop('wikipedia', None)
                        el.tags['id'] = el.id
                    if self.interactive:
                        self.proc_progress.update()
                if element.geom.is_empty:
                    self.logger.error("   got empty geom for %s" % element.osm_id())
                    element.tags.clear()  # clean all tags to later remove element
                    continue
                if pool:
                    results.append(pool.apply_async(
                        process_element, [element.geom, element.tags, element.mapping, self.basemap],
                        callback=process_result
                    ))
                else:
                    process_result(process_element(element.geom, element.tags, element.mapping, self.basemap))
            if pool:
                pool.close()

            extra_elements = []
            # get supplementary data while elements are processed
            with psycopg2.connect(configuration.DATA_DB_DSN) as c:
                if self.stubmap:
                    queries = mappings.stubmap_supplementary_queries
                elif self.basemap:
                    queries = mappings.basemap_supplementary_queries
                else:
                    queries = mappings.supplementary_queries
                    if bbox_override:
                        bbox = "ST_MakeEnvelope({}, {}, {}, {}, 3857)".format(*bbox_override.split(','))
                    else:
                        bounds = mercantile.xy_bounds(x, y, 7)
                        expand = 1.194 * 4
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
                    # encapsulate query as it can contain its own WHERE clause
                    if self.basemap:
                        sql = "SELECT * FROM ({query}) AS data".format(query=data['query'])
                    else:
                        if data['srid'] != 3857:
                            qbbox = "ST_Transform({bbox}, {srid})".format(bbox=bbox, srid=data['srid'])
                        else:
                            qbbox = bbox
                        sql = "SELECT * FROM ({query}) AS data WHERE ST_Intersects(geom, {bbox})".format(query=data['query'], bbox=qbbox)
                    try:
                        cur = c.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        cur.execute(sql)
                        self.logger.debug("     %s", cur.query.decode())
                        rows = cur.fetchall()
                        self.logger.debug("     fetched %d elements", len(rows))
                        for row in rows:
                            geom = shapely_wkb.loads(row['geom'], hex=True)
                            if data['srid'] != 3857:  # we support only 3857 and 4326 projections
                                geom = transform(wgs84_to_mercator, geom)
                            kind, tags, mapping = data['mapper'](row)
                            if mapping.pop('force-line', False) and geom.type in ['Polygon', 'MultiPolygon']:
                                geom = geom.boundary
                            element = Element(None, geom, tags, mapping)
                            if kind:
                                element.kind = kind
                            extra_elements.append(element)
                    except (psycopg2.ProgrammingError, psycopg2.InternalError):
                        self.logger.exception("Query error: %s" % sql)
                    except WKBReadingError:
                        self.logger.error("Geometry error: %s" % row['geom'])
                    finally:
                        cur.close()

            if self.worker_threads > 1:
                # wait for results, look for errors
                for r in results:
                    r.get()
                del pool
                del results

            if self.interactive:
                self.proc_progress.close()
            else:
                self.logger.info("    finished processing elements")

            # remove elements without tags (due to tag cleaning) and without renderable tags (due to place merging)
            def has_tags(el):
                if el.merged:
                    for k, v in el.tags.items():
                        if k == 'id':
                            continue
                        em = mappings.tags[k].get('__any__', None)
                        if em is None:
                            em = mappings.tags[k].get(v, None)
                        if em.get('render', True):
                            return True
                    self.logger.debug("   stripped %s" % el.osm_id())
                    return False
                elif len(el.tags):
                    return True
                else:
                    self.logger.warning(" missing tags in %s" % el.osm_id())
                    return False

            elements[:] = [el for el in elements if has_tags(el)]

            gc.collect()

            if extra_elements:
                self.logger.info("    added %d extra elements" % len(extra_elements))
                elements += extra_elements

            used = process.memory_info().rss // 1048576
            available = psutil.virtual_memory().available // 1048576 + used
            self.worker_threads = min(self.worker_threads, max(1, int(available / used / 2)))
            self.logger.info("    memory used: {:,}M out of {:,}M".format(used, available))

            if len(extra_elements) > 500000:
                self.worker_threads = 1
            if self.worker_threads > 1:
                self.logger.info("    running in multiprocessing mode with %d workers" % self.worker_threads)
            else:
                self.logger.info("    running in single threaded mode")

            if self.interactive:
                r = range(1, 8)
                num_tiles = 0
                for z in r:
                    n = 4 ** z
                    num_tiles = num_tiles + n
                self.gen_progress = tqdm(total=num_tiles, desc="Generated")

            if self.worker_threads > 1:
                tile_queue = multiprocessing.JoinableQueue()
                db_queue = multiprocessing.JoinableQueue()
            else:
                tile_queue = queue.Queue()
                db_queue = queue.Queue()

            db_thread = threading.Thread(target=self.dbWorker, args=(db_queue,), name="{} db worker".format(self.proc_name))
            db_thread.start()

            processes = []
            if self.worker_threads > 1:
                for i in range(self.worker_threads):
                    p = multiprocessing.Process(target=self.tileWorker, args=(tile_queue, db_queue, True), name="{} tile worker {}".format(self.proc_name, i + 1))
                    p.start()
                    processes.append(p)
            else:
                t = threading.Thread(target=self.tileWorker, args=(tile_queue, db_queue), name="{} tile worker".format(self.proc_name))
                t.start()
                processes.append(t)

            if self.basemap:
                tile = Tile(0, 0, 0, elements)
            else:
                tile = Tile(7, x, y, elements)
            tile_queue.put(tile)

            self.db.commit()

            if timeout:
                time.sleep(5)  # give tile queue time to settle
                start = time.time()
                while time.time() - start <= timeout:
                    if tile_queue.empty():
                        # block until all tasks are done
                        tile_queue.join()
                        # stop workers
                        for i in range(self.worker_threads):
                            tile_queue.put(None)
                        for p in processes:
                            p.join()
                        timeout = 0
                        break
                    else:
                        time.sleep(1)  # just to avoid hogging the CPU
                else:
                    self.logger.error("   timed out, killing all processes")
                    for p in processes:
                        if p.is_alive():
                            if isinstance(p, multiprocessing.Process):
                                p.terminate()
                            else:
                                tile_queue.put(None)
                        p.join()
                    if self.worker_threads > 1:
                        tile_queue.close()
                        tile_queue.join_thread()
                    while db_queue.qsize() > 0:
                        db_queue.get_nowait()
            else:
                # block until all tasks are done
                tile_queue.join()
                # stop workers
                for i in range(self.worker_threads):
                    tile_queue.put(None)
                for p in processes:
                    p.join()

            # block until all tasks are done
            db_queue.join()
            db_queue.put(None)
            db_thread.join()

            if self.worker_threads > 1:
                tile_queue.close()
                db_queue.close()

            self.db.finish()

            if self.interactive:
                self.gen_progress.close()

            used = process.memory_info().rss // 1048576
            available = psutil.virtual_memory().available // 1048576 + used
            self.logger.info("    memory used: {:,}M out of {:,}M".format(used, available))

        elapsed_time = datetime.utcnow() - start_time
        elapsed_time = elapsed_time - timedelta(microseconds=elapsed_time.microseconds)
        if has_elements and timeout:
            raise Exception("Timed out map: %s in %s (timeout was %s)" % (map_path, elapsed_time, timedelta(seconds=timeout)))
        else:
            self.logger.info("Finished map: %s in %s" % (map_path, elapsed_time))

        if not self.dry_run and has_elements:
            if os.path.getsize(map_path) == 0:
                raise Exception("Resulting map file size for %s is zero, keeping old map file" % map_path)

        if self.db and not self.db.isValid():
            raise Exception("There was an error generating map %s, keeping old map file" % map_path)

        logging.getLogger().removeHandler(log_file_handler)

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

    def dbWorker(self, db_queue):
        while True:
            job = db_queue.get()
            if job is None:
                db_queue.task_done()
                break
            self.db.putTile(job.zoom, job.x, job.y, job.features)
            db_queue.task_done()
            if self.interactive:
                self.gen_progress.update()

    def tileWorker(self, tile_queue, db_queue, process=False):
        if process:
            setproctitle.setproctitle(multiprocessing.current_process().name)
        self.tile_queue = tile_queue
        self.db_queue = db_queue
        while True:
            tile = tile_queue.get()
            if tile is None:
                tile_queue.task_done()
                break
            # noinspection PyBroadException
            try:
                self.generateTile(tile)
            except Exception:
                self.logger.exception("Error generating tile %s" % tile)
            tile_queue.task_done()

    def generateTile(self, tile):
        if (self.basemap and tile.zoom > 0) or tile.zoom > 7:
            if len(tile.elements) > 0:
                self.logger.debug("    generating tile %s with %d elements" % (tile, len(tile.elements)))

            unions = defaultdict(list)
            merges = defaultdict(list)
            features = []
            tile_pixel_area = tile.pixelWidth * tile.pixelWidth
            tile_ground_square_scale = tile.groundScale ** 2
            prepared_clip = prep(tile.bbox)

            building_parts_geom = None
            building_parts_prepared = None
            if tile.zoom == 14:
                building_parts = [element.geom for element in tile.elements if 'building:part' in element.tags and 'building' not in element.tags]
                if building_parts:
                    # noinspection PyBroadException
                    try:
                        building_parts_geom = cascaded_union(building_parts)
                        building_parts_prepared = prep(building_parts_geom)
                    except Exception:
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
                        pixel_area = element.area / tile_ground_square_scale
                        if self.basemap and 'basemap-filter-area' in element.mapping:
                            area = (element.mapping.get('basemap-filter-area', 0) * (2 << tile.zoom)) ** 2
                        else:
                            area = element.mapping.get('filter-area', 1)
                        if pixel_area < area:
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
                    if 'building' in element.tags and 'building:outline' not in element.tags and 'building:part' not in element.tags:
                        # if building_parts_geom is None or not building_parts_prepared.intersects(element.geom) or building_parts_geom.intersection(element.geom).area == 0:
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
                        self.logger.warning("Empty union key for %s, pattern: %s" % (element.osm_id(), pattern))
                if tile.zoom < 14:
                    if 'transform' in element.mapping:
                        if element.mapping.get('transform') == 'filter-rings':
                            geom = filter_rings(geom, tile_pixel_area)
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
                features.append(Feature(element.id, geometry, element.area, element.tags, element.kind, element.type, labels, element.building))

            # TODO combine union and merge to one logical block
            for union in unions:
                first = unions[union][0]
                # noinspection PyBroadException
                try:
                    # create united geometry
                    united_geom = cascaded_union([el.geometry for el in unions[union]])
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
                                united_geom = filter_rings(united_geom, tile_pixel_area)
                        if 'buffer' in first.mapping:
                            united_geom = united_geom.buffer(tile.pixelWidth * -first.mapping.get('buffer', 1))
                        # simplify after union
                        simple_geom = united_geom.simplify(tile.pixelWidth * first.mapping.get('simplify', 1))
                        if simple_geom.is_valid:
                            united_geom = simple_geom
                    geometry = affine_transform(united_geom, tile.matrix)
                    if not geometry.is_empty:
                        features.append(Feature(None, geometry, None, united_tags, None, None, None, None))
                except Exception:
                    self.logger.error("Failed to process union %s in tile %s" % (first.mapping['union'], tile))

            for merge in merges:
                first = merges[merge][0]
                # noinspection PyBroadException
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
                        features.append(Feature(None, geometry, None, united_tags, None, None, None, None))
                except Exception:
                    self.logger.error("Failed to process merge %s in tile %s" % (first.mapping['union'], tile))

            encoded = encode(features, mappings.tags)
            self.db_queue.put(DBJob(tile.zoom, tile.x, tile.y, encoded))

        # propagate elements to lower zoom
        if (not self.basemap and tile.zoom < 14) or tile.zoom < 7:
            nx = tile.x << 1
            ny = tile.y << 1
            nz = tile.zoom + 1
            self.generateSubtiles(nx, ny, nz, tile)
            self.generateSubtiles(nx, ny + 1, nz, tile)
            self.generateSubtiles(nx + 1, ny, nz, tile)
            self.generateSubtiles(nx + 1, ny + 1, nz, tile)

    def generateSubtiles(self, x, y, zoom, tile):
        subtile = Tile(zoom, x, y)
        # https://stackoverflow.com/a/43105613/488489 - indexing
        prepared_clip = prep(subtile.bbox.buffer(1.194 * 4))
        clipCache = BBoxCache(subtile)
        for element in tile.elements:
            if element.mapping.get('zoom-max', 14) < zoom:
                continue
            # noinspection PyBroadException
            try:
                if prepared_clip.covers(element.geom):
                    subtile.elements.append(element)
                elif prepared_clip.intersects(element.geom):
                    subtile.elements.append(element.clone(clipCache[element.mapping.get('clip-buffer', 4)].intersection(element.geom)))
            except Exception as ex:
                self.logger.error("Error preparing element for tile %s" % subtile)
                self.logger.error(" element was: %s" % element)
                self.logger.error(" error was: %s" % ex)
        self.tile_queue.put(subtile)

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
            osmconvert_call += ['-b=%.4f,%.4f,%.4f,%.4f' % (bbox.west, bbox.south, bbox.east, bbox.north)]
            osmconvert_call += ['--complete-ways', '--complete-multipolygons', '--complete-boundaries', '-o=%s' % target_pbf_path]
            self.logger.debug("    calling: %s", " ".join(osmconvert_call))
            if not self.dry_run:
                subprocess.check_call(osmconvert_call)
            else:
                subprocess.check_call(['touch', target_pbf_path])
        return target_pbf_path

    def generateBasemapFile(self, source_pbf_path):
        target_pbf_path = self.pbf_path(0, 0, 0)
        if not os.path.exists(target_pbf_path) or os.path.getmtime(target_pbf_path) < self.timestamp:
            self.logger.info("  Creating basemap file: %s" % target_pbf_path)
            pbf_dir = os.path.dirname(target_pbf_path)
            if not os.path.exists(pbf_dir):
                os.makedirs(pbf_dir)
            if os.path.exists(target_pbf_path):
                os.remove(target_pbf_path)

            if self.stubmap:
                filter_name = 'stubmap'
            else:
                filter_name = 'basemap'

            osmfilter_call = [configuration.OSMFILTER_PATH, source_pbf_path]
            osmfilter_call += ['--parameter-file=%s/%s.filter' % (configuration.FILTERS_PATH, filter_name)]
            osmfilter_call += ['-o=%s' % target_pbf_path]
            self.logger.debug("    calling: %s", " ".join(osmfilter_call))
            if not self.dry_run:
                subprocess.check_call(osmfilter_call)
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
    parser.add_argument('-t', '--timeout', default=0, type=int, help='timeout, seconds')
    parser.add_argument('-d', '--dry-run', action='store_true', help='do not generate any files')
    parser.add_argument('-b', '--bbox', help='bbox override: left,bottom,right,top (for testing purposes, in EPSG:3857)')
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    parser.add_argument('-n', '--noninteractive', action='store_true', help='forbid interactive mode')
    parser.add_argument('-s', '--single-thread', action='store_true', help='do not use multi-threading')
    parser.add_argument('-i', '--intermediate', action='store_true', help='create intermediate osm.pbf file')
    parser.add_argument('-k', '--keep', action='store_true', help='do not remove intermediate osm.pbf file on success')
    parser.add_argument('-f', '--from-file', action='store_true', help='use file instead of database as data source')
    parser.add_argument('x', type=int, help='tile X')
    parser.add_argument('y', type=int, help='tile Y')
    args = parser.parse_args()

    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        print("Invalid log level: %s" % args.log)
        exit(1)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    logging.getLogger("shapely").setLevel(logging.ERROR)
    app_logger = logging.getLogger(__name__)
    # during a dry run the console should receive all logs
    if args.dry_run:
        app_logger.setLevel(logging.DEBUG)

    try:
        mapWriter = MapWriter(args.data_path, args.dry_run, args.noninteractive, args.single_thread)
        mapWriter.createMap(args.x, args.y, args.timeout, args.intermediate, args.keep, args.from_file, args.bbox)
    except Exception as e:
        app_logger.exception(e)
