#! /usr/bin/env python3

import os.path as path

import configuration

f = open(configuration.MAP_TARGET_PATH + '/index', 'wb')
with f:
    f.truncate(6*128*128)
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
                    date = int(path.getmtime(map_path) / 3600 / 24)
                except OSError:
                    size = 0
                    date = 0
            print('    size: {0:d}'.format(size))
            #print('    date: {0:d}'.format(date))
            f.write((date).to_bytes(2, byteorder='big', signed=False))
            f.write((size).to_bytes(4, byteorder='big', signed=False))
    f.close()
