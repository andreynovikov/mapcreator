from util import osm


class MapTypes:
    Detailed, Base, Stub = range(3)

mapType = MapTypes.Detailed


def _admin_level_mapper(tags, renderable, ignorable, mapping):
    admin_level = tags.get('admin_level', '0')
    is_town = tags.get('place', None) in ('city','town')
    if mapType == MapTypes.Stub:
        renderable = admin_level == '2' or (is_town and tags.get('population', 0) > 0)
    if is_town:
        if admin_level == '2':
            mapping['zoom-min'] = 4
        if admin_level in ('3', '4'):
            mapping['zoom-min'] = 5
        if admin_level in ('5','6'):
            mapping['zoom-min'] = 6
    return (renderable, ignorable, mapping)


def _population_mapper(tags, renderable, ignorable, mapping):
    population = tags.get('population', 0)
    if mapType == MapTypes.Stub:
        renderable = tags.get('place', None) in ('country','city','town')
    if tags.get('place', None) in ('city','town'):
        if population >= 150000:
            mapping['zoom-min'] = 6
        if population >= 300000:
            mapping['zoom-min'] = 5
        if population >= 1000000:
            mapping['zoom-min'] = 4
    return (renderable, ignorable, mapping)


def _china_mapper(tags, renderable, ignorable, mapping):
    population = tags.get('population', 0)
    if tags.get('place', None) in ('city','town') and population < 300000:
        renderable = False
    return (renderable, ignorable, mapping)


DEFAULT_AREA = {
    'zoom-min': 12,
    'filter-area': 8
}

DEFAULT_LABELED_AREA = {
    'zoom-min': 12,
    'filter-area': 8,
    'label': True
}

DEFAULT_PLACE = {
    'zoom-min': 14,
    'label': True
}

# default clip-buffer = 4

