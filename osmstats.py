#!/usr/bin/python3

import argparse
import logging.config
from operator import itemgetter

import osmium

import configuration
import mappings


class OsmFilter(osmium.SimpleHandler):

    def __init__(self, logger):
        super(OsmFilter, self).__init__()
        self.logger = logger
        self.mapped = {}
        self.values = {}

    def filter(self, tags):
        filtered_tags = {}
        renderable = False
        for tag in tags:
            if tag.k in mappings.tags.keys():
                from_any = True
                m = mappings.tags[tag.k].get('__any__', None)
                if m is None:
                    m = mappings.tags[tag.k].get(tag.v, None)
                    from_any = False
                if m is not None: #empty dictionaries should be also accounted
                    k = tag.k
                    v = tag.v
                    if 'rewrite-key' in m or 'rewrite-value' in m:
                        k = m.get('rewrite-key', k)
                        v = m.get('rewrite-value', v)
                        m = mappings.tags.get(k, {}).get(v, {})
                    if 'one-of' in m:
                        if v not in m['one-of']:
                            continue
                    if 'adjust' in m:
                        v = m['adjust'](v)
                    if v is None:
                        continue
                    filtered_tags[k] = v
                    renderable_tag = m.get('render', True)
                    renderable = renderable or renderable_tag
                    if renderable_tag:
                        if from_any:
                            mapping = k
                        else:
                            mapping = k + ":" + v
                        self.mapped[mapping] = self.mapped.get(mapping, 0) + 1
        if renderable:
            for k, v in filtered_tags.items():
                if k not in ['addr:housenumber', 'name', 'ref', 'height', 'min_height', 'building:levels', 'building:min_level']:
                    self.values[v] = self.values.get(v, 0) + 1

    def node(self, n):
        self.filter(n.tags)

    def way(self, w):
        self.filter(w.tags)

    def relation(self, r):
        self.filter(r.tags)


class MapStatistics:

    def __init__(self, pbf_file):
        self.logger = logging.getLogger(__name__)
        self.pbf_file = pbf_file

    def collect(self):
        self.logger.info("Collecting statistics from: %s" % self.pbf_file)

        handler = OsmFilter(self.logger)
        handler.apply_file(self.pbf_file)
        for k, v in sorted(handler.mapped.items(), key=itemgetter(1), reverse=True):
            print('{:35s} {:10,d}'.format(k, v))

        print("")

        i = 1
        for k, v in sorted(handler.values.items(), key=itemgetter(1), reverse=True):
            print('{:<3d} {:35s} {:10,d}'.format(i, str(k), v))
            i = i + 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MapTrek map data statistics')
    parser.add_argument('-f', '--file', type=str, help='use specified pbf file as data source instead of configured')
    args = parser.parse_args()

    pbf_file = configuration.SOURCE_PBF
    if args.file:
        pbf_file = args.file

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    try:
        statistics = MapStatistics(pbf_file)
        statistics.collect()
    except Exception as e:
        print("An error occurred:")
        print(e)
