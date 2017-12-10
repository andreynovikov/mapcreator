#!/usr/bin/env python3

import os
import sys
import argparse
import inspect
import numpy as np
from collections import defaultdict

import sqlite3

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from encoder import attrib_offset, TileData_pb2, StaticKeys, StaticVals

import configuration


keys = {v: k for k, v in StaticKeys.staticKeys.items()}
vals = {v: k for k, v in StaticVals.staticValues.items()}


def getKey(k):
    if k < attrib_offset:
        return keys[k]
    else:
        return k


def getValue(v):
    if v < attrib_offset:
        return vals[v]
    else:
        return v


def print_tile(tile):
    tags = defaultdict(int)
    a = np.array(tile.tags)
    a.shape = (tile.num_tags, 2)
    if tile.num_vals > 0:
        print("Values:")
        for value in tile.values:
            print(value)
    print("")
    for point in tile.points:
        for tag in point.tags:
            tags[tuple(a[tag])] += 2
    for line in tile.lines:
        for tag in line.tags:
            tags[tuple(a[tag])] += len(line.coordinates)
    for polygon in tile.polygons:
        for tag in polygon.tags:
            tags[tuple(a[tag])] += len(polygon.coordinates)
    print("Coordinates:")
    for item in sorted(tags.items(), key=lambda x: x[1], reverse=True):
        t, n = item
        k, v = t
        print("%s: %s - %d" % (getKey(k), getValue(v), n))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek tile inspector')
    parser.add_argument('-m', '--map-path', help='path to map file')
    args = parser.parse_args()

    #if len(sys.argv) != 2 :
    #    print("Usage: %s <osmtile>" % sys.argv[0], file=sys.stderr)
    #    sys.exit(1)

    tile = TileData_pb2.Data()

    # 69-41: 14/8852/5305
    mx = 68
    my = 44
    z = 12
    x = 2187
    y = 1432
    if not args.map_path:
        args.map_path = '{0:s}/{1:d}/{1:d}-{2:d}.mtiles'.format(configuration.MAP_TARGET_PATH, mx, my)
    if os.path.exists(args.map_path):
        with sqlite3.connect(args.map_path) as db:
            cursor = db.cursor()
            cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", (z, x, y))
            blob = cursor.fetchone()[0]
            tile.ParseFromString(blob)
            print_tile(tile)
