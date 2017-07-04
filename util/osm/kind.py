kinds = {
    "road" :           0x00000001,
    "building" :       0x00000002,
    "accommodation" :  0x00000004,
    "food" :           0x00000008,
    "barrier" :        0x00000010,
    "entertainment" :  0x00000020,
    "emergency" :      0x00000040,
    "pets" :           0x00000080,
    "shopping" :       0x00000100,
    "attraction" :     0x00000200,
    "education" :      0x00000400,
    "vehicles" :       0x00000800,
    "transportation" : 0x00001000,
    "religion" :       0x00002000,
    "hikebike" :       0x00004000,
    "moneymail" :      0x00008000,
    "urban" :          0x00010000
}


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

    if key == 'building' or key == 'building.part':
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
        if value in ('police', 'fire_station', 'hospital', 'pharmacy', 'doctors', 'telephone'):
            return kinds['emergency']
        if value in ('library', 'university', 'school', 'college', 'kindergarten'):
            return kinds['education']
        if value in ('cafe', 'pub', 'bar', 'fast_food', 'restaurant'):
            return kinds['food']
        if value in ('theatre', 'cinema'):
            return kinds['entertainment']
        if value in ('parking', 'fuel', 'car_repair'):
            return kinds['vehicles']
        if value in ('bicycle_rental', 'drinking_water', 'shelter', 'toilets'):
            return kinds['hikebike']
        if value in ('bank', 'atm', 'post_office', 'post_box'):
            return kinds['moneymail']
        if value == 'veterinary':
            return kinds['pets']
        if value == 'bus_station':
            return kinds['transportation']
        if value == 'place_of_worship':
            return kinds['religion']
        if value == 'fountain':
            return kinds['urban']

    if key == 'tourism':
        if value in ('wilderness_hut', 'alpine_hut', 'camp_site', 'caravan_site', 'guest_house', 'motel', 'hostel', 'hotel'):
            return kinds['accommodation']
        if value in ('attraction', 'viewpoint', 'museum', 'information', 'artwork'):
            return kinds['attraction']
        if value in ('zoo', 'picnic_site'):
            return kinds['entertainment']

    if key == 'shop':
        if value in ('bakery', 'hairdresser', 'supermarket', 'doityourself', 'mall'):
            return kinds['shopping']
        if value in ('car', 'car_repair'):
            return kinds['vehicles']
        if value == 'pet':
            return kinds['pets']

    if key == 'historic':
        if value in ('memorial', 'castle', 'ruins', 'monument'):
            return kinds['attraction']

    if key == 'leisure':
        if value in ('sports_centre', 'water_park', 'playground'):
            return kinds['entertainment']

    if key == 'railway':
        if value in ('tram_stop', 'subway_entrance'):
            return kinds['transportation']

    return 0
