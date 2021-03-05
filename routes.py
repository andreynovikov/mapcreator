#!/usr/bin/env python3

import os
import re
import argparse
import logging.config
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import osmium
import shapely.wkb as shapely_wkb
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, linemerge

from webcolors import name_to_rgb

import configuration
from util.geometry import wgs84_to_mercator

wkbFactory = osmium.geom.WKBFactory()


def _color(r, g, b):
    return (r << 16) + (g << 8) + b


colors = {
    "white": _color(240, 240, 240),
    "black": _color(86, 86, 86),
    "gray": _color(120, 120, 120),
    "red": _color(255, 190, 190),
    "green": _color(190, 255, 190),
    "blue": _color(190, 190, 255),
    "yellow": _color(255, 255, 175),
    "darkbrown": _color(101, 67, 33),
    "darkgray": 0x444444,
    "lightgray": 0xcccccc
}

color_aliases = {
    "peach": "peachpuff",  # css color
    "peachpuf": "peachpuff",
    "rose": "mistyrose",  # css color
    "grey": "gray",
    "darkgrey": "darkgray",
    "lightgrey": "lightgray",
}


def _get_color(color: str) -> Optional[int]:
    if len(color) == 0:
        return None

    # process RGB hex color code
    if color[0] == '#':
        try:
            c = int(color[1:], 16)
            if c.bit_length() > 24:
                raise ValueError
            return c
        except ValueError:
            logging.warning("Invalid hex color: %s" % color)
            return None

    # clean all delimiters
    color = re.sub(r'[\-_\s]', '', color)

    # check aliases
    if color in color_aliases:
        color = color_aliases[color]

    if color in colors:
        return colors[color]

    try:
        # try to get color by name
        r, g, b = name_to_rgb(color)
        # return ColorUtil.modHsv(css, 1.0, HSV_S, HSV_V, true);
        return _color(r, g, b)
    except ValueError:
        # if failed try to treat as a RGB hex without prefix
        if len(color) == 6:
            try:
                c = int(color, 16)
                return c
            except ValueError:
                pass

    logging.debug("Unknown color: %s" % color)
    return None


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
                    colour = _get_color(tag.v)
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
                relation.colour = _get_color(tag.v)
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
            cur.execute("""CREATE TABLE osm_routes (id bigint PRIMARY KEY, route varchar(10), network varchar(10),
                            osmc_symbol varchar(60), colour int, state varchar(255), ref varchar(20),
                            name varchar(255), name_en varchar(255), name_de varchar(255), name_ru varchar(255))""")
            cur.execute("SELECT AddGeometryColumn('osm_routes','geom','3857','GEOMETRY',2)")
            for element_id, route in self.routes.items():
                try:
                    cur.execute("""INSERT INTO osm_routes (id, route, network, osmc_symbol, colour, state, ref, name, name_en, name_de, name_ru, geom)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 3857))""",
                                (element_id, route.route, route.network, route.osmc_symbol, route.colour, route.state, route.ref,
                                 route.name, route.name_en, route.name_de, route.name_ru, route.geom.wkt))
                except psycopg2.DataError:
                    self.logger.exception("Insertion error: %s" % str(route))
            c.commit()
            cur.execute('CREATE INDEX ON osm_routes USING GIST ("geom")')


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
