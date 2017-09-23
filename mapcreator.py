#!/usr/bin/python3

import os
import sys
import time
import argparse
import subprocess
import logging.config

import psycopg2

import mapwrite
import configuration

class MapCreator:

    def __init__(self, data_dir, dry_run=False, forbid_interactive=False):
        self.dry_run = dry_run
        self.forbid_interactive = forbid_interactive
        self.logger = logging.getLogger("mapcreator")
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        self.mapWriter = mapwrite.MapWriter(self.data_dir, self.dry_run, self.forbid_interactive)

        index = open(configuration.MAP_TARGET_PATH + '/nativeindex', 'r+b')
        index.truncate(6*128*128+6)
        index.close()


    def selectPopularMap(self, percent, period):
        query = "SELECT * FROM popular_map(%.2f, interval '%s') LIMIT 1;"
        with psycopg2.connect(configuration.STATS_DB_DSN) as c:
            with c.cursor() as cur:
                cur.execute(query % (percent, period))
                self.logger.debug(cur.query)
                if cur.rowcount > 0:
                    row = cur.fetchone()
                    self.logger.info("Selected map %s [%s] by popularity %.2f" % (row[0], row[1], percent))
                    return row[0]
        return None


    def selectDownloadedMap(self, period):
        query = "SELECT * FROM downloaded_map(interval '%s') LIMIT 1;"
        with psycopg2.connect(configuration.STATS_DB_DSN) as c:
            with c.cursor() as cur:
                cur.execute(query % (period))
                self.logger.debug(cur.query)
                if cur.rowcount > 0:
                    row = cur.fetchone()
                    self.logger.info("Selected map %s [%s] by download status" % (row[0], row[1]))
                    return row[0]
        return None


    def selectAnyMap(self, period):
        query = "SELECT * FROM any_map(interval '%s') LIMIT 1;"
        with psycopg2.connect(configuration.STATS_DB_DSN) as c:
            with c.cursor() as cur:
                cur.execute(query % (period))
                self.logger.debug(cur.query)
                if cur.rowcount > 0:
                    row = cur.fetchone()
                    self.logger.info("Selected map %s [%s]" % (row[0], row[1]))
                    return row[0]
        return None


    def loop(self, area):
        if not area:
            area = self.selectPopularMap(0.05, '1 week') or \
                   self.selectPopularMap(0.1, '2 weeks') or \
                   self.selectPopularMap(0.5, '3 weeks') or \
                   self.selectDownloadedMap('1 month') or \
                   self.selectAnyMap('2 months')

        if area is None:
            self.logger.debug("No maps to create")
            return
        (x, y) = map(int, area.split('-'))

        cost = time.time()
        try:
            map_path = self.mapWriter.createMap(x, y, True, False, True)
        except Exception as e:
            print("An error occurred:")
            print(e)
            if not self.dry_run:
                self.writeIndex(area, x, y, None, None, None, True)
            return
        cost = int(time.time() - cost)

        map_target_path = '{0:s}/{1:d}/{1:d}-{2:d}.mtiles'.format(configuration.MAP_TARGET_PATH, x, y)

        if map_path is None:
            self.logger.info("Empty map, skipping")
            if not self.dry_run:
                self.writeIndex(area, x, y, 0, cost, 0)
                if os.path.exists(map_target_path):
                    os.remove(map_target_path)
                    self.logger.info("  removed previously not empty map")
            return

        date = int(os.path.getmtime(map_path) / 3600 / 24)
        size = os.path.getsize(map_path)
        if not self.dry_run and size == 0:
            self.logger.error("Resulting map file size for %s is zero, keeping old map file" % map_path)
            self.writeIndex(area, x, y, None, None, None, True)
            return

        move_call = ["mv", map_path, map_target_path]
        self.logger.debug("calling: %s"," ".join(move_call))
        if not self.dry_run:
            try:
                subprocess.check_call(move_call)
            except Exception as e:
                print("Failed to move created map %s to target directory" % map_path)
                print(e)
                self.writeIndex(area, x, y, None, None, None, True)
                return
            self.writeIndex(area, x, y, size, cost, date)


    def writeIndex(self, area, x, y, size, cost, date, error=False):
        if error:
            with psycopg2.connect(configuration.STATS_DB_DSN) as c:
                with c.cursor() as cur:
                    cur.execute("UPDATE maps SET error = %s WHERE area = %s", (error, area))
                    if cur.rowcount != 1:
                        cur.execute("INSERT INTO maps (area, error) VALUES (%s, %s)", (area, error))
                    self.logger.debug(cur.query)
                c.commit()
        else:
            with open(configuration.MAP_TARGET_PATH + '/nativeindex', 'r+b') as index:
                index.seek((x * 128 + y) * 6)
                index.write((date).to_bytes(2, byteorder='big', signed=False))
                index.write((size).to_bytes(4, byteorder='big', signed=False))
            with psycopg2.connect(configuration.STATS_DB_DSN) as c:
                with c.cursor() as cur:
                    cur.execute("UPDATE maps SET size = %s, cost = %s, created = %s, error = %s WHERE area = %s", (size, cost, date, error, area))
                    if cur.rowcount != 1:
                        cur.execute("INSERT INTO maps (area, size, cost, created) VALUES (%s, %s, %s, %s)", (area, size, cost, date))
                    self.logger.debug(cur.query)
                c.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek map creation daemon')
    parser.add_argument('-p', '--data-path', default=configuration.DATA_PATH, help='base path for data files')
    parser.add_argument('-d', '--dry-run', action='store_true', help='do not generate any files')
    parser.add_argument('-l', '--log', default='ERROR', help='set logging verbosity')
    parser.add_argument('-n', '--noninteractive', action='store_true', help='forbid interactive mode')
    parser.add_argument('-z', '--daemonize', action='store_true', help='run as a daemon')
    parser.add_argument('-a', '--area', help='create specific area')
    args = parser.parse_args()

    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        print("Invalid log level: %s" % args.log)
        exit(1)

    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    # during a dry run the console should receive all logs
    if args.dry_run:
        logger.setLevel(logging.DEBUG)

    try:
        mapCreator = MapCreator(args.data_path, args.dry_run, args.noninteractive)
        if args.daemonize:
            import daemon
            import lockfile
            context = daemon.DaemonContext(
                working_directory='/tmp/mapcreator',
                pidfile=lockfile.FileLock('/var/run/mapcreator.pid'),
            )
            with context:
                while True:
                    mapCreator.loop()
                    time.sleep(5)
        else:
            mapCreator.loop(args.area)
    except Exception as e:
        logger.exception("An error occurred:")
