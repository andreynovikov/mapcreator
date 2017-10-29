#!/usr/bin/python3

import os
import sys
import time
import argparse
import logging.config

from sqlite3 import connect

import configuration

class HillShadeCreator:

    def __init__(self, tiles_dir, maps_dir, noninteractive=False):
        self.noninteractive = noninteractive
        self.logger = logging.getLogger("mapcreator")
        self.tiles_dir = tiles_dir
        self.maps_dir = maps_dir
        self.query = 'REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)'


    def createArea(self, x, y):
        name = "%d-%d hillshade" % (x, y)
        output_dir = os.path.join(self.maps_dir, str(x))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filename = os.path.join(output_dir, '%d-%d.mbtiles' % (x, y))
        timestamp = int(os.path.getmtime(self.tiles_dir) / 3600 / 24)

        if self.noninteractive:
            self.logger.debug("Creating %s" % filename)

        self.db = connect(filename)
        self.db.execute('PRAGMA journal_mode = OFF')
        self.db.execute('PRAGMA synchronous = NORMAL')
        self.db.execute('PRAGMA application_id = 0x4d504258')
        # check if database already exists
        try:
            self.db.execute('SELECT name, value FROM metadata LIMIT 1')
            self.db.execute('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT 1')
            self.db.execute('DELETE FROM metadata')
        except:
            self.db.execute('CREATE TABLE metadata (name TEXT NOT NULL, value TEXT)')
            self.db.execute('CREATE TABLE tiles (zoom_level INTEGER NOT NULL, tile_column INTEGER NOT NULL, tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL)')
            self.db.execute('CREATE UNIQUE INDEX coord ON tiles (zoom_level, tile_column, tile_row)')
            self.db.execute('CREATE UNIQUE INDEX property ON metadata (name)')

        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('name', name))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('type', 'overlay'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('version', '1'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('description', 'MapTrek hillshade layer'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('timestamp', timestamp))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('format', 'png'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('minzoom', '12'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('maxzoom', '12'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('scheme', 'tms'))

        self.db.commit()
        self.db.text_factory = bytes

        self.saveTile(7, x, y)

        self.db.commit()
        self.db.execute('VACUUM')
        self.db.close()
        self.db = None

    def saveTile(self, zoom, x, y):
        if zoom > 7:
            if self.noninteractive:
                self.logger.debug("Saving tile %d/%d/%d" % (zoom, x, y))
            tilepath = os.path.join(self.tiles_dir, str(zoom), str(x), '%d.png' % y)
            if os.path.exists(tilepath):
                with open(tilepath, 'rb') as f:
                    tile = f.read()
                    tile_row = (2**zoom - 1) - y # Hello, Paul Ramsey
                    self.db.execute(self.query, (zoom, x, tile_row, memoryview(tile)))
            else:
                self.logger.error("Tile does not exist: %d/%d/%d" % (zoom, x, y))
        if zoom < 12:
            nx = x << 1
            ny = y << 1
            nz = zoom + 1
            self.saveTile(nz, nx,   ny)
            self.saveTile(nz, nx,   ny+1)
            self.saveTile(nz, nx+1, ny)
            self.saveTile(nz, nx+1, ny+1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek hillshade layer creator')
    parser.add_argument('-t', '--tiles-path', default=configuration.HILLSHADE_TILES_PATH, help='path for source hillshade tile files')
    parser.add_argument('-m', '--maps-path', default=configuration.HILLSHADE_MAPS_PATH, help='do not generate any files')
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    parser.add_argument('-n', '--noninteractive', action='store_true', help='forbid interactive mode')
    parser.add_argument('-a', '--area', help='create specific area')
    args = parser.parse_args()

    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        print("Invalid log level: %s" % args.log)
        exit(1)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    try:
        hsCreator = HillShadeCreator(args.tiles_path, args.maps_path, args.noninteractive)
        if args.area:
            (x, y) = map(int, args.area.split('-'))
            hsCreator.createArea(x, y)
        else:
            for x in range(128):
                for y in range(128):
                    hsCreator.createArea(x, y)
    except Exception as e:
        logger.exception("An error occurred:")