tags = {
    'highway': {
        'motorway': {
            'zoom-min': 6,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway'
        },
        'motorway_link': {
            'zoom-min': 8,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'trunk': {
            'zoom-min': 6,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway'
        },
        'trunk_link': {
            'zoom-min': 8,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'primary': {
            'zoom-min': 7,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway'
        },
        'primary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'secondary': {
            'zoom-min': 7,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'name': 10, 'tunnel': 10, 'layer': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway'
        },
        'secondary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'tertiary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'tertiary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'unclassified': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'living_street': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'residential': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'construction': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'road': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'track': {
            'zoom-min': 13,
            'union': 'highway,tunnel,layer,tracktype,winter_road,ice_road',
            'union-zoom-max': 13,
            'clip-buffer': 8,
        },
        'service': {
            'zoom-min': 14,
            'clip-buffer': 8,
        },
        'pedestrian': {
            'zoom-min': 14,
            'clip-buffer': 8,
        },
        'bridleway': {
            'zoom-min': 14
        },
        'cycleway': {
            'zoom-min': 14
        },
        'path': {
            'zoom-min': 14
        },
        'footway': {
            'zoom-min': 14
        },
        'steps': {
            'zoom-min': 14
        },
        'traffic_signals': {
            'zoom-min': 14
        },
        'bus_stop': {
            'zoom-min': 14
        },
    },
    'railway': {
        'rail': {'zoom-min': 12},
        'tram': {'zoom-min': 14},
        'light_rail': {'zoom-min': 14},
        'monorail': {'zoom-min': 14},
        'miniature': {'zoom-min': 14},
        'subway': {'zoom-min': 11},
        'narrow_gauge': {'zoom-min': 14},
        'preserved': {'zoom-min': 14},
        'funicular': {'zoom-min': 14},
        'monorail': {'zoom-min': 14},
        'disused': {'zoom-min': 14},
        'abandoned': {'zoom-min': 14},
        'preserved': {'zoom-min': 14},
        'station': {'zoom-min': 14},
        'platform': {'zoom-min': 14},
        'halt': {'zoom-min': 14},
        'tram_stop': {'zoom-min': 14},
        'crossing': {'zoom-min': 14},
        'level_crossing': {'zoom-min': 14},
        'subway_entrance': {'zoom-min': 14},
    },
    'aeroway': {
        'aerodrome': {'zoom-min': 8, 'label': True},
        'heliport': {'zoom-min': 12, 'label': True},
        'runway': {'zoom-min': 11, 'label': True},
        'taxiway': {'zoom-min': 12, 'label': True},
        'helipad': {'zoom-min': 13, 'label': True},
        'apron': {'zoom-min': 14},
        'terminal': {'zoom-min': 14},
    },
    'landuse': {
        'forest': {
            'rewrite-key': 'natural',
            'rewrite-value': 'wood'
        },
        'wood': {
            'rewrite-key': 'natural'
        },
        'military': {
            'zoom-min': 7,
            'filter-type': ['Polygon','MultiPolygon'],
            'union': 'landuse',
            'union-zoom-max': 7,
            'filter-area': 128,
            'buffer': 4,
            'transform': 'filter-rings',
            'basemap-keep-tags': 'landuse'
        },
        'residential': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'retail': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'commercial': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'industrial': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'brownfield': DEFAULT_AREA,
        'construction': DEFAULT_AREA,
        'landfill': DEFAULT_AREA,
        'village_green': DEFAULT_AREA,
        'recreation_ground': DEFAULT_AREA,
        'allotments': DEFAULT_AREA,
        'quarry': DEFAULT_AREA,
        'farmyard': DEFAULT_AREA,
        'orchard': DEFAULT_AREA,
        'cemetery': {
            'zoom-min': 11,
            'filter-area': 8
        },
        'basin': {
            'filter-area': 2
        },
        'reservoir': {
            'filter-area': 2
        },
        'meadow': DEFAULT_AREA,
        'grass': DEFAULT_AREA,
        'vineyard': DEFAULT_AREA,
        'field': {'rewrite-value': 'farmland'},
        'farmland': DEFAULT_AREA,
        'greenhouse_horticulture': DEFAULT_AREA,
        'plant_nursery': DEFAULT_AREA,
    },
    'natural': {
        'forest': {
            'rewrite-value': 'wood'
        },
        'wood': {
            'zoom-min': 8,
            'transform': 'filter-rings',
            'union': 'natural',
            'filter-area': 2,
            'buffer': 1
        },
        'marsh': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'wetland': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'water': {
            'zoom-min': 8,
            'transform': 'filter-rings',
            'filter-area': 4,
            'buffer': 0.3
        },
        'grassland': DEFAULT_AREA,
        'heath': DEFAULT_AREA,
        'scrub': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'scree': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'bare_rock': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'shingle': DEFAULT_AREA,
        'sand': DEFAULT_AREA,
        'beach': {
            'zoom-min': 10,
            'filter-area': 8
        },
        'mud': DEFAULT_AREA,
        'glacier': {
            'keep-tags': 'natural', # used to strip names
            'union': 'natural',
            'ignore': True,
            'zoom-min': 7,
            'filter-area': 8
        },
        'cliff': {'zoom-min': 13},
        'volcano': {'zoom-min': 13},
        'peak': {'zoom-min': 13},
        'cave_entrance': {'zoom-min': 14},
        'spring': {'zoom-min': 13},
        'tree': {'zoom-min': 14, 'enlarge': 0.6},
        'mountain_pass': {'zoom-min': 14},
    },
    'waterway': {
        'riverbank': {
            'zoom-min': 8,
            'filter-area': 2
        },
        'dock': {
            'zoom-min': 8,
            'filter-area': 2
        },
        'lock_gate': {
            'zoom-min': 12
        },
        'river': {'zoom-min': 10},
        'canal': {'zoom-min': 10},
        'dam': {'zoom-min': 12},
        'stream': {'zoom-min': 13},
        'drain': {'zoom-min': 14},
        'ditch': {'zoom-min': 14},
    },
    'aerialway': {
        'mixed_lift': {'rewrite-value': 'chair_lift'},
        't-bar': {'rewrite-value': 'drag_lift'},
        'j-bar': {'rewrite-value': 'drag_lift'},
        'platter': {'rewrite-value': 'drag_lift'},
        'rope_tow': {'rewrite-value': 'drag_lift'},
        'cable_car': {'zoom-min': 12},
        'gondola': {'zoom-min': 12},
        'chair_lift': {'zoom-min': 13},
        'magic_carpet': {'zoom-min': 13},
        'drag_lift': {'zoom-min': 13},
    },
    'place': {
        'ocean': {'ignore': True, 'zoom-min': 2},
        'sea': {'ignore': True, 'zoom-min': 5},
        'country': {'ignore': True, 'zoom-min': 3},
        'state': {'ignore': True, 'zoom-min': 5},
        'island': {'zoom-min': 12},
        'city': {'filter-type': ['Point'], 'zoom-min': 7},
        'town': {'filter-type': ['Point'], 'zoom-min': 7},
        'village': {'zoom-min': 12},
        'hamlet': {'zoom-min': 13},
        'suburb': {'zoom-min': 12},
        'neighbourhood': {'zoom-min': 13},
        'locality': {'zoom-min': 13},
        'isolated_dwelling': {'zoom-min': 13},
        'allotments': {'zoom-min': 14},
    },
    'leisure': {
        'nature_reserve': {
            'zoom-min': 6,
            'filter-type': ['Polygon','MultiPolygon'],
            'union': 'leisure',
            'union-zoom-max': 7,
            'basemap-filter-area': 0.0625,
            'filter-area': 128,
            'buffer': 4,
            'transform': 'filter-rings',
            'basemap-keep-tags': 'leisure'
        },
        'garden': DEFAULT_AREA,
        'golf_course': DEFAULT_AREA,
        'pitch': DEFAULT_AREA,
        'stadium': DEFAULT_AREA,
        'common': DEFAULT_AREA,
        'dog_park': {'zoom-min': 14},
        'park': DEFAULT_AREA,
        'playground': DEFAULT_PLACE,
        'sports_centre': {'zoom-min': 14},
        'water_park': {'zoom-min': 14},
        'slipway': DEFAULT_PLACE,
    },
    'amenity': {
        'university': DEFAULT_PLACE,
        'school': DEFAULT_PLACE,
        'college': DEFAULT_PLACE,
        'kindergarten': DEFAULT_PLACE,
        'hospital': DEFAULT_PLACE,
        'place_of_worship': DEFAULT_PLACE,
        'fountain': DEFAULT_PLACE,
        'drinking_water': DEFAULT_PLACE,
        'police': DEFAULT_PLACE,
        'fire_station': DEFAULT_PLACE,
        'pharmacy': DEFAULT_PLACE,
        'doctors': DEFAULT_PLACE,
        'clinic': DEFAULT_PLACE,
        'veterinary': DEFAULT_PLACE,
        'cafe': DEFAULT_PLACE,
        'pub': DEFAULT_PLACE,
        'bar': DEFAULT_PLACE,
        'fast_food': DEFAULT_PLACE,
        'restaurant': DEFAULT_PLACE,
        'bank': DEFAULT_PLACE,
        'atm': DEFAULT_PLACE,
        'bureau_de_change': DEFAULT_PLACE,
        'bus_station': DEFAULT_PLACE,
        'fuel': DEFAULT_PLACE,
        'post_office': DEFAULT_PLACE,
        'theatre': DEFAULT_PLACE,
        'cinema': DEFAULT_PLACE,
        'shelter': DEFAULT_PLACE,
        'bicycle_rental': DEFAULT_PLACE,
        'telephone': DEFAULT_PLACE,
        'parking': DEFAULT_PLACE,
        'post_box': DEFAULT_PLACE,
        'library': DEFAULT_PLACE,
        'car_repair': {'rewrite-key': 'shop'},
        'toilets': DEFAULT_PLACE,
        'grave_yard': {'rewrite-key': 'landuse', 'rewrite-value': 'cemetery'}
    },
    'emergency': {
        'phone': DEFAULT_PLACE,
    },
    'shop': {
        'alcohol': DEFAULT_PLACE,
        'beverages': DEFAULT_PLACE,
        'bicycle': DEFAULT_PLACE,
        'confectionery': DEFAULT_PLACE,
        'jewelry': DEFAULT_PLACE,
        'bakery': DEFAULT_PLACE,
        'ice_cream': DEFAULT_PLACE,
        'hairdresser': DEFAULT_PLACE,
        'gift': DEFAULT_PLACE,
        'supermarket': DEFAULT_PLACE,
        'convenience': DEFAULT_PLACE,
        'variety_store': DEFAULT_PLACE,
        'doityourself': DEFAULT_PLACE,
        'hardware': DEFAULT_PLACE,
        'department_store': DEFAULT_PLACE,
        'outdoor': DEFAULT_PLACE,
        'photo': DEFAULT_PLACE,
        'books': DEFAULT_PLACE,
        'toys': DEFAULT_PLACE,
        'mall': DEFAULT_PLACE,
        'greengrocer': DEFAULT_PLACE,
        'farm': DEFAULT_PLACE,
        'pet': DEFAULT_PLACE,
        'car': DEFAULT_PLACE,
        'car_repair': DEFAULT_PLACE,
        'copyshop': DEFAULT_PLACE,
        'dry_cleaning': DEFAULT_PLACE,
        'laundry': DEFAULT_PLACE
    },
    'tourism': {
        'picnic_site': DEFAULT_LABELED_AREA,
        'zoo': DEFAULT_LABELED_AREA,
        'wilderness_hut': DEFAULT_PLACE,
        'alpine_hut': DEFAULT_PLACE,
        'camp_site': DEFAULT_PLACE,
        'caravan_site': DEFAULT_PLACE,
        'guest_house': DEFAULT_PLACE,
        'motel': DEFAULT_PLACE,
        'hostel': DEFAULT_PLACE,
        'hotel': DEFAULT_PLACE,
        'attraction': DEFAULT_PLACE,
        'viewpoint': DEFAULT_PLACE,
        'museum': DEFAULT_PLACE,
        'information': DEFAULT_PLACE,
        'artwork': {'zoom-min': 14}
    },
    'historic': {
        'memorial': DEFAULT_PLACE,
        'castle': DEFAULT_PLACE,
        'ruins': DEFAULT_PLACE,
        'monument': DEFAULT_PLACE
    },
    'route': {
        'ferry': {
            'zoom-min': 8,
            'force-line': True
        },
    },
    'piste:type': {
        'downhill': {'zoom-min': 13},
        'nordic': {'zoom-min': 13},
        'sled': {'zoom-min': 13},
    },
    'boundary': {
        'national_park': {'rewrite-key': 'leisure', 'rewrite-value': 'nature_reserve'},
    },
    'building': {
        '__any__': {
            'zoom-min': 14,
            'clip-buffer': 0
        },
    },
    'building:part': {
        '__any__': {
            'filter-type': ['Polygon','MultiPolygon'],
            'zoom-min': 14,
            'clip-buffer': 0
        },
    },
    'barrier': {
        'ditch': {'zoom-min': 14},
        'block': {'zoom-min': 14},
        'bollard': {'zoom-min': 14},
        'border_control': {'zoom-min': 13},
        'chain': {'zoom-min': 14},
        'cycle_barrier': {'zoom-min': 14},
        'gate': {'zoom-min': 14},
        'lift_gate': {'zoom-min': 14},
        'toll_booth': {'zoom-min': 14},
        'yes': {'zoom-min': 14},
        'city_wall': {'zoom-min': 13},
        'fence': {'zoom-min': 14},
        'hedge': {'zoom-min': 14},
        'retaining_wall': {'zoom-min': 14},
        'wall': {'zoom-min': 14},
    },
    'man_made': {
        'cutline': {'zoom-min': 14},
        'pier': {'zoom-min': 14},
        'bridge': DEFAULT_PLACE,
        'tower': {'zoom-min': 14},
        'lighthouse': DEFAULT_PLACE,
        'windmill': DEFAULT_PLACE,
    },
    'mountain_pass': {
        'yes': {'zoom-min': 13},
    },
    'power': {
        'line': {'zoom-min': 14},
        'tower': {'zoom-min': 14},
        'generator': {'zoom-min': 14},
    },
    'area': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'layer': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'name': {
        '__any__': {
            'label': True,
            'render': False
        },
        '__strip__': True
    },
    'name:en': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'name:de': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'name:ru': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'addr:housenumber': {
        '__any__': {
            'label': True,
            'render': False
        },
        '__strip__': True
    },
    'tunnel': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'bridge': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'ford': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'winter_road': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'ice_road': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'maritime': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'oneway': {
        '__any__': {
            'adjust': osm.direction,
            'render': False
        },
    },
    'admin_level': {
        '__any__': {
            'one-of': ['1','2','3','4','5','6'],
            'modify-mapping': _admin_level_mapper,
            'render': False
        },
    },
    'capital': {
        '__any__': {
            'rewrite-key': 'admin_level',
            'rewrite-if-missing': True
        },
    },
    'population': {
        '__any__': {
            'adjust': osm.integer,
            'modify-mapping': _population_mapper,
            'render': False
        },
        '__strip__': True
    },
    'china_class': {
        'zhen': {
            'modify-mapping': _china_mapper,
            'render': False
        },
        'xiang': {
            'modify-mapping': _china_mapper,
            'render': False
        },
        'village': {
            'modify-mapping': _china_mapper,
            'render': False
        },
        '__strip__': True
    },
    'piste:difficulty': {
        '__any__': {
            'one-of': ['novice','easy','intermediate','advanced','expert','freeride'],
            'render': False
        }
    },
    'tracktype': {
        '__any__': {
            'one-of': ['grade1','grade2','grade3','grade4','grade5'],
            'render': False
        }
    },
    'access': {
        '__any__': {
            'one-of': ['private','no'],
            'render': False
        }
    },
    'aerodrome': {
        'international': {
            'zoom-min': 7,
            'basemap-label': True,
            'render': False
        },
        '__strip__': True
    },
    'ele': {
        '__any__': {
            'adjust': osm.height,
            'render': False
        },
        '__strip__': True
    },
    'height': {
        '__any__': {
            'adjust': osm.height,
            'render': False
        },
        '__strip__': True
    },
    'min_height': {
        '__any__': {
            'adjust': osm.height,
            'render': False
        },
        '__strip__': True
    },
    'service': {'parking_aisle': {'render': False}},
    'ref': {'__any__': {'render': False}},
    'iata': {'__any__': {'render': False}},
    'icao': {'__any__': {'render': False}},
    'fee': {'__any__': {'render': False}},
    'station': {'__any__': {'render': False}},
    'religion': {'__any__': {'render': False}},
    'generator:source': {'__any__': {'render': False}},
    'building:levels': {'__any__': {'render': False}, '__strip__': True},
    'building:min_level': {'__any__': {'render': False}, '__strip__': True},
    'building:colour': {'__any__': {'render': False}, '__strip__': True},
    'building:material': {'__any__': {'render': False}, '__strip__': True},
    'roof:colour': {'__any__': {'render': False}, '__strip__': True},
    'roof:material': {'__any__': {'render': False}, '__strip__': True},
    'contour': {},
}


