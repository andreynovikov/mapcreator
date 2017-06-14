def bool(value):
    if value is None or value.strip().lower() in set(['false', 'no', '0', 'undefined']):
        return 0
    return 1

tags = {
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
            'zoom-min': 8,
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
            'label': True
        },
        'protected_area': {
            'filter-type': ['Polygon','MultiPolygon'],
            'label': True
        },
        'national_park': {
            'filter-type': ['Polygon','MultiPolygon'],
            'label': True
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
    'name': {
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
filter-rings['landuse'] - filter_rings(ST_SimplifyPreserveTopology(ST_Buffer(geometry,!pixel_width!),!pixel_width!),!pixel_width!*!pixel_width!*8)
                          filter_rings(ST_SimplifyPreserveTopology(ST_Union(geometry),               !pixel_width!),!pixel_width!*!pixel_width!*8) (ST_Buffer(geometry,!pixel_width!))
"""
