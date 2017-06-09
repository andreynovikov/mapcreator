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
            'area': True,
            'filter-area': 8,
            'buffer': True
        },
    },
    'name': {
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
