from os.path import exists
from sqlite3 import connect

from shapely.ops import transform

from util.geometry import mercator_to_wgs84
from util.jenkins import hashlittle


class MTilesDatabase():

    def __init__(self, filename):
        self.filename = filename
        self.namehashes = []


    def create(self, name, type, version, timestamp, format, bounds=None):
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
            self.db.execute('CREATE TABLE features (id INTEGER NOT NULL, kind INTEGER, lat REAL, lon REAL)')
            self.db.execute('CREATE UNIQUE INDEX coord ON tiles (zoom_level, tile_column, tile_row)')
            self.db.execute('CREATE UNIQUE INDEX property ON metadata (name)')
            self.db.execute('CREATE UNIQUE INDEX name_ref ON names (ref)')
            self.db.execute('CREATE UNIQUE INDEX feature_name_lang ON feature_names (id, lang)')
            self.db.execute('CREATE UNIQUE INDEX feature_id ON features (id)')

        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('name', name))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('type', type))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('version', version))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('timestamp', timestamp))
        #self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('description', description))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('format', format))

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


    def putTile(self, zoom, x, y, content):
        tile_row = (2**zoom - 1) - y # Hello, Paul Ramsey.
        q = 'REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)'
        self.db.execute(q, (zoom, x, tile_row, memoryview(content)))


    def putName(self, name):
        h = hashlittle(name)
        if h in self.namehashes:
            return h
        q = 'REPLACE INTO names (ref, name) VALUES (?, ?)'
        self.db.execute(q, (h, name))
        return h


    def putFeature(self, id, tags, kind, label, geometry):
        h = self.putName(tags['name'])
        q = 'REPLACE INTO feature_names (id, lang, name) VALUES (?, ?, ?)'
        self.db.execute(q, (id, 0, h))
        if 'name:en' in tags:
            h = self.putName(tags['name:en'])
            self.db.execute(q, (id, 840, h))
        if 'name:de' in tags:
            h = self.putName(tags['name:de'])
            self.db.execute(q, (id, 276, h))
        if 'name:ru' in tags:
            h = self.putName(tags['name:ru'])
            self.db.execute(q, (id, 643, h))
        lat = None
        lon = None
        if label:
            geom = transform(mercator_to_wgs84, label)
            lat = geom.y
            lon = geom.x
        elif geometry.type == 'Point':
            geom = transform(mercator_to_wgs84, geometry)
            lat = geom.y
            lon = geom.x
        q = 'REPLACE INTO features (id, kind, lat, lon) VALUES (?, ?, ?, ?)'
        self.db.execute(q, (id, kind, lat, lon))
