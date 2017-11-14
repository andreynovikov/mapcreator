#!/usr/bin/env python3

import os
import sys
import inspect
import time
import argparse
import logging.config

from sqlite3 import connect
from tqdm import tqdm

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

import configuration


class HillShadeCreator:

    def __init__(self, tiles_file, maps_dir, noninteractive=False):
        self.noninteractive = noninteractive
        self.logger = logging.getLogger("mapcreator")
        self.tiles_file = tiles_file
        self.maps_dir = maps_dir
        self.replace_query = 'REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)'
        self.select_query = 'SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?'

    def createArea(self, x, y):
        name = "%d-%d hillshade" % (x, y)
        output_dir = os.path.join(self.maps_dir, str(x))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filename = os.path.join(output_dir, '%d-%d.mbtiles' % (x, y))
        timestamp = int(os.path.getmtime(self.tiles_file) / 3600 / 24)

        if self.noninteractive:
            self.logger.debug("Creating %s" % filename)

        self.src_db = connect(self.tiles_file)
        self.db = connect(filename)
        self.db.execute('PRAGMA journal_mode = OFF')
        self.db.execute('PRAGMA synchronous = NORMAL')
        # check if database already exists
        try:
            self.db.execute('SELECT name, value FROM metadata LIMIT 1')
            self.db.execute('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT 1')
            self.db.execute('DELETE FROM metadata')
        except:
            self.db.execute('PRAGMA application_id = 0x4d504258')
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
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('minzoom', '8'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('maxzoom', '12'))
        self.db.execute('INSERT INTO metadata VALUES (?, ?)', ('tile_row_type', 'xyz'))

        self.db.commit()
        self.db.text_factory = bytes

        self.saveTile(7, x, y)

        self.db.commit()
        self.db.execute('VACUUM')
        self.db.close()
        self.db = None
        self.src_db.close()
        self.src_db = None

    def saveTile(self, zoom, x, y):
        if zoom > 7:
            if self.noninteractive:
                self.logger.debug("Saving tile %d/%d/%d" % (zoom, x, y))
            tile_row = (2**zoom - 1) - y # Hello, Paul Ramsey
            cur = self.src_db.cursor()
            cur.execute(self.select_query, (zoom, x, tile_row))
            row = cur.fetchone()
            if row is None:
                self.logger.error("Tile does not exist: %d/%d/%d" % (zoom, x, y))
            else:
                self.db.execute(self.replace_query, (zoom, x, y, memoryview(row[0])))
            cur.close()
        if zoom < 12:
            nx = x << 1
            ny = y << 1
            nz = zoom + 1
            self.saveTile(nz, nx,   ny)
            self.saveTile(nz, nx,   ny+1)
            self.saveTile(nz, nx+1, ny)
            self.saveTile(nz, nx+1, ny+1)


def mapinfo(maps_path, x, y):
    map_path = '{0:s}/{1:d}/{1:d}-{2:d}.mbtiles'.format(maps_path, x, y)
    size = 0
    if os.path.exists(map_path):
        size = os.path.getsize(map_path)
    return size


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek hillshade layer creator')
    parser.add_argument('-t', '--tiles-db', default=configuration.HILLSHADE_TILES_DB, help='source hillshade tiles database')
    parser.add_argument('-m', '--maps-path', default=configuration.HILLSHADE_TARGET_PATH, help='path for generated maps')
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    parser.add_argument('-i', '--index', action='store_true', help='generate index')
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
        hsCreator = HillShadeCreator(args.tiles_db, args.maps_path, args.noninteractive)
        if args.area:
            (x, y) = map(int, args.area.split('-'))
            hsCreator.createArea(x, y)
        elif not args.index:
            if not args.noninteractive:
                gen_progress = tqdm(total=128*(89-26), desc="Generated")
            for x in range(128):
                for y in range(26, 89):
                    hsCreator.createArea(x, y)
                    if not args.noninteractive:
                        gen_progress.update()
            if not args.noninteractive:
                gen_progress.close()
        if args.index:
            with open(args.maps_path + '/index', 'wb') as f:
                f.truncate(5*128*128)
                for x in range(128):
                    for y in range(128):
                        size = mapinfo(args.maps_path, x, y)
                        f.write((configuration.HILLSHADE_VERSION).to_bytes(1, byteorder='big', signed=False))
                        f.write((size).to_bytes(4, byteorder='big', signed=False))
    except Exception as e:
        logger.exception("An error occurred:")
