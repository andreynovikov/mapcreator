kinds = {
    "place":          0x00000001,
    "road":           0x00000002,
    "building":       0x00000004,
    "emergency":      0x00000008,
    "accommodation":  0x00000010,
    "food":           0x00000020,
    "attraction":     0x00000040,
    "entertainment":  0x00000080,
    "shopping":       0x00000100,
    "service":        0x00000200,
    "religion":       0x00000400,
    "healthbeauty":   0x00000800,
    "kids":           0x00001000,
    "pets":           0x00002000,
    "vehicles":       0x00004000,
    "transportation": 0x00008000,
    "hikebike":       0x00010000,
    "urban":          0x00020000,
    "barrier":        0x00040000
}

types = {
    "wilderness_hut": 1,
    "alpine_hut": 4,
    "guest_house": 7,
    "chalet": 8,
    "motel": 10,
    "hostel": 13,
    "hotel": 16,
    "camp_site": 19,
    "caravan_site": 22,
    "ice_cream": 25,
    "confectionery": 28,
    "alcohol": 31,
    "beverages": 34,
    "bakery": 37,
    "greengrocer": 40,
    "farm": 40,
    "supermarket": 43,
    "convenience": 43,
    "cafe": 46,
    "pub": 49,
    "bar": 52,
    "fast_food": 55,
    "restaurant": 58,
    "marketplace": 61,
    # "block": 64,
    # "bollard": 67,
    # "stile": 68,
    # "cycle_barrier": 70,
    # "lift_gate": 73,
    # "kissing_gate": 74,
    # "gate": 76,
    # "swing_gate": 76,
    # "chain": 76,
    "zoo": 82,
    "theme_park": 83,
    "picnic_site": 85,
    # "firepit": 86,
    "theatre": 88,
    "cinema": 91,
    "library": 94,
    "boat_rental": 97,
    "water_park": 100,
    "horse_riding": 101,
    "beach_resort": 103,
    "sauna": 106,
    "massage": 107,
    "embassy": 108,
    "police": 109,
    "fire_station": 112,
    "hospital": 115,
    "ranger_station": 118,
    "doctors": 121,
    "dentist": 122,
    "pharmacy": 124,
    "telephone": 127,
    "phone": 130,
    "pet": 133,
    "veterinary": 136,
    "toys": 139,
    "amusement_arcade": 142,
    # "playground": 145,
    "bicycle": 148,
    "outdoor": 151,
    "sports": 154,
    "gift": 157,
    "jewelry": 160,
    "photo": 163,
    "books": 166,
    "variety_store": 169,
    "doityourself": 172,
    "hardware": 172,
    "mall": 175,
    "department_store": 175,
    "waterfall": 178,
    "lighthouse": 181,
    "watermill": 183,
    "windmill": 184,
    "bust": 185,
    "stone": 186,
    "plaque": 187,
    "statue": 188,
    "memorial": 189,
    "castle": 190,
    "monument": 193,
    "archaeological_site": 196,
    "wayside_shrine": 197,
    "ruins": 199,
    "museum": 202,
    "gallery": 203,
    "information_office": 205,
    # "guidepost" > 208
    # "map" > 211
    # "information" > 214
    "artwork": 217,
    "viewpoint": 220,
    "attraction": 223,
    # "fountain": 226,
    "car": 229,
    "motorcycle": 230,
    "car_repair": 232,
    "car_rental": 235,
    "fuel": 238,
    # "slipway": 241,
    # "parking": 244,
    "bus_station": 247,
    "bus_stop": 248,
    "tram_stop": 249,
    "bicycle_rental": 250,
    "drinking_water": 253,
    "shelter": 256,
    "toilets": 259,
    "hairdresser": 262,
    "copyshop": 265,
    "laundry": 268,
    "dry_cleaning": 268,
    "bank": 271,
    "post_office": 274,
    "atm": 277,
    "bureau_de_change": 280,
    # "post_box": 283,
    "shower": 286,

    "jewish": 401,
    "muslim": 402,
    "moslem": 402,
    "buddhist": 403,
    "hindu": 404,
    "shinto": 405,
    "christian": 406,
    "sikh": 407,
    "taoist": 408,
    "place_of_worship": 420,
}


def is_place(kind):
    return kind is not None and (kind & 0x00000001) > 0


def is_building(kind):
    return kind is not None and (kind & 0x00000004) > 0


def get_kinds():
    return kinds


def get_kind_and_type(tags):
    feature_kind = 0
    feature_type = 0
    for k, v in tags.items():
        kind, f_type = _tag_kind(k, v)
        feature_kind = feature_kind | kind
        if f_type and (feature_type == 0 or f_type < feature_type):
            feature_type = f_type
    if feature_kind:
        return feature_kind, feature_type
    else:
        return None, None