def _water_z2_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 0, 'zoom-max': 2})


def _water_z3_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 3, 'zoom-max': 3})


def _water_z4_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 4, 'zoom-max': 4})


def _water_z5_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 5, 'zoom-max': 5})


def _water_z6_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 6, 'zoom-max': 6})


def _water_z7_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 7, 'zoom-max': 7})


def _water_z8_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 8, 'buffer': 0.2, 'transform': 'filter-rings', 'zoom-max': 8, 'union': 'natural'})


def _water_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 9, 'buffer': 1, 'transform': 'filter-rings', 'union': 'natural'})


def _lakes_50m_mapper(row):
    if mapType == MapTypes.Stub:
        zoom_max = 7
    else:
        zoom_max = 4
    return ({'natural': 'water'}, {'zoom-min': 2, 'zoom-max': zoom_max, 'filter-area': 32})


def _rivers_50m_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 4, 'zoom-max': 4})


def _lakes_rivers_10m_mapper(row):
    return ({'natural': 'water'}, {'zoom-min': 5})


def _urban_areas(row):
    return ({'landuse': 'residential'}, {'zoom-min': 6})


def _contours_mapper(row):
    elevation = int(row['elevation'])
    zoom = 14
    if elevation % 100 == 0:
        contour = 'elevation_major'
        zoom = 11
    elif elevation % 50 == 0:
        contour = 'elevation_medium'
    else:
        contour = 'elevation_minor'
    return ({'contour': contour, 'ele': elevation}, {'zoom-min': zoom})


