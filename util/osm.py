def is_area(tags):
    if not tags:
        return True # or False?

    result = True
    for k, v in tags.items():
        if k == 'area':
            if v in ['yes','y','true']:
                return True
            if v in ['no','n','false']:
                return False
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
