#!/usr/bin/python3

import re
from os import path
from datetime import datetime

import psycopg2

import configuration


map_file_path = configuration.MAP_TARGET_PATH + '/%s/%s.mtiles'

"""
217.66.157.187 - - [15/Jan/2019:07:44:49 +0300] "GET /maps/index?2844,1,3,24,33,0,104 HTTP/1.1" 200 98567 "-" "Dalvik/2.1.0 (Linux; U; Android 8.1.0; SM-N960F Build/M1AJQ)" 0.237 1 0
217.66.152.237 - - [01/Oct/2016:13:29:18 +0300] "GET /maps/74/74-37.map HTTP/1.1" 200 43869017 "-" "AndroidDownloadManager/6.0 (Linux; U; Android 6.0; FRD-L19 Build/HUAWEIFRD-L19)" 20.679 1 0
"""

ip = re.compile('^(\d+\.\d+\.\d+\.\d+) - - \[([^\]]+)\] "(.+) \/maps\/index\?([\d,]+) (.+)" (\d+) (\d+) "(.*?)" "(.*?)" ([\d\.]+) (\d+) (\d+)')
mp = re.compile('^(\d+\.\d+\.\d+\.\d+) - - \[([^\]]+)\] "(.+) \/maps\/\d+\/((\d+)-(\d+))\.(?:map|mtiles) (.+)" (\d+) (\d+) "(.*?)" "(.*?)" ([\d\.]+) (\d+) (\d+)')
ap = re.compile('^.+\(Linux; U; Android ([\d\.]+); (.+) [^\s]+\)')

sizes = {}
stats = []
hits = {}

def process_index(fields):
    # check HTTP status
    time = datetime.strptime(fields[1], '%d/%b/%Y:%H:%M:%S %z')
    data = [int(s) for s in fields[3].split(',')]
    if not filter(lambda s: s > 0, data):
        return
    m = ap.match(fields[8])
    if m:
        f = list(m.groups())
        f[0] = f[0][:10]
        f[1] = f[1][:20]
        data = f + data
    else:
        data = ['',''] + data
    data.insert(0, time)
    stats.append(data)
    print(' '.join(['{}'] * len(data)).format(*data))

def process_map(fields):
    # check HTTP status
    if fields[7] not in ['200', '206']:
        return
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
        try:
            size = path.getsize(filename)
            sizes[area] = size
        except FileNotFoundError:
            size = 0
    if size:
        # header size is 254-261 bytes
        ratio = (total - 258) / size
    else:  # no map (removed)
        ratio = 0
    areas = hits.get(month, None)
    if not areas:
        areas = {}
        hits[month] = areas
    stats = areas.get(area, 0)
    areas[area] = stats + ratio
    print("%d %d %d %f %f" % (month, int(x), int(y), ratio, seconds))


with open(configuration.MAP_DOWNLOAD_LOG, 'r') as f:
    for line in f:
        m = ip.match(line)
        if m:
            process_index(m.groups())
            continue
        m = mp.match(line)
        if m:
            process_map(m.groups())


"""
create table trekarta_stats(at timestamp not null, android varchar(10), model varchar(20), running_time integer, tracking_time integer,
                            waypoint_count integer, data_set_count integer, native_map_count integer, map_count integer, fullscreen_times integer,
                            hiking_times integer, skiing_times integer);
create table map_downloads(month integer, area varchar(7), downloads real, primary key(month, area));
"""

with psycopg2.connect(configuration.STATS_DB_DSN) as c:
    cur = c.cursor()
    for line in stats:
        if len(line) < 12:
            line.extend([0] * (12 - len(line)))
        cur.execute("INSERT INTO trekarta_stats VALUES (%s)" % ', '.join(['%s'] * len(line)), line)
    c.commit()
    cur = c.cursor()
    for month in hits:
        for area in hits[month]:
            downloads = round(hits[month][area], 5)
            cur.execute("UPDATE map_downloads SET downloads = downloads + %s WHERE month = %s AND area = %s", (downloads, month, area))
            if cur.rowcount != 1:
                cur.execute("INSERT INTO map_downloads (month, area, downloads) VALUES (%s, %s, %s)", (month, area, downloads))
    c.commit()
