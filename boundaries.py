#!/usr/bin/env python3

import os
import argparse
import logging.config

import psycopg2
import psycopg2.extras
import osmium

import configuration
from util import osm


wktFactory = osmium.geom.WKTFactory()


class Boundary:
    def __init__(self, wkt, admin_level, maritime):
        self.wkt = wkt
        self.admin_level = admin_level
        self.maritime = maritime

    def __str__(self):
        return "%s %s %s" % (self.admin_level, self.maritime, self.wkt)


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, logger):
        super(OsmFilter, self).__init__()
        self.boundaries = set()
        self.ways = {}
        self.logger = logger

    def way(self, w):
        try:
            wkt = wktFactory.create_linestring(w)
            boundary = False
            admin_level = None
            maritime = None
            for tag in w.tags:
                if tag.k == 'boundary' and tag.v == 'administrative':
                    boundary = True
                if tag.k == 'admin_level' and tag.v in ('1', '2', '3', '4'):
                    admin_level = int(tag.v)
                if tag.k == 'maritime':
                    maritime = osm.boolean(tag.v)
            if not boundary:
                admin_level = None
            self.ways[w.id] = Boundary(wkt, admin_level, maritime)
        except Exception as e:
            self.logger.error("%s: %s" % (w.id, e))

    def relation(self, r):
        boundary = False
        t = None
        admin_level = None
        maritime = None
        for tag in r.tags:
            if tag.k == 'boundary' and tag.v == 'administrative':
                boundary = True
            if tag.k == 'type':
                t = tag.v
            if tag.k == 'admin_level' and tag.v in ('1', '2', '3', '4'):
                admin_level = int(tag.v)
            if tag.k == 'maritime':
                maritime = osm.boolean(tag.v)
        if t != 'boundary' or not boundary or not admin_level:
            return
        self.logger.error("%s %s" % (str(r.id), t))
        for member in r.members:
            if member.type == 'w' and member.role == 'outer':
                way = self.ways.get(member.ref, None)
                if not way.admin_level or way.admin_level > admin_level:
                    way.admin_level = admin_level
                if maritime and maritime == 'yes':
                    way.maritime = maritime

    def finish(self):
        with psycopg2.connect(configuration.DATA_DB_DSN) as c:
            cur = c.cursor()
            try:
                cur.execute("SELECT DropGeometryColumn('osm_boundaries','geom');")
            except psycopg2.InternalError:
                pass
            c.commit()
            cur.execute('DROP TABLE IF EXISTS osm_boundaries;')
            c.commit()
            cur.execute("CREATE TABLE osm_boundaries (id bigint PRIMARY KEY, admin_level integer, maritime varchar(3));")
            cur.execute("SELECT AddGeometryColumn('osm_boundaries','geom','3857','GEOMETRY',2);")
            for id, way in self.ways.items():
                if way.admin_level:
                    cur.execute("""INSERT INTO osm_boundaries (id, admin_level, maritime, geom)
                                   VALUES (%s, %s, %s, ST_Transform(ST_GeomFromText(%s, 4326), 3857))""",
                                (id, way.admin_level, way.maritime, way.wkt))
            c.commit()
            cur.execute('CREATE INDEX ON osm_boundaries USING GIST ("geom")')
            cur.execute('ANALYZE osm_boundaries')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek boundaries preprocessor')
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
        osm_path = os.path.join(configuration.DATA_PATH, 'boundaries.o5m')
        timestamp = os.path.getmtime(configuration.SOURCE_PBF)
        if not os.path.exists(osm_path) or os.path.getmtime(osm_path) < timestamp:
            # time osmfilter planet-170914.o5m --parameter-file=boundaries.filter >boundaries.o5m
            pass
        handler = OsmFilter(logger)
        handler.apply_file(osm_path, locations=True)
        handler.finish()

    except Exception as e:
        logger.exception("An error occurred:")
