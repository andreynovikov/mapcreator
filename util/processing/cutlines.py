import logging
from tqdm import tqdm
from shapely.geometry import CAP_STYLE
from shapely.errors import ShapelyError

from util.core import Element


BUFFER_RESOLUTION = 3


def process(elements, interactive):
    cutlines = []
    cutline_areas = []
    woods = []
    for element in elements:
        if 'man_made' in element.tags and element.tags['man_made'] == 'cutline':
            cutline_areas.append(element.geom.buffer(10, resolution=BUFFER_RESOLUTION, cap_style=CAP_STYLE.square))
            if len(element.tags) == 1 or (len(element.tags) == 2 and 'name' in element.tags):
                cutlines.append(element)
        if 'natural' in element.tags and element.tags['natural'] == 'wood':
            woods.append(element)

    # remove cut lines that are nothing else
    for element in cutlines:
        elements.remove(element)

    if not woods:
        return

    if interactive:
        progress = tqdm(total=len(woods), desc="Woods")
    else:
        logging.info("      subtract cut lines")

    for wood in woods:
        for cutline in cutline_areas:
            try:
                geom = wood.geom.intersection(cutline)
                if not geom.is_empty:
                    wood.geom = wood.geom.difference(cutline)
                    # this is not always true but makes map more readable
                    elements.append(Element(None, geom, {'natural': 'grassland'}, {'zoom-min': 14}))
            except ShapelyError:
                logging.error("failed to cut lines from %s", wood.osm_id())
        if interactive:
            # noinspection PyUnboundLocalVariable
            progress.update()
    if interactive:
        progress.close()

