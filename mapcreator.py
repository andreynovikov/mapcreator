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

    def __init__(self, data_dir, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.logger = logging.getLogger("mapcreator")
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self.mapWriter = mapwrite.MapWriter(self.data_dir, self.dry_run, self.verbose)

        index = open(configuration.MAP_TARGET_PATH + '/index', 'r+b')
        index.truncate(6*128*128)
        index.close()


    def selectPopularMap(self, percent, period):
        query = """
        SELECT * FROM (
            SELECT maps.area, date '1970-01-01' + created * interval '1 day' AS created FROM (
                SELECT area, percent_rank() OVER (ORDER BY downloads DESC) AS pct FROM (
                    SELECT area, SUM(downloads) AS downloads FROM map_downloads
                    --- consider only last 2 months of download statistics
                    WHERE month >= (date_part('year', now() - interval '2 months') * 100 + date_part('month', now() - interval '2 months'))::integer
                    GROUP BY area
                ) AS areas
            ) AS areas
            INNER JOIN maps ON (areas.area = maps.area)
            WHERE pct < %.2f AND error = FALSE
        ) AS areas
        WHERE age(created) > interval '%s'
        ORDER BY created
        LIMIT 1;
        """
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
        query = """
        SELECT * FROM (
            SELECT maps.area, date '1970-01-01' + created * interval '1 day' AS created FROM (
                SELECT area FROM map_downloads
                WHERE month >= (date_part('year', now() - interval '2 months') * 100 + date_part('month', now() - interval '2 months'))::integer
                GROUP BY area
            ) AS areas
            INNER JOIN maps ON (areas.area = maps.area)
            WHERE error = FALSE
        ) AS areas
        WHERE age(created) > interval '%s'
        ORDER BY created
        LIMIT 1;
        """
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
        query = """
        SELECT * FROM (
            SELECT area, date '1970-01-01' + created * interval '1 day' AS created FROM maps
            WHERE created > 0 AND error = FALSE
        ) AS areas
        WHERE age(created) > interval '%s'
        ORDER BY created
        LIMIT 1;
        """
        with psycopg2.connect(configuration.STATS_DB_DSN) as c:
            with c.cursor() as cur:
                cur.execute(query % (period))
                self.logger.debug(cur.query)
                if cur.rowcount > 0:
                    row = cur.fetchone()
                    self.logger.info("Selected map %s [%s]" % (row[0], row[1]))
                    return row[0]
        return None


    def loop(self):
        area = self.selectPopularMap(0.05, '2 weeks') or \
               self.selectPopularMap(0.1, '1 month') or \
               self.selectPopularMap(0.5, '2 months') or \
               self.selectDownloadedMap('2 months') or \
               self.selectAnyMap('4 months')
        if area is None:
            self.logger.debug("No maps to create")
            return
        (x, y) = map(int, area.split('-'))

        cost = time.time()
        try:
            map_path = self.mapWriter.createMap(x, y, True)
        except Exception as e:
            print("An error occurred:")
            print(e)
            if not self.dry_run:
                self.writeIndex(area, x, y, None, None, None, True)
            return
        cost = int(time.time() - cost)

        date = int(os.path.getmtime(map_path) / 3600 / 24)
        size = os.path.getsize(map_path)
        if not self.dry_run and size == 0:
            self.logger.error("Resulting map file size for %s is zero, keeping old map file" % map_path)
            self.writeIndex(area, x, y, None, None, None, True)
            return

        map_target_path = '{0:s}/{1:d}/{1:d}-{2:d}.map'.format(configuration.MAP_TARGET_PATH, x, y)
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
            with open(configuration.MAP_TARGET_PATH + '/index', 'r+b') as index:
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
    parser.add_argument('-p', '--data-path', default='data', help='base path for data files')
    parser.add_argument('-d', '--dry-run', action='store_true', help='do not generate any files')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose logging')
    args = parser.parse_args()

    sh = logging.StreamHandler()
    logger = logging.getLogger("mapcreator")
    formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    # during a dry run the console should receive all logs
    if args.dry_run or args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        mapCreator = MapCreator(args.data_path, args.dry_run, args.verbose)
        mapCreator.loop()
    except Exception as e:
        print("An error occurred:")
        print(e)
        import traceback
        traceback.print_exc()