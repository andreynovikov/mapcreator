#! /usr/bin/env python3

import os.path as path
import struct
import psycopg2

import configuration

"""
create table maps(area varchar(7), size integer not null default 0, cost integer not null default 0, created integer not null default 0, error boolean not null default false, primary key(area));
create index maps_created ON maps(created);
"""

with open(configuration.MAP_TARGET_PATH + '/index', 'wb') as f, psycopg2.connect(configuration.STATS_DB_DSN) as c:
    f.truncate(6*128*128)
    cur = c.cursor()
    for x in range(128):
        for y in range(128):
            map_path = '{0:s}/{1:d}/{1:d}-{2:d}.map'.format(configuration.MAP_TARGET_PATH, x, y)
            print(map_path)
            size = 0
            date = 0
            if not path.exists(map_path):
                print('    skip')
            else:
                try:
                    size = path.getsize(map_path)
                    mf = open(map_path, 'rb')
                    mf.seek(36, 0)
                    buf = mf.read(8)
                    mf.close()
                    date = int(struct.unpack(">Q", buf)[0] / 1000 / 3600 / 24)
                    #date = int(path.getmtime(map_path) / 3600 / 24)
                except OSError:
                    size = 0
                    date = 0
            print('    size: {0:d}'.format(size))
            #print('    date: {0:d}'.format(date))
            f.write((date).to_bytes(2, byteorder='big', signed=False))
            f.write((size).to_bytes(4, byteorder='big', signed=False))
            area = '{0:d}-{1:d}'.format(x, y)
            cur.execute("UPDATE maps SET size = %s, created = %s WHERE area = %s", (size, date, area))
            if cur.rowcount != 1:
                cur.execute("INSERT INTO maps (area, size, created) VALUES (%s, %s, %s)", (area, size, date))
    c.commit()
