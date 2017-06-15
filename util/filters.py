from shapely.geometry import Polygon, MultiPolygon
from shapely.algorithms.cga import signed_area


def filter_rings(geom, area):
    area = area * 8
    if geom.type == 'Polygon':
        return _filter_polygon_rings(geom, area)
    if geom.type == 'MultiPolygon':
        return MultiPolygon([_filter_polygon_rings(part, area) for part in geom])
    return geom

def _filter_polygon_rings(polygon, area):
    exterior = polygon.exterior
    interiors = list(polygon.interiors)
    if not interiors:
        return polygon
    interiors = [hole for hole in interiors if abs(signed_area(hole)) > area]
    return Polygon(exterior, interiors)
