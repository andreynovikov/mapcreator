#!/usr/bin/env python3

import os
import argparse
import logging.config
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import osmium
import shapely.wkb as shapely_wkb
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, linemerge

import configuration
from util.geometry import wgs84_to_mercator
from util.osm.buildings import get_color

wkbFactory = osmium.geom.WKBFactory()


class Relation:
    def __init__(self, osm_id: int):
        self.osm_id: int = osm_id
        self.ways: List[int] = []
        self.geoms: List[BaseGeometry] = []
        self.incomplete: List[int] = []
        self.is_route: bool = False
        self.route: Optional[str] = None
        self.network: Optional[str] = None
        self.osmc_symbol: Optional[str] = None
        self.colour: Optional[int] = None
        self.state: Optional[str] = None
        self.ref: Optional[str] = None
        self.name: Optional[str] = None
        self.name_en: Optional[str] = None
        self.name_de: Optional[str] = None
        self.name_ru: Optional[str] = None


class Route:
    def __init__(self, geom: BaseGeometry, route: str = None, network: str = None, osmc_symbol: str = None,
                 colour: int = None, state: str = None, ref: str = None, name: str = None, name_en: str = None,
                 name_de: str = None, name_ru: str = None, way: str = None):
        self.geom: BaseGeometry = geom
        self.route: str = route
        self.network: str = network
        self.osmc_symbol: str = osmc_symbol
        self.colour: int = colour
        self.state: str = state
        self.ref: str = ref
        self.name: str = name
        self.name_en: str = name_en
        self.name_de: str = name_de
        self.name_ru: str = name_ru
        self.way: str = way

    def __str__(self):
        return "%s %s %s %s %s %s" % (self.route, self.network, self.osmc_symbol, self.colour, self.state, self.ref)


