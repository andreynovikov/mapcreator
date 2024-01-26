import logging
import json
from collections import defaultdict

from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.geometry import mapping as geom_mapping
from shapely.ops import cascaded_union
from shapely.ops import transform
from shapely.prepared import prep
from tqdm import tqdm

from util.core import Element
from util.geometry import mercator_to_wgs84


BUFFER_RESOLUTION = 3

# playground and snow-park are piste types, but are (temporary) converted to difficulties
# for processing
difficulties = ['playground', 'snow_park', 'novice', 'easy', 'intermediate', 'advanced',
                'expert', 'freeride', 'extreme', 'unknown']
groomings = ['unknown', 'mogul', 'backcountry']

piste_mapping = {'zoom-min': 12}
labeled_piste_mapping = {'zoom-min': 13, 'label': True}
border_mapping = {'zoom-min': 12}


def multidimentiondict(n, leaf_type):
    """ Creates an n-dimension dictionary where the n-th dimension is of type 'type' """
    if n <= 1:
        return leaf_type()
    return defaultdict(lambda: multidimentiondict(n-1, leaf_type))


class Piste:
    def __init__(self, el_id, area, geom, difficulty=None, grooming=None):
        self.id = el_id
        self.area = area
        if not area:
            geom = geom.buffer(10, resolution=BUFFER_RESOLUTION)
        self.geom = geom
        self.difficulty = difficulty
        self.grooming = grooming
        self.point = geom.representative_point()
        self.borders = None

    def __str__(self):
        return "%d %s %s" % (self.id, self.difficulty, self.grooming)


class Resort:
    def __init__(self, piste):
        # union of all pistes
        self.geom = Polygon()
        # union of area pistes
        self.area = Polygon()
        # list of all pistes combined by difficulty
        self.pistes = multidimentiondict(3, list)
        # united piste areas combined by difficulty, used in post-processing
        self.areas = multidimentiondict(3, Polygon)
        # united piste borders combined by difficulty, used in post-processing
        self.borders = multidimentiondict(3, LineString)
        self.prepared = None

        self.add(piste)
        self.point = piste.point

    def add(self, piste):
        if piste.area:
            self.area = cascaded_union([self.area, piste.geom])
        self.pistes[piste.difficulty][piste.grooming].append(piste)
        self.geom = cascaded_union([self.geom, piste.geom])
        self.prepared = prep(self.geom)

    def check(self, piste):
        if self.point.distance(piste.point) > 100000:  # do not consider pistes more then 100km away
            return False
        if self.geom.distance(piste.geom) < 10:
            return True
        return self.prepared.contains(piste.geom) or self.prepared.intersects(piste.geom)  # 'contains' is much faster

    def combine(self, resort):
        for difficulty in resort.pistes:
            for grooming in resort.pistes[difficulty]:
                self.pistes[difficulty][grooming].extend(resort.pistes[difficulty][grooming])
        self.area = cascaded_union([self.area, resort.area])
        self.geom = cascaded_union([self.geom, resort.geom])
        self.prepared = prep(self.geom)


