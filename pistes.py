#!/usr/bin/env python3

import os
import argparse
import logging.config
from collections import defaultdict

import psycopg2
import psycopg2.extras
import osmium
import shapely.wkb as shapelyWkb
from shapely.geometry import LineString, Polygon
from shapely.ops import transform, linemerge
from shapely.ops import transform, linemerge, cascaded_union
from shapely.prepared import prep
from tqdm import tqdm

import configuration
from util import osm
from util.geometry import wgs84_to_mercator, mercator_to_wgs84, clockwise


wkbFactory = osmium.geom.WKBFactory()

difficulties = ['novice', 'easy', 'intermediate', 'advanced', 'expert', 'freeride', 'extreme', 'unknown']
groomings = ['unknown', 'mogul', 'backcountry']


def multidimentiondict(n, type):
    """ Creates an n-dimension dictionary where the n-th dimension is of type 'type' """
    if n <= 1:
        return type()
    return defaultdict(lambda: multidimentiondict(n-1, type))


class Piste():
    def __init__(self, id, area, geom, piste=None, difficulty=None, grooming=None):
        self.id = id
        self.area = area
        if not area:
            geom = geom.buffer(10, resolution=32)
        self.geom = geom
        self.piste = piste
        self.difficulty = difficulty
        self.grooming = grooming
        self.point = geom.representative_point()
        self.borders = None


    def __str__(self):
        return "%s %s %s" % (self.piste, self.difficulty, self.grooming)


class Resort():
    def __init__(self, piste):
        # union of all pistes
        self.geom = Polygon()
        # union of area pistes
        self.area = Polygon()
        # list of all pistes combined by difficulty
        self.pistes = multidimentiondict(3, list)
        # united piste areas combined by difficulty, used in post-processing
        self.areas = multidimentiondict(3, Polygon)
        # united piste borders combined by difficulty, used in post-processing
        self.borders = multidimentiondict(3, LineString)

        self.add(piste)
        self.point = piste.point



    def add(self, piste):
        if piste.area:
            self.area = cascaded_union([self.area, piste.geom])
        self.pistes[piste.difficulty][piste.grooming].append(piste)
        self.geom = cascaded_union([self.geom, piste.geom])
        self.prepared = prep(self.geom)


    def check(self, piste):
        if self.point.distance(piste.point) > 100000: # do not consider pistes more then 100km away
            return False
        return self.prepared.contains(piste.geom) or self.prepared.intersects(piste.geom) # 'contains' is much faster


    def combine(self, resort):
        for difficulty in resort.pistes:
            for grooming in resort.pistes[difficulty]:
                self.pistes[difficulty][grooming].extend(resort.pistes[difficulty][grooming])
        self.area = cascaded_union([self.area, resort.area])
        self.geom = cascaded_union([self.geom, resort.geom])
        self.prepared = prep(self.geom)


