from util import osm
from util.processing import cutlines, pistes


class MapTypes:
    Detailed, Base, Stub = range(3)


mapType = MapTypes.Detailed


def _admin_level_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    admin_level = tags.get('admin_level', '0')
    is_town = tags.get('place', None) in ('city', 'town')
    if mapType == MapTypes.Stub:
        renderable = admin_level == '2' or (is_town and tags.get('population', 0) > 0)
    if is_town:
        if admin_level == '2':
            mapping['zoom-min'] = 4
        if admin_level in ('3', '4'):
            mapping['zoom-min'] = 5
        if admin_level in ('5', '6'):
            mapping['zoom-min'] = 6
    return renderable, ignorable, mapping


def _population_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    population = tags.get('population', 0)
    if mapType == MapTypes.Stub:
        renderable = tags.get('place', None) in ('country', 'city', 'town')
    if tags.get('place', None) in ('city', 'town'):
        if population >= 150000:
            mapping['zoom-min'] = 6
        if population >= 300000:
            mapping['zoom-min'] = 5
        if population >= 1000000:
            mapping['zoom-min'] = 4
    return renderable, ignorable, mapping


def _china_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    population = tags.get('population', 0)
    if tags.get('place', None) in ('city', 'town') and population < 300000:
        renderable = False
    return renderable, ignorable, mapping


def _ice_skate_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    skating = False
    leisure = tags.get('leisure', None)
    if leisure == 'pitch':
        if tags.get('sport', None) == 'ice_skating':
            skating = True
    if leisure == 'ice_rink':
        sport = tags.get('sport', None)
        if sport is None or sport == 'ice_skating':
            skating = True
            renderable = True
            tags['area'] = 'yes'
    if skating:
        tags['piste:type'] = 'ice_skate'
        mapping['label'] = True
        if tags.get('covered', 'no') == 'yes':
            tags['area'] = 'no'
    return renderable, ignorable, mapping


def _underwater_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    if tags.get('location', None) == 'underwater':
        ignorable = True
    return renderable, ignorable, mapping


def _indoor_mapper(tags: dict, renderable: bool, ignorable: bool, mapping: dict):
    if any(k in ('highway', 'railway', 'barrier') for k in tags.keys()):
        renderable = False
    return renderable, ignorable, mapping


