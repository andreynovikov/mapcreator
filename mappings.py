from util import osm


# default clip-buffer = 4

tags = {
    'highway': {
        'motorway': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 8,
        },
        'motorway_link': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 8,
        },
        'trunk': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 8,
        },
        'trunk_link': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 8,
        },
        'primary': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 8,
        },
        'primary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'secondary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'secondary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'tertiary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'tertiary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'unclassified': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'living_street': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'residential': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'construction': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'road': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 8,
        },
        'track': {
            'zoom-min': 13,
            'union': 'highway,layer,tracktype',
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
            'filter-type': ['Polygon','MultiPolygon'],
            'calc-area': True,
            'filter-area': 16,
            'buffer': 2,
            'transform': 'filter-rings'
        },
        'nature_reserve': {
            'filter-type': ['Polygon','MultiPolygon'],
            'buffer': 2,
            'transform': 'filter-rings'
        },
        'protected_area': {
            'filter-type': ['Polygon','MultiPolygon'],
            'buffer': 2,
            'transform': 'filter-rings'
        },
        'national_park': {
            'filter-type': ['Polygon','MultiPolygon'],
            'buffer': 2,
            'transform': 'filter-rings'
        },
    },
    'natural': {
        'forest': {
            'rewrite-value': 'wood'
        },
        'wood': {
            'transform': 'filter-rings',
            'union': 'natural',
            #TODO combine next two settings into one
            'calc-area': True,
            'filter-area': 2,
            'buffer': 1
        },
    },
    'place': {
        'ocean': {},
        'sea': {},
        'country': {},
        'state': {},
        'region': {},
        'island': {'zoom-min': 12},
        'city': {},
        'town': {},
        'village': {'zoom-min': 12},
        'hamlet': {'zoom-min': 13},
        'suburb': {'zoom-min': 12},
        'neighbourhood': {'zoom-min': 13},
        'locality': {'zoom-min': 13},
        'isolated_dwelling': {'zoom-min': 13},
    },
    'leisure': {
        'nature_reserve': {'rewrite-key': 'landuse'},
        'protected_area': {'rewrite-key': 'landuse'},
        'national_park': {'rewrite-key': 'landuse'},
    },
    'boundary': {
        'nature_reserve': {'rewrite-key': 'landuse'},
        'protected_area': {'rewrite-key': 'landuse'},
        'national_park': {'rewrite-key': 'landuse'},
        'administrative': {
            'force-line': True
        },
    },
    'building': {
        '__any__': {
            'filter-type': ['Polygon','MultiPolygon'],
            'zoom-min': 14
        },
    },
    'building:part': {
        '__any__': {
            'filter-type': ['Polygon','MultiPolygon'],
            'zoom-min': 14
        },
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
    },
    'name': {
        '__any__': {
            'label': True,
            'render': False
        },
    },
    'addr:housenumber': {
        '__any__': {
            'label': True,
            'render': False
        }
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
    'oneway': {
        '__any__': {
            'adjust': osm.direction,
            'render': False
        },
    },
    'admin_level': {
        '__any__': {
            'one-of': ['1','2','3','4','5','6'],
            'render': False
        },
    },
    'capital': {
        '__any__': {
            'render': False
        },
    },
    'ref': {'__any__': {'render': False}},
    'access': {'__any__': {'render': False}},
    'service': {'__any__': {'render': False}},
    'tracktype': {'__any__': {'render': False}},
    'height': {'__any__': {'render': False}},
    'min_height': {'__any__': {'render': False}},
    'building:levels': {'__any__': {'render': False}},
    'building:min_level': {'__any__': {'render': False}},
    'building:colour': {'__any__': {'render': False}},
    'building:material': {'__any__': {'render': False}},
    'roof:colour': {'__any__': {'render': False}},
    'roof:material': {'__any__': {'render': False}},
}
