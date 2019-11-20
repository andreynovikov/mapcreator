from functools import partial

import pyproj
from shapely import geometry
from shapely.geometry.polygon import orient
from shapely.algorithms.polylabel import polylabel as shapely_polylabel


wgs84 = pyproj.Proj(init='epsg:4326')
mercator = pyproj.Proj(init='epsg:3857')

wgs84_to_mercator = partial(pyproj.transform, wgs84, mercator)
mercator_to_wgs84 = partial(pyproj.transform, mercator, wgs84)


def clockwise(geom):
    def _multi(kind, geom):
        return kind([clockwise(g) for g in geom.geoms])

    if geom.type == 'Polygon':
        return orient(geom, -1.0)
    elif geom.type == 'MultiPolygon':
        return _multi(geometry.MultiPolygon, geom)
    elif geom.type == 'GeometryCollection':
        return _multi(geometry.GeometryCollection, geom)
    else:
        return geom


# old version
def clockwise_polygon(polygon):
    exterior = polygon.exterior
    fix = exterior.is_ccw
    if fix:
        exterior = geometry.LinearRing(list(exterior.coords)[::-1])
    interiors = []
    for interior in polygon.interiors:
        if interior.is_ccw:
            interiors.append(interior)
        else:
            interiors.append(geometry.LinearRing(list(interior.coords)[::-1]))
            fix = True
    if fix:
        return geometry.Polygon(exterior, interiors)
    else:
        return polygon


def polylabel(geom):
    label = None
    area = 0
    if geom.type == 'Polygon':
        area = geom.area
        label = shapely_polylabel(geom, 1.194)  # pixel width at zoom 17
    elif geom.type == 'MultiPolygon':
        label = []
        for p in geom:
            lbl = shapely_polylabel(p, 1.194)
            if p.area > area:  # we need to find largest polygon for main label
                area = p.area
                label.insert(0, lbl)
            else:
                label.append(lbl)
    return label, area
