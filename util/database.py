from os.path import exists
from sqlite3 import connect

from shapely.ops import transform

from util.geometry import mercator_to_wgs84
from util.jenkins import hashlittle

class MTilesDatabase():
    def __init__(self, filename):
        self.filename = filename
        self.namehashes = []

    def create(self, name, type, version, format, bounds=None):
        self.db = connect(self.filename, check_same_thread=False)
        # check if database already exists
        try:
            self.db.execute('SELECT name, value FROM metadata LIMIT 1')
            self.db.execute('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT 1')
            self.db.execute('DELETE FROM metadata')
        except:
            self.db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
            self.db.execute('CREATE TABLE tiles (zoom_level INTEGER NOT NULL, tile_column INTEGER NOT NULL, tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL)')
            self.db.execute('CREATE TABLE names (ref INTEGER NOT NULL, name TEXT NOT NULL)')
            self.db.execute('CREATE TABLE features(id INTEGER NOT NULL, name INTEGER NOT NULL, lat REAL, lon REAL)')
            self.db.execute('CREATE UNIQUE INDEX coord ON tiles (zoom_level, tile_column, tile_row)')
            self.db.execute('CREATE UNIQUE INDEX property ON metadata (name)')
            self.db.execute('CREATE UNIQUE INDEX name_ref ON names (ref)')
            self.db.execute('CREATE UNIQUE INDEX feature_ref ON features (id, name)')

        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('name', name))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('type', type))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('version', version))
        #self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('description', description))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('format', format))

        if bounds is not None:
            self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('bounds', bounds))

        self.db.commit()
        self.db.text_factory = bytes

    def finish(self):
        self.db.commit()
        self.db.execute('VACUUM')
        self.db.close()
        self.db = None

    def putTile(self, zoom, x, y, content):
        tile_row = (2**zoom - 1) - y # Hello, Paul Ramsey.
        q = 'REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)'
        self.db.execute(q, (zoom, x, tile_row, memoryview(content)))
        self.db.commit()

    def putName(self, name):
        h = hashlittle(name)
        if h in self.namehashes:
            return h
        q = 'REPLACE INTO names (ref, name) VALUES (?, ?)'
        self.db.execute(q, (h, name))
        self.db.commit()
        return h

    def putFeature(self, id, name, label, geometry):
        h = self.putName(name)
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
        q = 'REPLACE INTO features (id, name, lat, lon) VALUES (?, ?, ?, ?)'
        self.db.execute(q, (id, h, lat, lon))
        self.db.commit()
