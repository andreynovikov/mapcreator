#!/usr/bin/env python3

import os
import argparse
import logging.config

import psycopg2
import psycopg2.extras
import osmium
import shapely.wkb as shapelyWkb
from shapely.ops import transform, linemerge

import configuration
from util import osm
from util.geometry import wgs84_to_mercator, mercator_to_wgs84, clockwise


"""
What to do with untagged lines: http://www.openstreetmap.org/way/337351731 ?
"""

wkbFactory = osmium.geom.WKBFactory()

NETWORKS = ['iwn','nwn','rwn','lwn',None]


class Way():
    def __init__(self, network):
        self.network = network


class Route():
    def __init__(self, geom, route=None, network=None, osmc_symbol=None, state=None, ref=None, name=None, name_en=None, name_de=None, name_ru=None, way=None):
        self.geom = geom
        self.route = route
        self.network = network
        self.osmc_symbol = osmc_symbol
        self.state = state
        self.ref = ref
        self.name = name
        self.name_en = name_en
        self.name_de = name_de
        self.name_ru = name_ru
        self.way = way

    def __str__(self):
        return "%s %s %s %s %s" % (self.route, self.network, self.osmc_symbol, self.state, self.ref)


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, logger):
        super(OsmFilter, self).__init__()
        self.routes = {}
        self.routeways = {}
        self.ways = {}
        self.logger = logger

    def way(self, w):
        try:
            wkb = wkbFactory.create_linestring(w)
            route = None
            network = None
            osmc_symbol = None
            state = None
            ref = None
            name = None
            name_en = None
            name_de = None
            name_ru = None
            way = None
            for tag in w.tags:
                if tag.k == 'route':
                    if tag.v in ('hiking','foot'):
                        route = 'hiking'
                    elif tag.v == 'ferry':
                        way = tag.v
                if tag.k == 'network' and tag.v in ('iwn','nwn','rwn','lwn'):
                    network = tag.v
                if tag.k == 'osmc:symbol':
                    osmc_symbol = tag.v[:60]
                if tag.k == 'state':
                    state = tag.v[:255]
                if tag.k == 'ref':
                    ref = tag.v[:30]
                if tag.k == 'name':
                    name = tag.v
                if tag.k == 'name:en':
                    name_en = tag.v
                if tag.k == 'name:de':
                    name_de = tag.v
                if tag.k == 'name:ru':
                    name_ru = tag.v
                if tag.k in ('highway','railway','aerialway','waterway'):
                    way = tag.v
            if route:
                geom = transform(wgs84_to_mercator, shapelyWkb.loads(wkb, hex=True))
                id = (w.id << 2) + 2
                self.routes[id] = Route(geom, route, network, osmc_symbol, state, ref, name, name_en, name_de, name_ru, way)
                if network:
                    self.routeways[id] = Way(network)
            else:
                self.ways[w.id] = {'wkb': wkb, 'way': way, 'closed': w.is_closed()}
        except Exception as e:
            self.logger.error("%s: %s" % (w.id, e))


    def relation(self, r):
        geoms = []
        t = None
        route = None
        network = None
        osmc_symbol = None
        state = None
        ref = None
        name = None
        name_en = None
        name_de = None
        name_ru = None
        for tag in r.tags:
            if tag.k == 'type':
                t = tag.v
            if tag.k == 'route' and tag.v in ('hiking','foot'):
                route = 'hiking'
            if tag.k == 'network' and tag.v in ('iwn','nwn','rwn','lwn'):
                network = tag.v
            if tag.k == 'osmc:symbol':
                osmc_symbol = tag.v[:60]
            if tag.k == 'state':
                state = tag.v[:255]
            if tag.k == 'ref':
                ref = tag.v[:30]
            if tag.k == 'name':
                name = tag.v
            if tag.k == 'name:en':
                name_en = tag.v
            if tag.k == 'name:de':
                name_de = tag.v
            if tag.k == 'name:ru':
                name_ru = tag.v
        if t != 'route' or not route:
            return
        for member in r.members:
            if member.type == 'w':
                id = (member.ref << 2) + 2
                if id in self.routes:
                    geoms.append(self.routes[id].geom)
                    if self.routes[id].ref == ref:
                        self.ways[member.ref] = {'wkb': self.routes[id].geom.wkb.hex(), 'way': self.routes[id].way,
                                                 'closed': False}
                        del self.routes[id]
                else:
                    way = self.ways.get(member.ref, {'wkb': None, 'closed': False})
                    if way['closed']:
                        continue
                    wkb = way.get('wkb', None)
                    if wkb:
                        geom = transform(wgs84_to_mercator, shapelyWkb.loads(wkb, hex=True))
                        geoms.append(geom)
                        if way.get('way', None):
                            if id in self.routeways:
                                if NETWORKS.index(network) < NETWORKS.index(self.routeways[id].network):
                                    self.routeways[id].network = network
                            elif network:
                                self.routeways[id] = Way(network)
                        else:
                            self.logger.warn("Way %s is not a motion way" % member.ref)
                    else:
                        self.logger.error("Missing way %s" % member.ref)
        # multilinestrings can not be merged so we have to split them first
        lines = []
        for geom in geoms:
            if geom.type == 'LineString':
                lines.append(geom)
            else:
                lines.extend(geom.geoms)
        if not lines:
            self.logger.error("Empty relation: %s" % r.id)
            return
        united_geom = linemerge(lines)
        id = (r.id << 2) + 3
        self.routes[id] = Route(united_geom, route, network, osmc_symbol, state, ref, name, name_en, name_de, name_ru)

    def finish(self):
        with psycopg2.connect(configuration.DATA_DB_DSN) as c:
            cur = c.cursor()
            try:
                cur.execute("SELECT DropGeometryColumn('osm_routes','geom')")
            except psycopg2.InternalError:
                pass
            c.commit()
            cur.execute('DROP TABLE IF EXISTS osm_routes')
            c.commit()
            cur.execute("""CREATE TABLE osm_routes (id bigint PRIMARY KEY, route varchar(10), network varchar(10),
                            osmc_symbol varchar(60), state varchar(255), ref varchar(30), name varchar(255),
                            name_en varchar(255), name_de varchar(255), name_ru varchar(255))""")
            cur.execute("SELECT AddGeometryColumn('osm_routes','geom','3857','GEOMETRY',2)")
            for id, route in self.routes.items():
                try:
                    cur.execute("""INSERT INTO osm_routes (id, route, network, osmc_symbol, state, ref, name, name_en, name_de, name_ru, geom)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 3857))""", \
                                (id, route.route, route.network, route.osmc_symbol, route.state, route.ref, route.name,
                                 route.name_en, route.name_de, route.name_ru, route.geom.wkt))
                except psycopg2.DataError as e:
                    self.logger.exception("Insertion error: %s" % str(route))
            c.commit()
            cur.execute('CREATE INDEX ON osm_routes USING GIST ("geom")')

            # map route networks to ways
            cur.execute('DROP TABLE IF EXISTS osm_features_meta')
            c.commit()
            cur.execute('CREATE TABLE osm_features_meta (id bigint PRIMARY KEY, network varchar(10))')
            for id, way in self.routeways.items():
                try:
                    cur.execute('INSERT INTO osm_features_meta (id, network) VALUES (%s, %s)', (id, way.network))
                except psycopg2.DataError as e:
                    self.logger.exception("Insertion error: %s" % str(route))
            c.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek routes preprocessor')
    parser.add_argument('-p', '--data-path', default='data', help='base path for data files')
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    args = parser.parse_args()

    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        print("Invalid log level: %s" % args.log)
        exit(1)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s - %(message)s')
    logging.getLogger("shapely").setLevel(logging.ERROR)
    logger = logging.getLogger(__name__)

    try:
        osm_path = os.path.join(configuration.DATA_PATH, 'routes.o5m')
        timestamp = os.path.getmtime(configuration.SOURCE_PBF)
        if not os.path.exists(osm_path) or os.path.getmtime(osm_path) < timestamp:
            # time osmfilter planet-170914.o5m --parameter-file=boundaries.filter >boundaries.o5m
            pass
        handler = OsmFilter(logger)
        handler.apply_file(osm_path, locations=True)
        handler.finish()

    except Exception as e:
        logger.exception("An error occurred:")