def _tag_kind(k, v):
    if v is None:
        return 0, 0
    if not isinstance(v, str):
        return 0, 0

    key = k.lower()
    value = v.lower()

    f_kind = 0
    f_type = types.get(value, 0)

    if key == 'place':
        f_kind = kinds['place']

    elif key == 'building' or key == 'building:part':
        f_kind = kinds['building']

    elif key == 'highway':
        if value in ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
                     'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified', 'service',
                     'living_street', 'residential', 'pedestrian', 'construction', 'road', 'track'):
            f_kind = kinds['road']
        elif value == 'bus_stop':
            f_kind = kinds['transportation']
        elif value == 'traffic_signals':
            f_kind = kinds['vehicles']

    elif key == 'barrier':
        if value in ('block', 'bollard', 'stile', 'chain', 'cycle_barrier', 'gate', 'lift_gate', 'swing_gate',
                     'kissing_gate', 'yes'):
            f_kind = kinds['barrier']
            if value == 'yes':
                f_type = types.get('gate', 0)

    elif key == 'amenity':
        if value in ('embassy', 'police', 'fire_station', 'hospital', 'pharmacy', 'doctors', 'dentist', 'telephone'):
            f_kind = kinds['emergency']
        elif value in ('kindergarten',):
            f_kind = kinds['kids']
        elif value in ('cafe', 'pub', 'bar', 'fast_food', 'restaurant'):
            f_kind = kinds['food']
        elif value in ('theatre', 'cinema', 'library', 'boat_rental'):
            f_kind = kinds['entertainment']
        elif value in ('parking', 'fuel', 'car_repair', 'car_rental'):
            f_kind = kinds['vehicles']
        elif value in ('bicycle_rental', 'drinking_water', 'shelter', 'toilets'):
            f_kind = kinds['hikebike']
        elif value in ('bank', 'atm', 'bureau_de_change', 'post_office', 'post_box', 'shower'):
            f_kind = kinds['service']
        elif value == 'marketplace':
            f_kind = kinds['food'] | kinds['shopping']
        elif value == 'ranger_station':
            f_kind = kinds['emergency'] | kinds['hikebike']
        elif value == 'veterinary':
            f_kind = kinds['pets']
        elif value == 'bus_station':
            f_kind = kinds['transportation']
        elif value == 'place_of_worship':
            f_kind = kinds['religion']
        elif value == 'fountain':
            f_kind = kinds['urban']

    elif key == 'tourism':
        if value in ('wilderness_hut', 'alpine_hut'):
            f_kind = kinds['accommodation'] | kinds['hikebike']
        elif value in ('camp_site', 'caravan_site', 'guest_house', 'motel', 'hostel', 'hotel'):
            f_kind = kinds['accommodation']
        elif value in ('attraction', 'viewpoint', 'museum', 'gallery', 'artwork'):
            f_kind = kinds['attraction']
        elif value in ('zoo', 'picnic_site', 'theme_park'):
            f_kind = kinds['entertainment']
        elif value == 'information':
            f_kind = kinds['hikebike']

    elif key == 'shop':
        if value in ('gift', 'variety_store', 'doityourself', 'hardware', 'department_store', 'mall', 'jewelry',
                     'photo', 'books', 'sports'):
            f_kind = kinds['shopping']
        elif value in ('bakery', 'ice_cream', 'greengrocer', 'farm', 'alcohol', 'beverages', 'confectionery'):
            f_kind = kinds['food']
        elif value in ('supermarket', 'convenience'):
            f_kind = kinds['food'] | kinds['shopping']
        elif value in ('car', 'car_repair', 'motorcycle'):
            f_kind = kinds['vehicles']
        elif value in ('bicycle', 'outdoor'):
            f_kind = kinds['hikebike'] | kinds['shopping']
        elif value == 'massage':
            f_kind = kinds['healthbeauty']
        elif value == 'hairdresser':
            f_kind = kinds['healthbeauty'] | kinds['service']
        elif value == 'toys':
            f_kind = kinds['kids']
        elif value == 'pet':
            f_kind = kinds['pets']
        elif value in ('copyshop', 'dry_cleaning', 'laundry'):
            f_kind = kinds['service']

    elif key == 'historic':
        if value in ('memorial', 'castle', 'ruins', 'monument', 'archaeological_site'):
            f_kind = kinds['attraction']

    elif key == 'leisure':
        if value in ('sports_centre', 'horse_riding', 'water_park', 'beach_resort'):
            f_kind = kinds['entertainment']
        elif value == 'sauna':
            f_kind = kinds['healthbeauty'] | kinds['entertainment']
        elif value in ('playground', 'amusement_arcade'):
            f_kind = kinds['kids']
        elif value == 'slipway':
            f_kind = kinds['vehicles']
        elif value == 'firepit':
            f_kind = kinds['hikebike']

    elif key == 'man_made':
        if value in ('lighthouse', 'watermill', 'windmill'):
            f_kind = kinds['attraction']

    elif key == 'railway':
        if value in ('tram_stop', 'subway_entrance'):
            f_kind = kinds['transportation']

    elif key == 'waterway':
        if value == 'waterfall':
            f_kind = kinds['attraction']

    elif key == 'diplomatic':
        if value == 'embassy':
            f_kind = kinds['emergency']

    elif key == 'emergency':
        if value == 'phone':
            f_kind = kinds['emergency']

    elif key == 'information':
        if value == 'office':
            f_type = types['information_office']

    elif key == 'religion':
        if f_type == 0:
            f_type = types['place_of_worship']

    return f_kind, f_type
