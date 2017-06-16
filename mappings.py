def bool(value):
    if value is None or value.strip().lower() in set(['false', 'no', '0', 'undefined']):
        return 0
    return 1

tags = {
    'highway': {
        'motorway': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 4,
        },
        'motorway_link': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 4,
        },
        'trunk': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 4,
        },
        'trunk_link': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 4,
        },
        'primary': {
            'union': {'highway': 0, 'ref': 8, 'name': 10, 'layer': 12},
            'clip-buffer': 4,
        },
        'primary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        },
        'secondary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        },
        'secondary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        },
        'tertiary': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        },
        'tertiary_link': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        },
        'unclassified': {
            'zoom-min': 12,
            'union': 'highway,ref,name,layer',
            'clip-buffer': 4,
        }
    },
    'landuse': {
        'forest': {
            'rewrite-key': 'natural',
            'rewrite-value': 'wood'
        },
        'wood': {
            'rewrite-key': 'natural'
        }
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
            'buffer': True
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
    'landuse': {
        'military': {},
    },
    'leisure': {
        'nature_reserve': {
            'filter-type': ['Polygon','MultiPolygon'],
            'clip-buffer': 4,
            'label': True,
            'transform': 'filter-rings'
        },
        'protected_area': {
            'filter-type': ['Polygon','MultiPolygon'],
            'clip-buffer': 4,
            'label': True,
            'transform': 'filter-rings'
        },
        'national_park': {
            'filter-type': ['Polygon','MultiPolygon'],
            'clip-buffer': 4,
            'label': True,
            'transform': 'filter-rings'
        },
    },
    'boundary': {
        'nature_reserve': {'rewrite-key': 'leisure'},
        'protected_area': {'rewrite-key': 'leisure'},
        'national_park': {'rewrite-key': 'leisure'},
        'administrative': {
            'force-line': True
        },
    },
    'layer': {
        '__any__': {
            'render': False
        },
    },
    'name': {
        '__any__': {
            'render': False
        },
    },
    'ref': {
        '__any__': {
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
}

"""
transforms:
simplify['ref','name'] - ST_SimplifyPreserveTopology(ST_Linemerge(ST_Collect(geometry)),!pixel_width!)
"""
