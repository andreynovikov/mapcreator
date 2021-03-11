import re

from typing import Optional

from sqlite3 import connect, Connection
from spooky import hash64
from shapely.ops import transform
from util.geometry import mercator_to_wgs84
from util.url import iri2uri
from util.smaz import compress
from util.codebooks import WEBSITE_TREE, OPENING_HOURS_TREE, PHONE_TREE

OH_CLEANUP_PATTERN = re.compile(r'\s+([\s,;])')
PHONE_CLEANUP_PATTERN = re.compile(r'[ ()\-.]')
TILE_INSERT_QUERY: str = 'REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)'
NAME_INSERT_QUERY: str = 'REPLACE INTO names (ref, name) VALUES (?, ?)'
FEATURE_NAME_INSERT_QUERY: str = 'REPLACE INTO feature_names (id, lang, name) VALUES (?, ?, ?)'
FEATURE_INSERT_QUERY: str = 'REPLACE INTO features (id, kind, type, lat, lon, opening_hours, phone, wikipedia, website, flags, enum1) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'


class MTilesDatabase:

    def __init__(self, filename: str):
        self.filename: str = filename
        self.namehashes: list = []
        self.db: Optional[Connection] = None

    def create(self, name: str, db_type: str, timestamp: int, db_format: str, bounds=None):
        self.db = connect(self.filename, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode = OFF')
        self.db.execute('PRAGMA synchronous = NORMAL')
        # check if database already exists
        try:
            self.db.execute('SELECT name, value FROM metadata LIMIT 1')
            self.db.execute('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT 1')
            self.db.execute('DELETE FROM metadata')
        except:
            self.db.execute('CREATE TABLE metadata (name TEXT NOT NULL, value TEXT)')
            self.db.execute('CREATE TABLE tiles (zoom_level INTEGER NOT NULL, tile_column INTEGER NOT NULL, tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL)')
            self.db.execute('CREATE TABLE names (ref INTEGER NOT NULL, name TEXT NOT NULL)')
            self.db.execute('CREATE TABLE feature_names (id INTEGER NOT NULL, lang INTEGER NOT NULL, name INTEGER NOT NULL)')
            self.db.execute('CREATE TABLE features (id INTEGER NOT NULL, kind INTEGER, type INTEGER, lat REAL, lon REAL, opening_hours TEXT, phone TEXT, wikipedia TEXT, website TEXT, flags INTEGER, enum1 INTEGER)')
            self.db.execute('CREATE UNIQUE INDEX coord ON tiles (zoom_level, tile_column, tile_row)')
            self.db.execute('CREATE UNIQUE INDEX property ON metadata (name)')
            self.db.execute('CREATE UNIQUE INDEX name_ref ON names (ref)')
            self.db.execute('CREATE UNIQUE INDEX feature_name_lang ON feature_names (id, lang)')
            self.db.execute('CREATE UNIQUE INDEX feature_id ON features (id)')
            if name == "basemap":
                self.db.execute('PRAGMA main.page_size = 4096')
                self.db.execute('PRAGMA main.auto_vacuum = INCREMENTAL')
                self.db.execute('CREATE TABLE maps (x INTEGER NOT NULL, y INTEGER NOT NULL, date INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0, downloading INTEGER NOT NULL DEFAULT 0, hillshade_downloading INTEGER NOT NULL DEFAULT 0)')
                self.db.execute('CREATE UNIQUE INDEX maps_x_y ON maps (x, y)')
                self.db.execute('CREATE TABLE map_features (x INTEGER NOT NULL, y INTEGER NOT NULL, feature INTEGER NOT NULL)')
                self.db.execute('CREATE INDEX map_feature_ids ON map_features (feature)')
                self.db.execute('CREATE UNIQUE INDEX map_feature_refs ON map_features (x, y, feature)')

        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('name', name))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('type', db_type))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('version', '3'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('timestamp', timestamp))
        # self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('description', description))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('format', db_format))

        if bounds is not None:
            self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('bounds', bounds))

        self.db.commit()
        self.db.text_factory = bytes

    def commit(self):
        self.db.commit()

    def finish(self):
        self.db.commit()
        self.db.execute('VACUUM')
        self.db.close()
        self.db = None

    def isValid(self):
        if self.db is None:
            self.db = connect(self.filename, check_same_thread=False)
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM metadata WHERE name = 'timestamp'")
        date = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM tiles")
        count = int(cursor.fetchone()[0])
        self.finish()
        return date and count == 21844

    def putTile(self, zoom: int, x: int, y: int, content: bytes):
        self.db.execute(TILE_INSERT_QUERY, (zoom, x, y, memoryview(content)))

        """
        86M /gis/data/7/74/74-37.mtiles
        49M /gis/data/7/74/74-37.mtiles.gz
        memoryview(zcompress(content, 9))
        63M /gis/data/7/74/74-37.mtiles
        """

    def putName(self, name: str) -> int:
        h: int = hash64(name)
        if h & 0x8000000000000000:
            h = -0x10000000000000000 + h
        if h in self.namehashes:
            return h
        self.db.execute(NAME_INSERT_QUERY, (h, name))
        return h

    def putFeature(self, el_id: int, tags: dict, kind: int, el_type: int, label, geometry):
        if 'name' in tags:
            h = self.putName(tags['name'])
            self.db.execute(FEATURE_NAME_INSERT_QUERY, (el_id, 0, h))
            if 'name:en' in tags:
                h = self.putName(tags['name:en'])
                self.db.execute(FEATURE_NAME_INSERT_QUERY, (el_id, 840, h))
            if 'name:de' in tags:
                h = self.putName(tags['name:de'])
                self.db.execute(FEATURE_NAME_INSERT_QUERY, (el_id, 276, h))
            if 'name:ru' in tags:
                h = self.putName(tags['name:ru'])
                self.db.execute(FEATURE_NAME_INSERT_QUERY, (el_id, 643, h))
        lat: Optional[float] = None
        lon: Optional[float] = None
        opening_hours: Optional[str] = None
        phone: Optional[str] = None
        wikipedia: Optional[str] = None
        website: Optional[str] = None
        flags: Optional[int] = None
        enum1: Optional[int] = None
        if label:
            if isinstance(label, list):
                geom = transform(mercator_to_wgs84, label[0])
            else:
                geom = transform(mercator_to_wgs84, label)
            lat = geom.y
            lon = geom.x
        elif geometry.type == 'Point':
            geom = transform(mercator_to_wgs84, geometry)
            lat = geom.y
            lon = geom.x
        if kind and kind & 0x0FFBFFF8 != 0:  # skip places, roads, buildings, barriers
            if 'opening_hours' in tags:
                oh = tags['opening_hours']
                oh = oh.replace('"', '')
                oh = OH_CLEANUP_PATTERN.sub(r'\1', oh)
                oh = ''.join(c for c in oh if ord(c) < 128)  # strip non-ascii chars, should find better solution
                opening_hours = compress(oh, compression_tree=OPENING_HOURS_TREE)
            if 'phone' in tags:
                ph = tags['phone'].split(',')[0]
                ph = PHONE_CLEANUP_PATTERN.sub('', ph)
                ph = ''.join(c for c in ph if ord(c) < 128)  # strip non-ascii chars, should find better solution
                phone = compress(ph, compression_tree=PHONE_TREE)
            if 'wikipedia' in tags:
                wikipedia = tags['wikipedia']
            if 'website' in tags:
                website = compress(iri2uri(tags['website']), compression_tree=WEBSITE_TREE)
            if 'fee' in tags and tags['fee'] == 'yes':
                if flags is None:
                    flags = 0x00000001
                else:
                    flags |= 0x00000001
            if 'wheelchair' in tags:
                if flags is None:
                    flags = 0x00000000
                if tags['wheelchair'] == 'no':
                    flags |= 0x00000002
                elif tags['wheelchair'] == 'limited':
                    flags |= 0x00000004
                elif tags['wheelchair'] == 'yes':
                    flags |= 0x00000006
            if 'enum1' in tags:
                enum1 = tags['enum1']

        self.db.execute(FEATURE_INSERT_QUERY, (el_id, kind, el_type, lat, lon, opening_hours, phone, wikipedia, website, flags, enum1))