def _boundaries_mapper(row):
    admin_level = str(row['admin_level'])
    tags = {'boundary': 'administrative', 'admin_level': admin_level}
    zoom = 14
    if admin_level == '2':
        zoom = 2
    if admin_level in ('3', '4'):
        zoom = 5
    if row['maritime'] and row['maritime'] == 'yes':
        zoom = 8
        tags['maritime'] = row['maritime']
    return (tags, {'zoom-min': zoom, 'union': 'boundary,admin_level,maritime', 'simplify': 3})


queries = [
    {
        'query': 'SELECT geom FROM osmd_water_z8',
        'srid': 3857,
        'mapper': _water_z8_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water',
        'srid': 3857,
        'mapper': _water_mapper
    },
    {
        'query': 'SELECT geom, admin_level, maritime FROM osm_boundaries',
        'srid': 3857,
        'mapper': _boundaries_mapper
    },
    {
        'query': 'SELECT geom, elevation FROM contours',
        'srid': 4326,
        'mapper': _contours_mapper
    }
]

basemap_queries = [
    {
        'query': 'SELECT geom FROM osmd_water_z2',
        'srid': 3857,
        'mapper': _water_z2_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z3',
        'srid': 3857,
        'mapper': _water_z3_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z4',
        'srid': 3857,
        'mapper': _water_z4_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z5',
        'srid': 3857,
        'mapper': _water_z5_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z6',
        'srid': 3857,
        'mapper': _water_z6_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z7',
        'srid': 3857,
        'mapper': _water_z7_mapper
    },
    {
        'query': 'SELECT geom FROM ne_50m_lakes',
        'srid': 3857,
        'mapper': _lakes_50m_mapper
    },
    {
        'query': 'SELECT geom FROM ne_10m_lakes',
        'srid': 3857,
        'mapper': _lakes_rivers_10m_mapper
    },
    {
        'query': 'SELECT geom FROM ne_50m_rivers_lake_centerlines',
        'srid': 3857,
        'mapper': _rivers_50m_mapper
    },
    {
        'query': 'SELECT geom FROM ne_10m_rivers_lake_centerlines',
        'srid': 3857,
        'mapper': _lakes_rivers_10m_mapper
    },
    {
        'query': 'SELECT geom FROM ne_10m_urban_areas',
        'srid': 3857,
        'mapper': _urban_areas
    },
    {
        'query': 'SELECT geom, admin_level, maritime FROM osm_boundaries',
        'srid': 3857,
        'mapper': _boundaries_mapper
    },
]

stubmap_queries = [
    {
        'query': 'SELECT geom FROM osmd_water_z2',
        'srid': 3857,
        'mapper': _water_z2_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z3',
        'srid': 3857,
        'mapper': _water_z3_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z4',
        'srid': 3857,
        'mapper': _water_z4_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z5',
        'srid': 3857,
        'mapper': _water_z5_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z6',
        'srid': 3857,
        'mapper': _water_z6_mapper
    },
    {
        'query': 'SELECT geom FROM osmd_water_z7',
        'srid': 3857,
        'mapper': _water_z7_mapper
    },
    {
        'query': 'SELECT geom FROM ne_50m_lakes',
        'srid': 3857,
        'mapper': _lakes_50m_mapper
    },
    {
        'query': 'SELECT geom, admin_level, maritime FROM osm_boundaries WHERE admin_level = \'2\'',
        'srid': 3857,
        'mapper': _boundaries_mapper
    },
]
