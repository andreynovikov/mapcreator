#!/usr/bin/python3

import re
from os import path
from datetime import datetime

import psycopg2

import configuration


map_file_path = configuration.MAP_TARGET_PATH + '/%s/%s.map'

"""
217.66.152.237 - - [01/Oct/2016:13:29:18 +0300] "GET /maps/74/74-37.map HTTP/1.1" 200 43869017 "-" "AndroidDownloadManager/6.0 (Linux; U; Android 6.0; FRD-L19 Build/HUAWEIFRD-L19)" 20.679 1 0
"""

p = re.compile('^(\d+\.\d+\.\d+\.\d+) - - \[([^\]]+)\] "(.+) \/maps\/\d+\/((\d+)-(\d+))\.(?:map|mtiles) (.+)" (\d+) (\d+) "(.*?)" "(.*?)" ([\d\.]+) (\d+) (\d+)')

sizes = {}
hits = {}

with open(configuration.MAP_DOWNLOAD_LOG, 'r') as f:
    for line in f:
        m = p.match(line)
        if not m:
            continue
        fields = m.groups()
        # check HTTP status
        if fields[7] not in ['200', '206']:
            continue
        time = datetime.strptime(fields[1], '%d/%b/%Y:%H:%M:%S %z')
        month = time.year * 100 + time.month
        area = fields[3]
        x = fields[4]
        y = fields[5]
        total = int(fields[8])
        seconds = float(fields[11])
        size = sizes.get(area, None)
        if not size:
            filename = map_file_path % (x, area)
            size = path.getsize(filename)
            sizes[area] = size
        # header size is 254-261 bytes
        ratio = (total - 258) / size
        areas = hits.get(month, None)
        if not areas:
            areas = {}
            hits[month] = areas
        stats = areas.get(area, 0)
        areas[area] = stats + ratio
        print("%d %d %d %f %f" % (month, int(x), int(y), ratio, seconds))

"""
create table map_downloads(month integer, area varchar(7), downloads real, primary key(month, area));
"""

with psycopg2.connect(configuration.STATS_DB_DSN) as c:
    cur = c.cursor()
    for month in hits:
        for area in hits[month]:
            downloads = round(hits[month][area], 5)
            cur.execute("UPDATE map_downloads SET downloads = downloads + %s WHERE month = %s AND area = %s", (downloads, month, area))
            if cur.rowcount != 1:
                cur.execute("INSERT INTO map_downloads (month, area, downloads) VALUES (%s, %s, %s)", (month, area, downloads))
    c.commit()