class OsmFilter(osmium.SimpleHandler):
    def __init__(self, logger):
        super(OsmFilter, self).__init__()
        self.pistes = []
        self.resorts = []
        self.logger = logger


    def way(self, w):
        self.process(2, w)


    def area(self, a):
        self.process(3, a)


    def process(self, t, o):
        if len(o.tags) == 0:
            return
        if t == 2 and o.is_closed():
            return # will get it later in area handler
        piste = None
        difficulty = 'unknown'
        grooming = 'unknown'
        id = o.id
        try:
            for tag in o.tags:
                if tag.k == 'piste:type' and tag.v == 'downhill':
                    piste = 'downhill'
                if tag.k == 'piste:difficulty' and tag.v in difficulties:
                    difficulty = tag.v
                if tag.k == 'piste:grooming' and tag.v in groomings:
                    grooming = tag.v
            if piste:
                if t == 2:
                    wkb = wkbFactory.create_linestring(o)
                if t == 3:
                    id = o.orig_id()
                    wkb = wkbFactory.create_multipolygon(o)
                geom = transform(wgs84_to_mercator, shapelyWkb.loads(wkb, hex=True))
                if t == 3 and not o.is_multipolygon():
                    geom = geom[0] # simplify geometry
                geom = clockwise(geom)
                # construct unique id
                if t == 3 and o.from_way():
                    t = 2
                #print("%d: %s %s" % (id, piste, geom.type))
                id = (id << 2) + t
                piste = Piste(id, geom.type in ['Polygon', 'MultiPolygon'], geom, piste, difficulty, grooming)
                self.pistes.append(piste)
        except Exception as e:
            self.logger.exception("%s: %s" % (id, e))


    def finish(self):
        self.logger.info("Group pistes")
        progress = tqdm(total=len(self.pistes), desc="Pistes")
        for piste in self.pistes:
            resorts = []
            for resort in self.resorts:
                if resort.check(piste):
                    resorts.append(resort)
            if resorts:
                resorts[0].add(piste)
                for resort in resorts[1:]:
                    resorts[0].combine(resort)
                    self.resorts.remove(resort)
            else:
                self.resorts.append(Resort(piste))
            progress.update()
        progress.close()

        self.logger.info("Process resorts")
        progress = tqdm(total=len(self.resorts), desc="Resorts")
        for resort in self.resorts:
            print("------------------")
            resort.geom = resort.geom.buffer(1.7, resolution=32)
            areas = Polygon()
            geoms = []
            for difficulty in difficulties:
                if not resort.pistes[difficulty]:
                    continue
                print(difficulty)
                for grooming in groomings:
                    if not resort.pistes[difficulty][grooming]:
                        continue
                    print("  ", grooming)
                    pistes = []
                    for piste in resort.pistes[difficulty][grooming]:
                        if not piste.area:
                            piste.geom = piste.geom.difference(resort.area)
                        pistes.append(piste.geom)
                    resort.areas[difficulty][grooming] = cascaded_union(pistes)
                    resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(5, resolution=32).buffer(-3)
                    resort.borders[difficulty][grooming] = resort.areas[difficulty][grooming].boundary
                    for geom in geoms:
                        resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].difference(geom)
                    geoms.append(resort.areas[difficulty][grooming])
            for borders_difficulty in resort.borders:
                for borders_grooming in resort.borders[borders_difficulty]:
                    for pistes_difficulty in resort.pistes:
                        for pistes_grooming in resort.areas[pistes_difficulty]:
                            if resort.borders[borders_difficulty][borders_grooming].is_empty:
                                continue
                            if borders_difficulty == pistes_difficulty and borders_grooming == pistes_grooming:
                                continue
                            print("%s %s %s %s" % (borders_difficulty, borders_grooming, pistes_difficulty, pistes_grooming))
                            borders = resort.borders[borders_difficulty][borders_grooming]
                            pistes = resort.areas[pistes_difficulty][pistes_grooming].buffer(0.0001)
                            borders = borders.difference(pistes)
                            resort.borders[borders_difficulty][borders_grooming] = borders
        progress.close()

        self.logger.info("Save data")
        with psycopg2.connect(configuration.DATA_DB_DSN) as c:
            cur = c.cursor()
            try:
                cur.execute("SELECT DropGeometryColumn('osm_pistes','geom')")
            except psycopg2.InternalError:
                pass
            c.commit()
            try:
                cur.execute("SELECT DropGeometryColumn('osm_piste_borders','geom')")
            except psycopg2.InternalError:
                pass
            c.commit()
            cur.execute('DROP TABLE IF EXISTS osm_pistes')
            c.commit()
            cur.execute('DROP TABLE IF EXISTS osm_piste_borders')
            c.commit()
            cur.execute("""CREATE TABLE osm_pistes (difficulty varchar(12), grooming varchar(12))""")
            cur.execute("SELECT AddGeometryColumn('osm_pistes','geom','3857','GEOMETRY',2)")
            cur.execute("""CREATE TABLE osm_piste_borders (difficulty varchar(12), grooming varchar(12))""")
            cur.execute("SELECT AddGeometryColumn('osm_piste_borders','geom','3857','GEOMETRY',2)")
            for resort in self.resorts:
                print("------------------")
                for difficulty in resort.areas:
                    print(difficulty)
                    for grooming in resort.areas[difficulty]:
                        print("  ", grooming)
                        if resort.areas[difficulty][grooming].is_empty:
                            continue
                        try:
                            cur.execute("""INSERT INTO osm_pistes (difficulty, grooming, geom)
                                           VALUES (%s, %s, ST_GeomFromText(%s, 3857))""", \
                                        (difficulty, grooming, resort.areas[difficulty][grooming].wkt))
                        except psycopg2.DataError as e:
                            self.logger.exception("Insertion error:")
                        if resort.borders[difficulty][grooming].is_empty:
                            continue
                        try:
                            cur.execute("""INSERT INTO osm_piste_borders (difficulty, grooming, geom)
                                           VALUES (%s, %s, ST_GeomFromText(%s, 3857))""", \
                                        (difficulty, grooming, resort.borders[difficulty][grooming].wkt))
                        except psycopg2.DataError as e:
                            self.logger.exception("Insertion error:")
            c.commit()
            cur.execute('CREATE INDEX ON osm_pistes USING GIST ("geom")')
            cur.execute('CREATE INDEX ON osm_piste_borders USING GIST ("geom")')
        self.logger.info("Finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek pistes preprocessor')
    parser.add_argument('-p', '--data-path', default=configuration.DATA_PATH, help='base path for data files')
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
        osm_path = os.path.join(args.data_path, 'pistes.o5m')
        timestamp = os.path.getmtime(configuration.SOURCE_PBF)
        if not os.path.exists(osm_path) or os.path.getmtime(osm_path) < timestamp:
            # time osmfilter planet-170914.o5m --parameter-file=boundaries.filter >boundaries.o5m
            pass
        handler = OsmFilter(logger)
        handler.apply_file(osm_path, locations=True)
        handler.finish()

    except Exception as e:
        logger.exception("An error occurred:")
