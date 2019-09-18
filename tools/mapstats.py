#!/usr/bin/env python3

import os
import sys
import argparse
import inspect
import numpy as np
from collections import defaultdict
from tabulate import tabulate

import sqlite3


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from encoder import attrib_offset, TileData_pb2, StaticKeys, StaticVals

import configuration
import mappings

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


def print_stats(title, stats):
    print("")
    table = [ [t, float(v[0]), float(v[1]), float(v[2]), float(v[2] / v[0])] for t, v in stats.items() ]
    sorted_table = sort_table(table, 3)[:10]
    print(tabulate(sorted_table, [title, "Num", "Coords", "Size", "Avg.Size"], floatfmt=",.0f"))


def stat_zoom(zoom, cursor):
    print("")
    print("Zoom {:2d}".format(zoom))
    print("=======")

    unknown_values = defaultdict(int)
    tag_points = defaultdict(lambda: [0, 0, 0])
    tag_lines = defaultdict(lambda: [0, 0, 0])
    tag_polygons = defaultdict(lambda: [0, 0, 0])

    tile = TileData_pb2.Data()
    cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level = ?", (zoom,))
    for row in cursor:
        tile.ParseFromString(row[0])

        a = np.array(tile.tags)
        a.shape = (tile.num_tags, 2)

        if tile.num_vals > 0:
            for value in tile.values:
                unknown_values[value] += 1

        for point in tile.points:
            size = point.ByteSize()
            tags = []
            for tag_num in point.tags:
                k, v = tuple(a[tag_num])
                k = getKey(k)
                v = getValue(v)
                m = mappings.tags.get(k, {'__any__': {}})
                if not m.get(v, m.get('__any__', {})).get('render', True):
                    continue
                tags.append("{}:{}".format(k, v))
            tag = ','.join(sorted(tags))
            tag_points[tag][0] += 1
            tag_points[tag][1] += len(point.coordinates) >> 1
            tag_points[tag][2] += size

        for line in tile.lines:
            size = line.ByteSize()
            tags = []
            for tag_num in line.tags:
                k, v = tuple(a[tag_num])
                k = getKey(k)
                v = getValue(v)
                m = mappings.tags.get(k, {'__any__': {}})
                if not m.get(v, m.get('__any__', {})).get('render', True):
                    continue
                tags.append("{}:{}".format(k, v))
            tag = ','.join(sorted(tags))
            tag_lines[tag][0] += 1
            tag_lines[tag][1] += len(line.coordinates) >> 1
            tag_lines[tag][2] += size

        for polygon in tile.polygons:
            size = polygon.ByteSize()
            tags = []
            for tag_num in polygon.tags:
                k, v = tuple(a[tag_num])
                k = getKey(k)
                v = getValue(v)
                m = mappings.tags.get(k, {'__any__': {}})
                if not m.get(v, m.get('__any__', {})).get('render', True):
                    continue
                tags.append("{}:{}".format(k, v))
            tag = ','.join(sorted(tags))
            tag_polygons[tag][0] += 1
            tag_polygons[tag][1] += len(polygon.coordinates) >> 1
            tag_polygons[tag][2] += size

    print_stats("Points", tag_points)
    print_stats("Lines", tag_lines)
    print_stats("Polygons", tag_polygons)


def sort_table(table, col, reverse=True):
    return sorted(table, key=lambda k: float(k[col]), reverse=reverse)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Trekarta map inspector')
    parser.add_argument('-m', '--map-path', help='path to map file')
    args = parser.parse_args()

    #if len(sys.argv) != 2 :
    #    print("Usage: %s <osmtile>" % sys.argv[0], file=sys.stderr)
    #    sys.exit(1)

    # 69-41: 14/8852/5305
    mx = 74
    my = 37
    if not args.map_path:
        args.map_path = '{0:s}/{1:d}/{1:d}-{2:d}.mtiles'.format(configuration.MAP_TARGET_PATH, mx, my)
    if os.path.exists(args.map_path):
        with sqlite3.connect(args.map_path) as db:
            print("Table sizes")
            print("===========")
            cursor = db.cursor()
            cursor.execute("SELECT name, CAST(SUM(pgsize-unused) AS float), CAST(SUM(pgsize) AS float) FROM dbstat GROUP BY name")
            table_sizes = cursor.fetchall()
            print(tabulate(sort_table(table_sizes, 1), ["Table", "Size", "P.Size"], floatfmt=",.0f"))

            print("")
            print("Zoom level sizes")
            print("================")
            cursor = db.cursor()
            cursor.execute("SELECT zoom_level, CAST(SUM(LENGTH(tile_data)) AS float) FROM tiles GROUP BY zoom_level")
            zoom_sizes = cursor.fetchall()
            print(tabulate(sort_table(zoom_sizes, 0, False), ["Zoom", "Size"], floatfmt=",.0f"))

            for zoom in range(8, 15):
                stat_zoom(zoom, cursor)
            #cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", (z, x, y))
            #blob = cursor.fetchone()[0]
            #tile.ParseFromString(blob)
            #print_tile(tile)