class OsmFilter(osmium.SimpleHandler):
    # noinspection PyShadowingNames
    def __init__(self, logger):
        super(OsmFilter, self).__init__()
        self.routes: Dict[int, Route] = {}
        self.ways: Dict[int, Dict] = {}
        self.relations: Dict[int, Relation] = {}
        self.logger = logger

    def way(self, w):
        try:
            wkb = wkbFactory.create_linestring(w)
            route: Optional[str] = None
            network: Dict[str, bool] = {}
            osmc_symbol: Optional[str] = None
            colour: Optional[int] = None
            state: Optional[str] = None
            ref: Optional[str] = None
            name: Optional[str] = None
            name_en: Optional[str] = None
            name_de: Optional[str] = None
            name_ru: Optional[str] = None
            way: Optional[str] = None
            for tag in w.tags:
                if tag.k == 'route':
                    if tag.v in ('hiking', 'foot'):
                        route = 'hiking'
                    elif tag.v in ('bicycle', 'mtb'):
                        route = tag.v
                    elif tag.v == 'ferry':
                        way = tag.v
                if tag.k == 'network' and tag.v in ('iwn', 'nwn', 'rwn', 'lwn', 'icn', 'ncn', 'rcn', 'lcn'):
                    network[tag.v] = True
                if tag.k in ('icn', 'ncn', 'rcn', 'lcn') and tag.v == 'yes':
                    network[tag.k] = True
                if tag.k == 'osmc:symbol':
                    osmc_symbol = tag.v[:60]
                if tag.k == 'colour':
                    colour = get_color(tag.v, False)
                if tag.k == 'state':
                    state = tag.v[:255]
                if tag.k == 'ref':
                    ref = tag.v
                if tag.k == 'name':
                    name = tag.v
                if tag.k == 'name:en':
                    name_en = tag.v
                if tag.k == 'name:de':
                    name_de = tag.v
                if tag.k == 'name:ru':
                    name_ru = tag.v
                if tag.k in ('highway', 'railway', 'aerialway', 'waterway'):
                    way = tag.v
            if ref and ref == name and len(ref) > 10:
                ref = None
            if ref and len(ref) > 20:
                ref = ref[:20]
            if route:
                if route not in ('bicycle', 'mtb'):
                    colour = None
                geom = transform(wgs84_to_mercator, shapely_wkb.loads(wkb, hex=True))
                element_id = (w.id << 2) + 2
                self.routes[element_id] = Route(geom, route, next(iter(network.keys()), None), osmc_symbol, colour, state, ref, name, name_en, name_de, name_ru, way)
            else:
                self.ways[w.id] = {'wkb': wkb, 'way': way, 'closed': w.is_closed()}
        except Exception as ex:
            self.logger.error("%s: %s" % (w.id, ex))

    def relation(self, r):
        t = None
        relation = Relation(r.id)
        for tag in r.tags:
            if tag.k == 'type':
                t = tag.v
            if tag.k == 'route':
                if tag.v in ('hiking', 'foot'):
                    relation.route = 'hiking'
                elif tag.v in ('bicycle', 'mtb'):
                    relation.route = tag.v
            if tag.k == 'network' and tag.v in ('iwn', 'nwn', 'rwn', 'lwn', 'icn', 'ncn', 'rcn', 'lcn'):
                relation.network = tag.v
            if tag.k == 'osmc:symbol':
                relation.osmc_symbol = tag.v[:60]
            if tag.k == 'colour':
                relation.colour = 0x00ffffff & get_color(tag.v, False)
            if tag.k == 'state':
                relation.state = tag.v[:255]
            if tag.k == 'ref':
                relation.ref = tag.v
            if tag.k == 'name':
                relation.name = tag.v
            if tag.k == 'name:en':
                relation.name_en = tag.v
            if tag.k == 'name:de':
                relation.name_de = tag.v
            if tag.k == 'name:ru':
                relation.name_ru = tag.v
        if relation.ref and relation.ref == relation.name and len(relation.ref) > 10:
            relation.ref = None
        if relation.ref and len(relation.ref) > 20:
            relation.ref = relation.ref[:20]

        if relation.route not in ('bicycle', 'mtb'):
            relation.colour = None

        relation.is_route = t == 'route' and relation.route
        self.relations[r.id] = relation

        for member in r.members:
            if member.role in ('planned', 'proposed'):
                continue
            if member.type == 'w':
                element_id = (member.ref << 2) + 2
                if element_id in self.routes:
                    relation.geoms.append(self.routes[element_id].geom)
                    if relation.is_route and self.routes[element_id].ref == relation.ref:
                        self.ways[member.ref] = {
                            'wkb': self.routes[element_id].geom.wkb.hex(),
                            'way': self.routes[element_id].way,
                            'closed': False
                        }
                        del self.routes[element_id]
                else:
                    way = self.ways.get(member.ref, {'wkb': None, 'closed': False})
                    if way['closed']:
                        continue
                    if way['wkb']:
                        geom: BaseGeometry = transform(wgs84_to_mercator, shapely_wkb.loads(way['wkb'], hex=True))
                        relation.geoms.append(geom)
                        relation.ways.append(member.ref)
                    else:
                        self.logger.error("Missing way %s" % member.ref)
            if member.type == 'r':
                if member.ref in self.relations:
                    relation.geoms.extend(self.relations[member.ref].geoms)
                    relation.ways.extend(self.relations[member.ref].ways)
                else:
                    relation.incomplete.append(member.ref)

    def finish(self):
        for osm_id, relation in self.relations.items():
            if not relation.is_route:
                continue
            while relation.incomplete:
                rel_id = relation.incomplete.pop()
                r = self.relations.get(rel_id, None)
                if r:
                    relation.geoms.extend(r.geoms)
                    relation.ways.extend(r.ways)
                    relation.incomplete.extend(r.incomplete)
                else:
                    self.logger.error("Missing relation: %s (in %s)" % (rel_id, relation.osm_id))

            # MultiLineStrings can not be merged so we have to split them first
            lines: List[BaseGeometry] = []
            for geom in relation.geoms:
                if geom.type == 'LineString':
                    lines.append(geom)
                else:
                    lines.extend(geom.geoms)
            if not lines:
                self.logger.info("Empty relation: %s" % relation.osm_id)
                continue

            united_geom: BaseGeometry = linemerge(lines)
            element_id: int = (osm_id << 2) + 3
            self.routes[element_id] = Route(united_geom, relation.route, relation.network, relation.osmc_symbol,
                                            relation.colour, relation.state, relation.ref, relation.name,
                                            relation.name_en, relation.name_de, relation.name_ru)

        with psycopg2.connect(configuration.DATA_DB_DSN) as c:
            cur = c.cursor()
            try:
                cur.execute("SELECT DropGeometryColumn('osm_routes','geom')")
            except psycopg2.InternalError:
                pass
            c.commit()
            cur.execute('DROP TABLE IF EXISTS osm_routes')
            c.commit()
            cur.execute("CREATE TABLE osm_routes (relation_id bigint PRIMARY KEY, type varchar(10), tags hstore")
            cur.execute("SELECT AddGeometryColumn('osm_routes','geom','3857','MULTILINESTRING',2)")
            for element_id, route in self.routes.items():
                try:
                    hstore = []
                    if route.network:
                        hstore.append('"network" => "%s"'.format(route.network))
                    if route.osmc_symbol:
                        hstore.append('"osmc:symbol" => "%s"'.format(route.osmc_symbol))
                    if route.colour:
                        hstore.append('"colour" => "%s"'.format(route.colour))
                    if route.state:
                        hstore.append('"state" => "%s"'.format(route.state))
                    if route.ref:
                        hstore.append('"ref" => "%s"'.format(route.ref))
                    if route.name:
                        hstore.append('"name" => "%s"'.format(route.name))
                    if route.name_en:
                        hstore.append('"name:en" => "%s"'.format(route.name_en))
                    if route.name_de:
                        hstore.append('"name:de" => "%s"'.format(route.name_de))
                    if route.name_ru:
                        hstore.append('"name:ru" => "%s"'.format(route.name_ru))
                    cur.execute("""INSERT INTO osm_routes (relation_id, type, tags, geom)
                                   VALUES (%s, %s, %s, ST_GeomFromText(%s, 3857))""",
                                (element_id, route.route, ', '.join(hstore), route.geom.wkt))
                except psycopg2.DataError:
                    self.logger.exception("Insertion error: %s" % str(route))
            c.commit()
            cur.execute('CREATE INDEX ON osm_routes USING GIST ("geom")')
            cur.execute('CREATE INDEX ON osm_routes USING BTREE ("relation_id")')
            cur.execute('ANALYZE osm_routes')


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

    # noinspection PyBroadException
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
