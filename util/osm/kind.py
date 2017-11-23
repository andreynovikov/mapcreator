kinds = {
    "place" :          0x00000001,
    "road" :           0x00000002,
    "building" :       0x00000004,
    "emergency" :      0x00000008,
    "accommodation" :  0x00000010,
    "food" :           0x00000020,
    "attraction" :     0x00000040,
    "entertainment" :  0x00000080,
    "shopping" :       0x00000100,
    "service" :        0x00000200,
    "religion" :       0x00000400,
    "education" :      0x00000800,
    "kids" :           0x00001000,
    "pets" :           0x00002000,
    "vehicles" :       0x00004000,
    "transportation" : 0x00008000,
    "hikebike" :       0x00010000,
    "urban" :          0x00020000,
    "barrier" :        0x00040000
}


def is_place(kind):
    return kind is not None and (kind & 0x00000001) > 0


def is_building(kind):
    return kind is not None and (kind & 0x00000004) > 0


def get_kinds():
    return kinds


def get_kind(tags):
    kind = 0
    for k, v in tags.items():
        kind = kind | _tag_kind(k, v)
    if kind:
        return kind
    else:
        return None


def _tag_kind(k, v):
    if v is None:
        return 0
    if not isinstance(v, str):
        return 0

    key = k.lower()
    value = v.lower()

    if key == 'place':
        return kinds['place']

    if key == 'building' or key == 'building:part':
        return kinds['building']

    if key == 'highway':
        if value in ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
                     'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified', 'service',
                     'living_street', 'residential', 'pedestrian', 'construction', 'road', 'track'):
            return kinds['road']
        if value == 'bus_stop':
            return kinds['transportation']
        if value == 'traffic_signals':
            return kinds['vehicles']

    if key == 'barrier':
        if value in ('block', 'bollard', 'chain', 'cycle_barrier', 'gate', 'lift_gate', 'swing_gate', 'yes'):
            return kinds['barrier']

    if key == 'amenity':
        if value in ('police', 'fire_station', 'hospital', 'pharmacy', 'doctors', 'clinic', 'telephone'):
            return kinds['emergency']
        if value in ('library', 'university', 'school', 'college'):
            return kinds['education']
        if value in ('kindergarten',):
            return kinds['kids']
        if value in ('cafe', 'pub', 'bar', 'fast_food', 'restaurant'):
            return kinds['food']
        if value in ('theatre', 'cinema'):
            return kinds['entertainment']
        if value in ('parking', 'fuel', 'car_repair'):
            return kinds['vehicles']
        if value in ('bicycle_rental', 'drinking_water', 'shelter', 'toilets'):
            return kinds['hikebike']
        if value in ('bank', 'atm', 'bureau_de_change', 'post_office', 'post_box'):
            return kinds['service']
        if value == 'veterinary':
            return kinds['pets']
        if value == 'bus_station':
            return kinds['transportation']
        if value == 'place_of_worship':
            return kinds['religion']
        if value == 'fountain':
            return kinds['urban']

    if key == 'tourism':
        if value in ('wilderness_hut', 'alpine_hut'):
            return kinds['accommodation'] | kinds['hikebike']
        if value in ('camp_site', 'caravan_site', 'guest_house', 'motel', 'hostel', 'hotel'):
            return kinds['accommodation']
        if value in ('attraction', 'viewpoint', 'museum', 'artwork'):
            return kinds['attraction']
        if value in ('zoo', 'picnic_site'):
            return kinds['entertainment']
        if value == 'information':
            return kinds['attraction'] | kinds['hikebike']

    if key == 'shop':
        if value in ('gift', 'variety_store', 'doityourself', 'hardware', 'department_store', 'mall', 'jewelry',
                     'photo', 'books', 'sports'):
            return kinds['shopping']
        if value in ('bakery', 'ice_cream', 'greengrocer', 'farm', 'alcohol', 'beverages', 'confectionery'):
            return kinds['food']
        if value in ('supermarket', 'convenience'):
            return kinds['food'] | kinds['shopping']
        if value in ('car', 'car_repair'):
            return kinds['vehicles']
        if value in ('bicycle', 'outdoor'):
            return kinds['hikebike'] | kinds['shopping']
        if value == 'toys':
            return kinds['kids']
        if value == 'pet':
            return kinds['pets']
        if value in ('hairdresser', 'copyshop', 'dry_cleaning', 'laundry'):
            return kinds['service']

    if key == 'historic':
        if value in ('memorial', 'castle', 'ruins', 'monument'):
            return kinds['attraction']

    if key == 'leisure':
        if value in ('sports_centre', 'water_park'):
            return kinds['entertainment']
        if value == 'playground':
            return kinds['kids']
        if value == 'slipway':
            return kinds['vehicles']

    if key == 'man_made':
        if value in ('lighthouse', 'windmill'):
            return kinds['attraction']

    if key == 'railway':
        if value in ('tram_stop', 'subway_entrance'):
            return kinds['transportation']

    if key == 'waterway':
        if value == 'waterfall':
            return kinds['attraction']

    if key == 'emergency':
        if value == 'phone':
            return kinds['emergency']

    return 0
