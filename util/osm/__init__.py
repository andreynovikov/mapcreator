def boolean(value):
    if value is None or value.strip().lower() in ('false', 'no', '0', 'undefined'):
        return 'no'
    return 'yes'


def integer(value):
    try:
        return int(value)
    except:
        return None


def direction(value):
    """
    Preprocessor for one-way directions.
    Converts `yes`, `true` and `1` to ``1`` for one-ways in the direction  of the way,
    `-1` to ``-1`` for one-way ways against the direction of the way and ``0`` for all
    other values.
    """
    if value is not None:
        value = value.strip().lower()
        if value in ('yes', 'true', '1'):
            return 1
        if value == '-1':
            return -1
    return 0


def is_area(tags):
    if not tags:
        return True # or False?

    result = True
    for k, v in tags.items():
        if k == 'area':
            return (v == 1)
        if k in ['building', 'building:part']:
            return True
        # as specified by http://wiki.openstreetmap.org/wiki/Key:area
        if k in ['aeroway','building','landuse','leisure','natural','amenity']:
            return True
        if k in ['highway','barrier']:
            result = False
        if k == 'railway':
            # There is more to the railway tag then just rails, this excludes the
            # most common railway lines from being detected as areas if they are closed.
            # Since this method is only called if the first and last node are the same
            # this should be safe
            if v in ['rail','tram','subway','monorail','narrow_gauge','preserved','light_rail','construction']:
                result = False

    return result