"""
Mapping parameters:

   rewrite-key - rewrite tag key
   rewrite-if-missing - rewrite only if there is no target tag key
   rewrite-value - rewrite tag value
   one-of - apply only if value is in the specified list
   adjust
   filter-type
   render - mark element as renderable (default True)
   zoom-min - set minimum zoom for element
   zoom-max - set maximum zoom for element
   ignore - do not render map if this is the only renderable element
   filter-area
   buffer
   enlarge
   simplify
   label
   clip-buffer
   keep-tags - force keeping tags with keys in the specified list
   keep-for - keep tag only if element contains one of specified keys
   union
   union-zoom-max
   transform - transform geom ['point', 'filter-rings']
   transform-exclusive - apply transform only if this is the only renderable tag
   force-line - treat closed line as line instead of area
   check-meta - get additional data from database
   modify-mapping - call predefined routine that post-modifies mapping (stacked)
   pre-process - apply pre-processing routine (stacked)

   basemap-label
   basemap-keep-tags
   basemap-filter-area
"""

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
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway',
            'check-meta': True
        },
        'motorway_link': {
            'zoom-min': 8,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'trunk': {
            'zoom-min': 6,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway',
            'check-meta': True
        },
        'trunk_link': {
            'zoom-min': 8,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'primary': {
            'zoom-min': 7,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway',
            'check-meta': True
        },
        'primary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'secondary': {
            'zoom-min': 7,
            'union': {'highway': 0, 'ref': 8, 'winter_road': 8, 'ice_road': 8, 'surface': 8, 'toll': 8,
                      'name': 10, 'tunnel': 10, 'layer': 12, 'piste:type': 12},
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'basemap-keep-tags': 'highway',
            'check-meta': True
        },
        'secondary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'tertiary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'tertiary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'unclassified': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'living_street': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'residential': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'construction': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,toll,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'road': {
            'zoom-min': 12,
            'union': 'highway,ref,name,tunnel,layer,winter_road,ice_road,surface,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'track': {
            'zoom-min': 13,
            'union': 'highway,tunnel,layer,smoothness,winter_road,ice_road,piste:type',
            'union-zoom-max': 13,
            'clip-buffer': 8,
            'check-meta': True
        },
        'service': {
            'zoom-min': 14,
            'clip-buffer': 8,
            'check-meta': True
        },
        'services': {
            'zoom-min': 14,
            'check-meta': True
        },
        'rest_area': {
            'zoom-min': 14,
            'check-meta': True
        },
        'pedestrian': {
            'zoom-min': 14,
            'clip-buffer': 8,
            'check-meta': True
        },
        'bridleway': {
            'zoom-min': 14,
            'check-meta': True
        },
        'cycleway': {
            'zoom-min': 14,
            'check-meta': True
        },
        'path': {
            'zoom-min': 14,
            'check-meta': True
        },
        'footway': {
            'zoom-min': 14,
            'check-meta': True
        },
        'steps': {
            'zoom-min': 14,
            'check-meta': True
        },
        'via_ferrata': {
            'zoom-min': 14,
            'check-meta': True
        },
        'bus_stop': {
            'zoom-min': 14
        },
    },
    'railway': {
        'rail': {'zoom-min': 12, 'check-meta': True},
        'tram': {'zoom-min': 14, 'check-meta': True},
        'light_rail': {'zoom-min': 14, 'check-meta': True},
        'monorail': {'zoom-min': 14, 'check-meta': True},
        'miniature': {'zoom-min': 14, 'check-meta': True},
        'subway': {'zoom-min': 14, 'check-meta': True},
        'narrow_gauge': {'zoom-min': 14, 'check-meta': True},
        'funicular': {'zoom-min': 14, 'check-meta': True},
        'disused': {'zoom-min': 14, 'check-meta': True},
        'abandoned': {'zoom-min': 14, 'check-meta': True},
        'preserved': {'zoom-min': 14, 'check-meta': True},
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
            'filter-type': ['Polygon', 'MultiPolygon'],
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
            'keep-tags': 'natural',  # used to strip names
            'union': 'natural',
            'filter-area': 2,
            'simplify': 0.5,
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
        'bay': {
            'zoom-min': 8,
            'filter-area': 4,
            'transform': 'point',
            'label': True
        },
        'strait': {
            'zoom-min': 8,
            'filter-area': 4,
            'transform': 'point',
            'label': True
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
            'filter-area': 8,
            'label': True
        },
        'mud': DEFAULT_AREA,
        'glacier': {
            'keep-tags': 'natural',  # used to strip names
            'union': 'natural',
            'ignore': True,
            'zoom-min': 7,
            'filter-area': 8
        },
        'cliff': {'zoom-min': 13},
        'volcano': {'zoom-min': 13},
        'peak': {'zoom-min': 13},
        'saddle': {'zoom-min': 13},
        'cave_entrance': {'zoom-min': 14},
        'spring': {'zoom-min': 13},
        'tree_row': {'zoom-min': 14},
        'tree': {'zoom-min': 14},
        'waterfall': {'rewrite-key': 'waterway'},
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
        'waterfall': DEFAULT_PLACE,
        'river': {'zoom-min': 10, 'check-meta': True},
        'canal': {'zoom-min': 10, 'check-meta': True},
        'dam': {'zoom-min': 12, 'check-meta': True},
        'weir': {'zoom-min': 13, 'check-meta': True},
        'stream': {'zoom-min': 13, 'check-meta': True},
        'drain': {'zoom-min': 14, 'check-meta': True},
        'ditch': {'zoom-min': 14, 'check-meta': True},
    },
    'water': {  # natural=water supplement
        'river': {
            'keep-tags': 'natural,intermittent',  # used to strip names
            'render': False
        },
        'canal': {
            'keep-tags': 'natural,intermittent',  # used to strip names
            'render': False
        },
    },
    'wetland': {
        '__any__': {
            'one-of': ['marsh', 'reedbed', 'saltmarsh', 'wet_meadow', 'swamp', 'mangrove', 'bog', 'fen', 'string_bog', 'tidalflat'],
            'buffer': 0.5,
            'render': False
        },
    },
    'aerialway': {
        'mixed_lift': {'rewrite-value': 'chair_lift'},
        't-bar': {'rewrite-value': 'drag_lift'},
        'j-bar': {'rewrite-value': 'drag_lift'},
        'platter': {'rewrite-value': 'drag_lift'},
        'rope_tow': {'rewrite-value': 'drag_lift'},
        'cable_car': {'zoom-min': 12, 'check-meta': True},
        'gondola': {'zoom-min': 12, 'check-meta': True},
        'chair_lift': {'zoom-min': 13, 'check-meta': True},
        'magic_carpet': {'zoom-min': 13, 'check-meta': True},
        'drag_lift': {'zoom-min': 13, 'check-meta': True},
        'zip_line': {'zoom-min': 14, 'check-meta': True},
        'station': {'zoom-min': 14},
    },
    'place': {
        'ocean': {'ignore': True, 'zoom-min': 2, 'transform': 'point', 'transform-exclusive': True},
        'sea': {'ignore': True, 'zoom-min': 5, 'transform': 'point', 'transform-exclusive': True},
        'country': {'ignore': True, 'zoom-min': 3, 'transform': 'point', 'transform-exclusive': True},
        'state': {'ignore': True, 'zoom-min': 5, 'transform': 'point', 'transform-exclusive': True},
        'island': {'zoom-min': 12, 'transform': 'point', 'transform-exclusive': True},
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
        'nature_reserve': {'rewrite-key': 'boundary', 'rewrite-value': 'national_park'},
        'ice_rink': {
            'modify-mapping': _ice_skate_mapper,
            'zoom-min': 13,
            'filter-area': 8,
            'render': False,
            '__strip__': True
        },
        'pitch': {
            'modify-mapping': _ice_skate_mapper,
            'zoom-min': 12,
            'filter-area': 8
        },
        'marina': {
            'zoom-min': 14,
            'label': True
        },
        'dog_park': {
            'zoom-min': 14
        },
        'garden': DEFAULT_AREA,
        'golf_course': DEFAULT_AREA,
        'stadium': DEFAULT_AREA,
        'common': DEFAULT_AREA,
        'park': DEFAULT_AREA,
        'playground': DEFAULT_PLACE,
        'sports_centre': DEFAULT_LABELED_AREA,
        'water_park': DEFAULT_LABELED_AREA,
        'beach_resort': DEFAULT_LABELED_AREA,
        'slipway': DEFAULT_PLACE,
        'swimming_pool': DEFAULT_PLACE,
        'sauna': DEFAULT_PLACE,
        'amusement_arcade': DEFAULT_PLACE,
        'horse_riding': DEFAULT_PLACE,
        'firepit': {'zoom-min': 14}
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
        'post_box': {'zoom-min': 14},
        'library': DEFAULT_PLACE,
        'marketplace': DEFAULT_PLACE,
        'car_repair': {'rewrite-key': 'shop'},
        'toilets': DEFAULT_PLACE,
        'ranger_station': DEFAULT_PLACE,
        'car_rental': DEFAULT_PLACE,
        'ferry_terminal': DEFAULT_PLACE,
        'shower': DEFAULT_PLACE,
        'boat_rental': DEFAULT_PLACE,
        'dentist': DEFAULT_PLACE,
        'grave_yard': {'rewrite-key': 'landuse', 'rewrite-value': 'cemetery'},
        'swimming_pool': {'rewrite-key': 'leisure'},
        'embassy': {'rewrite-key': 'diplomatic', 'rewrite-if-missing': True},
    },
    'diplomatic': {
        'embassy': DEFAULT_PLACE,
        'consulate': {'rewrite-value': 'embassy'},  # temporary
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
        'laundry': DEFAULT_PLACE,
        'sports': DEFAULT_PLACE,
        'massage': DEFAULT_PLACE
    },
    'tourism': {
        'picnic_site': DEFAULT_LABELED_AREA,
        'zoo': DEFAULT_LABELED_AREA,
        'gallery': DEFAULT_LABELED_AREA,
        'theme_park': DEFAULT_LABELED_AREA,
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
        'monument': DEFAULT_PLACE,
        'archaeological_site': DEFAULT_PLACE,
        'wayside_shrine': DEFAULT_PLACE
    },
    'route': {
        'ferry': {
            'zoom-min': 7,
            'basemap-keep-tags': 'route',
            'force-line': True
        },
    },
    'piste:type': {
        'downhill': {'zoom-min': 12, 'pre-process': pistes.process},
        'nordic': {'zoom-min': 12},
        'sled': {'zoom-min': 12},
        'skitour': {'zoom-min': 12},
        'hike': {'zoom-min': 12},
        'sleigh': {'zoom-min': 12},
        'snow_park': {'zoom-min': 13},
        'playground': {'zoom-min': 13},
        'ice_skate': {'zoom-min': 13, 'label': True},
        'ski_jump': {'zoom-min': 13, 'label': True},
        'ski_jump_landing': {'zoom-min': 13, 'label': True},
    },
    'boundary': {
        'national_park': {
            'zoom-min': 6,
            'filter-type': ['Polygon', 'MultiPolygon'],
            'union': 'boundary',
            'union-zoom-max': 7,
            'basemap-filter-area': 0.0625,
            'filter-area': 128,
            'buffer': 4,
            'transform': 'filter-rings',
            'basemap-keep-tags': 'boundary'
        },
    },
    'building': {
        '__any__': {
            'adjust': osm.boolean,
            'zoom-min': 14,
            'clip-buffer': 0
        },
    },
    'building:part': {
        '__any__': {
            'filter-type': ['Polygon', 'MultiPolygon'],
            'adjust': osm.boolean,
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
        'kissing_gate': {'zoom-min': 14},
        'lift_gate': {'zoom-min': 14},
        'stile': {'zoom-min': 14},
        'toll_booth': {'zoom-min': 14},
        'yes': {'zoom-min': 14},
        'city_wall': {'zoom-min': 13},
        'fence': {'zoom-min': 14},
        'hedge': {'zoom-min': 14},
        'retaining_wall': {'zoom-min': 14},
        'wall': {'zoom-min': 14},
    },
    'man_made': {
        'cutline': {'zoom-min': 14, 'pre-process': cutlines.process, '__strip__': True},
        'pier': {'zoom-min': 14},
        'embankment': {'zoom-min': 14},
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
    'sport': {
        '__any__': {
            'render': False
        },
        '__strip__': True
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
    'opening_hours': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'contact:website': {
        '__any__': {
            'rewrite-key': 'website',
            'rewrite-if-missing': True
        },
        '__strip__': True
    },
    'website': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'contact:phone': {
        '__any__': {
            'rewrite-key': 'phone',
            'rewrite-if-missing': True
        },
        '__strip__': True
    },
    'phone': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'wikipedia': {
        '__any__': {
            'render': False
        },
        '__strip__': True
    },
    'addr:housenumber': {
        '__any__': {
            'label': True,
            'keep-for': 'building,building:part',
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
            'zoom-min': 14,
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
    '4wd_only': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'surface': {
        'unpaved': {
            'render': False
        },
        'dirt': {
            'render': False
        },
        'compacted': {
            'rewrite-value': 'unpaved'
        },
        'earth': {
            'rewrite-value': 'dirt'
        },
        'grass': {
            'rewrite-value': 'unpaved'
        },
        'gravel_turf': {
            'rewrite-value': 'unpaved'
        },
        'fine_gravel': {
            'rewrite-value': 'unpaved'
        },
        'gravel': {
            'rewrite-value': 'unpaved'
        },
        'ground': {
            'rewrite-value': 'dirt'
        },
        'ice': {
            'rewrite-key': 'ice_road',
            'rewrite-value': 'yes',
            'rewrite-if-missing': True
        },
        'mud': {
            'rewrite-value': 'dirt'
        },
        'pebblestone': {
            'rewrite-value': 'unpaved'
        },
        'salt': {
            'rewrite-value': 'unpaved'
        },
        'sand': {
            'rewrite-value': 'unpaved'
        },
        'snow': {
            'rewrite-key': 'winter_road',
            'rewrite-value': 'yes',
            'rewrite-if-missing': True
        },
        'woodchips': {
            'rewrite-value': 'unpaved'
        },
    },
    'smoothness': {
        '__any__': {
            'one-of': ['excellent', 'good', 'intermediate', 'bad', 'very_bad', 'horrible', 'very_horrible', 'impassable'],
            'render': False
        },
    },
    'tracktype': {
        'grade1': {
            'rewrite-key': 'smoothness',
            'rewrite-value': 'intermediate',
            'rewrite-if-missing': True
        },
        'grade2': {
            'rewrite-key': 'smoothness',
            'rewrite-value': 'bad',
            'rewrite-if-missing': True
        },
        'grade3': {
            'rewrite-key': 'smoothness',
            'rewrite-value': 'bad',
            'rewrite-if-missing': True
        },
        'grade4': {
            'rewrite-key': 'smoothness',
            'rewrite-value': 'very_bad',
            'rewrite-if-missing': True
        },
        'grade5': {
            'rewrite-key': 'smoothness',
            'rewrite-value': 'horrible',  # it's not exactly correct but is often used to mark extremely bad roads
            'rewrite-if-missing': True
        },
    },
    'toll': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        }
    },
    'fee': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        }
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
    'lit': {
        '__any__': {
            'adjust': osm.boolean,
            'keep-for': 'piste:type',
            'render': False
        },
        '__strip__': True
    },
    'piste:lit': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'piste:oneway': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
    },
    'covered': {
        '__any__': {
            'adjust': osm.boolean,
            'render': False
        },
        '__strip__': True
    },
    'admin_level': {
        '__any__': {
            'one-of': ['1', '2', '3', '4', '5', '6'],
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
    'memorial': {
        'statue': {'render': False},
        'bust': {'render': False},
        'stone': {'render': False},
        'plaque': {'render': False},
        'blue_plaque': {'rewrite-value': 'blue_plaque'}
    },
    'information': {
        'guidepost': {'render': False},
        'map': {'render': False},
        'office': {'render': False},
        'citymap': {'rewrite-value': 'map'},
        'hikingmap': {'rewrite-value': 'map'},
    },
    'sac_scale': {
        'hiking': {'rewrite-value': 'T1'},
        'mountain_hiking': {'rewrite-value': 'T2'},
        'demanding_mountain_hiking': {'rewrite-value': 'T3'},
        'alpine_hiking': {'rewrite-value': 'T4'},
        'demanding_alpine_hiking': {'rewrite-value': 'T5'},
        'difficult_alpine_hiking': {'rewrite-value': 'T6'},
        'T1': {'render': False},
        'T2': {'render': False},
        'T3': {'render': False},
        'T4': {'render': False},
        'T5': {'render': False},
        'T6': {'render': False},
    },
    'trail_visibility': {
        '__any__': {
            'one-of': ['excellent', 'good', 'intermediate', 'bad', 'horrible', 'no'],
            'render': False
        }
    },
    'piste:difficulty': {
        '__any__': {
            'one-of': ['novice', 'easy', 'intermediate', 'advanced', 'expert', 'freeride'],
            'render': False
        }
    },
    'piste:grooming': {
        '__any__': {
            'one-of': ['mogul', 'backcountry', 'scooter'],
            'render': False
        }
    },
    'access': {
        '__any__': {
            'one-of': ['private', 'no'],
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
    'aerodrome:type': {
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
            'keep-for': 'building,building:part',
            'render': False
        },
        '__strip__': True
    },
    'min_height': {
        '__any__': {
            'adjust': osm.height,
            'keep-for': 'building,building:part',
            'render': False
        },
        '__strip__': True
    },
    'ref': {
        '__any__': {
            'keep-for': 'highway',
            'render': False
        }
    },
    'location': {
        'underwater': {
            'modify-mapping': _underwater_mapper,
            'render': False,
        },
        '__strip__': True
    },
    'indoor': {
        '__any__': {
            'modify-mapping': _indoor_mapper,
            'render': False,
        },
        '__strip__': True
    },
    'service': {'parking_aisle': {'render': False}},
    'intermittent': {'yes': {'render': False}},
    'iata': {'__any__': {'render': False}},
    'icao': {'__any__': {'render': False}},
    'station': {'__any__': {'render': False}},
    'religion': {'__any__': {'render': False}},
    'osmc:symbol': {'__any__': {'render': False}},
    'generator:source': {'__any__': {'render': False}},
    'building:levels': {'__any__': {'render': False}, '__strip__': True},
    'building:min_level': {'__any__': {'render': False}, '__strip__': True},
    'building:colour': {'__any__': {'render': False}, '__strip__': True},
    'building:material': {'__any__': {'render': False}, '__strip__': True},
    'roof:height': {'__any__': {'render': False}, '__strip__': True},
    'roof:levels': {'__any__': {'render': False}, '__strip__': True},
    'roof:colour': {'__any__': {'render': False}, '__strip__': True},
    'roof:material': {'__any__': {'render': False}, '__strip__': True},
    'roof:shape': {'__any__': {'render': False}, '__strip__': True},
    'roof:direction': {'__any__': {'render': False}, '__strip__': True},
    'roof:angle': {'__any__': {'render': False}, '__strip__': True},
    'roof:orientation': {'__any__': {'render': False}, '__strip__': True},
    'network': {},
    'route:network': {},
    'contour': {},
    'piste:border': {},
}


def _water_z2_mapper(row):
    return {'natural': 'sea'}, {'zoom-min': 0, 'zoom-max': 2}


def _water_z3_mapper(row):
    return {'natural': 'sea'}, {'zoom-min': 3, 'zoom-max': 3}


def _water_z4_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 4, 'zoom-max': 4})


def _water_z5_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 5, 'zoom-max': 5})


def _water_z6_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 6, 'zoom-max': 6})


def _water_z7_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 7, 'zoom-max': 7})


def _water_z8_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 8, 'buffer': 0.2, 'transform': 'filter-rings', 'zoom-max': 8, 'union': 'natural'})


def _water_mapper(row):
    return ({'natural': 'sea'}, {'zoom-min': 9, 'buffer': 1, 'transform': 'filter-rings', 'union': 'natural'})


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
        zoom = 12
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
    return (tags, {'zoom-min': zoom, 'union': 'boundary,admin_level,maritime', 'simplify': 2})


def _routes_mapper(row):
    tags = {'route': row['route'], 'network': row['network'], 'osmc:symbol': row['osmc_symbol'],
            'ref': row['ref']}
    zoom = 11
    if row['network'] == 'iwn':
        zoom = 8
    elif row['network'] == 'nwn':
        zoom = 9
    elif row['network'] == 'rwn':
        zoom = 10
    return (tags, {'zoom-min': zoom, 'simplify': 2})


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
        'query': 'SELECT geom, id, route, network, osmc_symbol, state, ref FROM osm_routes',
        'srid': 3857,
        'mapper': _routes_mapper
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