def process(elements, interactive):
    pistes = []
    resorts = []
    areas = []
    for element in elements:
        if 'piste:type' not in element.tags:
            continue
        if 'lit' in element.tags and 'piste:lit' not in element.tags:
            element.tags['piste:lit'] = element.tags['lit']
        if element.tags['piste:type'] not in ['downhill', 'snow_park', 'playground']:
            continue
        difficulty = element.tags.get('piste:difficulty', 'unknown')
        if element.tags['piste:type'] in ['snow_park', 'playground']:
            difficulty = element.tags['piste:type']
        grooming = element.tags.get('piste:grooming', 'unknown')
        if difficulty not in difficulties:
            difficulty = 'unknown'
        if grooming not in groomings:
            grooming = 'unknown'
        is_area = element.geom.type in ['Polygon', 'MultiPolygon']
        piste = Piste(element.id, is_area, element.geom, difficulty, grooming)
        pistes.append(piste)
        if is_area:
            areas.append(element)

    for element in areas:
        elements.remove(element)

    if interactive:
        progress = tqdm(total=len(pistes), desc="Pistes")
    else:
        logging.info("      group %d pistes", len(pistes))
    for piste in pistes:
        piste_resorts = []
        for resort in resorts:
            if resort.check(piste):
                piste_resorts.append(resort)
        if piste_resorts:
            piste_resorts[0].add(piste)
            for resort in piste_resorts[1:]:
                piste_resorts[0].combine(resort)
                resorts.remove(resort)
        else:
            resorts.append(Resort(piste))
        if interactive:
            # noinspection PyUnboundLocalVariable
            progress.update()
    if interactive:
        progress.close()

    if interactive:
        progress = tqdm(total=len(resorts) * len(difficulties) * len(groomings), desc="Resorts")
    else:
        logging.info("      process %d resorts", len(resorts))
    for resort in resorts:
        resort.geom = resort.geom.buffer(1.7, resolution=BUFFER_RESOLUTION)
        geoms = []
        for difficulty in difficulties:
            if not resort.pistes[difficulty]:
                if interactive:
                    progress.update(len(groomings))
                continue
            for grooming in groomings:
                if interactive:
                    progress.update()
                if not resort.pistes[difficulty][grooming]:
                    continue
                pistes = []
                for piste in resort.pistes[difficulty][grooming]:
                    if not piste.area:
                        piste.geom = piste.geom.difference(resort.area)
                    if piste.geom.is_empty:
                        continue
                    pistes.append(piste.geom)
                # noinspection PyBroadException
                try:
                    resort.areas[difficulty][grooming] = cascaded_union(pistes)
                except Exception:
                    logging.error("-------------------------------------------------------")
                    for piste in pistes:
                        # noinspection PyBroadException
                        try:
                            if resort.areas[difficulty][grooming]:
                                resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].union(piste.buffer(1))
                                # piste = piste.buffer(2)
                                # resort.areas[difficulty][grooming] = cascaded_union([ resort.areas[difficulty][grooming], piste])
                                # resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(-2)
                            else:
                                resort.areas[difficulty][grooming] = piste.buffer(1)
                        except Exception:
                            geom = transform(mercator_to_wgs84, resort.areas[difficulty][grooming])
                            logging.error("---------------")
                            print(json.dumps(geom_mapping(geom)))
                            geom = transform(mercator_to_wgs84, piste.buffer(1))
                            logging.error("---------------")
                            print(json.dumps(geom_mapping(geom)))
                            logging.error("---------------")
                    resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(-1)
                resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(5, resolution=BUFFER_RESOLUTION)
                resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(-3)
                resort.borders[difficulty][grooming] = resort.areas[difficulty][grooming].boundary
                for geom in geoms:
                    resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].difference(geom)
                    # filter out bits and bobs
                    if type(resort.areas[difficulty][grooming]) == MultiPolygon:
                        resort.areas[difficulty][grooming] = MultiPolygon([
                            polygon for polygon in resort.areas[difficulty][grooming].geoms if polygon.area > 0.1
                        ])
                geoms.append(resort.areas[difficulty][grooming])
        for difficulty in resort.areas:
            for grooming in resort.areas[difficulty]:
                resort.areas[difficulty][grooming] = resort.areas[difficulty][grooming].buffer(0.001)
        for borders_difficulty in resort.borders:
            for borders_grooming in resort.borders[borders_difficulty]:
                for pistes_difficulty in resort.areas:
                    for pistes_grooming in resort.areas[pistes_difficulty]:
                        if resort.borders[borders_difficulty][borders_grooming].is_empty:
                            continue
                        if borders_difficulty == pistes_difficulty and borders_grooming == pistes_grooming:
                            continue
                        borders = resort.borders[borders_difficulty][borders_grooming]
                        borders = borders.difference(resort.areas[pistes_difficulty][pistes_grooming])
                        resort.borders[borders_difficulty][borders_grooming] = borders
    if interactive:
        progress.close()

    for resort in resorts:
        for difficulty in resort.areas:
            for grooming in resort.areas[difficulty]:
                if resort.areas[difficulty][grooming].is_empty:
                    continue
                if difficulty in ['snow_park', 'playground']:
                    tags = {'piste:type': difficulty}
                    mapping = labeled_piste_mapping
                else:
                    tags = {'piste:type': 'downhill', 'piste:difficulty': difficulty}
                    mapping = piste_mapping
                if grooming != 'unknown':
                    tags['piste:grooming'] = grooming
                elements.append(Element(None, resort.areas[difficulty][grooming], tags, mapping))
                if resort.borders[difficulty][grooming].is_empty:
                    continue
                if difficulty in ['snow_park', 'playground']:
                    tags = {'piste:border': difficulty}
                else:
                    tags = {'piste:border': 'downhill', 'piste:difficulty': difficulty}
                if grooming != 'unknown':
                    tags['piste:grooming'] = grooming
                elements.append(Element(None, resort.borders[difficulty][grooming], tags, border_mapping))
