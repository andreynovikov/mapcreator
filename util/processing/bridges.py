import logging
from tqdm import tqdm
from shapely.geometry import CAP_STYLE
from shapely.prepared import prep
from shapely.errors import ShapelyError

from util.core import Element


BUFFER_RESOLUTION = 3


def process(elements, interactive):
    bridges = []
    rivers = []
    drop_elements = []
    for element in elements:
        if 'man_made' in element.tags and element.tags['man_made'] == 'bridge' and element.geom.area > 0:
            bridges.append(element.geom)
        if 'waterway' in element.tags and element.tags['waterway'] == 'river':
            rivers.append(element)

    if not bridges or not rivers:
        return

    if interactive:
        progress = tqdm(total=len(rivers), desc="Rivers")
    else:
        logging.info("      subtract %d bridges from %d rivers", len(bridges), len(rivers))

    for river in rivers:
        prepared_river = prep(river.geom)
        for bridge in bridges:
            try:
                if prepared_river.intersects(bridge):
                    geom = river.geom.intersection(bridge)
                    if not geom.is_empty:
                        river.geom = river.geom.difference(bridge)
            except ShapelyError:
                logging.error("        failed to cut bridge %s from %s", bridge.osm_id(), river.osm_id())
        if river.geom.is_empty:
            logging.debug("        cutting produced empty geom for %s", river.osm_id())
            drop_elements.append(river)

        if interactive:
            # noinspection PyUnboundLocalVariable
            progress.update()
    if interactive:
        progress.close()

    # remove empty rivers (almost likely culverts)
    for element in drop_elements:
        elements.remove(element)
