import re
import numbers

from webcolors import name_to_rgb

def _to_float(x):
    if x is None:
        return None
    # normalize punctuation
    x = x.replace(';', '.').replace(',', '.')
    try:
        return float(x)
    except ValueError:
        return None

feet_pattern = re.compile('([+-]?[0-9.]+)\'(?: *([+-]?[0-9.]+)")?')
number_pattern = re.compile('([+-]?[0-9.]+)')


def _to_float_meters(x):
    if x is None:
        return None

    if isinstance(x, numbers.Number):
        return x

    as_float = _to_float(x)
    if as_float is not None:
        return as_float

    # trim whitespace to simplify further matching
    x = x.strip()

    # try explicit meters suffix
    if x.endswith(' m'):
        meters_as_float = _to_float(x[:-2])
        if meters_as_float is not None:
            return meters_as_float

    # try if it looks like an expression in feet via ' "
    feet_match = feet_pattern.match(x)
    if feet_match is not None:
        feet = feet_match.group(1)
        inches = feet_match.group(2)
        feet_as_float = _to_float(feet)
        inches_as_float = _to_float(inches)

        total_inches = 0.0
        parsed_feet_or_inches = False
        if feet_as_float is not None:
            total_inches = feet_as_float * 12.0
            parsed_feet_or_inches = True
        if inches_as_float is not None:
            total_inches += inches_as_float
            parsed_feet_or_inches = True
        if parsed_feet_or_inches:
            meters = total_inches * 0.02544
            return meters

    # try and match the first number that can be parsed
    for number_match in number_pattern.finditer(x):
        potential_number = number_match.group(1)
        as_float = _to_float(potential_number)
        if as_float is not None:
            return as_float

    return None


def _building_calc_levels(levels):
    levels = max(levels, 1)
    levels = (levels * 3) + 0.5
    return levels


def _building_calc_min_levels(min_levels):
    min_levels = max(min_levels, 0)
    min_levels = min_levels * 3
    return min_levels


def _building_calc_height(height_val, levels_val, levels_calc_fn):
    height = _to_float_meters(height_val)
    if height is not None:
        return height
    levels = _to_float_meters(levels_val)
    if levels is None:
        return None
    return levels_calc_fn(levels)


def _color(r, g, b):
    return 0x0ff000000 + (r<<16) + (g<<8) + b


roof_colors = {
    "brown" : _color(120, 110, 110),
    "red" : _color(235, 140, 130),
    "green" : _color(150, 200, 130),
    "blue" : _color(100, 50, 200)
}

colors = {
    "white" : _color(240, 240, 240),
    "black" : _color(86, 86, 86),
    "gray" : _color(120, 120, 120),
    "red" : _color(255, 190, 190),
    "green" : _color(190, 255, 190),
    "blue" : _color(190, 190, 255),
    "yellow" : _color(255, 255, 175),
    "darkgray" : 0xff444444,
    "lightgray" : 0xffcccccc,
    "transparent" : 0x000010101
}

material_colors = {
    "roof_tiles" : _color(216, 167, 111),
    "tile" : _color(216, 167, 111),
    "concrete" : _color(210, 212, 212),
    "cement_block" : _color(210, 212, 212),
    "metal" : 0xffc0c0c0,
    "tin" : 0xffc0c0c0,
    "tar_paper" : 0xff969998,
    "eternit" : _color(216, 167, 111),
    "asbestos" : _color(160, 152, 141),
    "glass" : _color(130, 224, 255),
    "slate" : 0xff605960,
    "zink" : _color(180, 180, 180),
    "gravel" : _color(170, 130, 80),
    "copper" : _color(150, 200, 130),
    "wood" : _color(170, 130, 80),
    "timber_framing" : _color(170, 130, 80),
    "grass" : 0xff50aa50,
    "stone" : _color(206, 207, 181),
    "marble" : _color(220, 210, 215),
    "plaster" : _color(236, 237, 181),
    "brick" : _color(255, 217, 191),
    "stainless_steel" : _color(153, 157, 160),
    "gold" : 0xffffd700
}

color_aliases = {
    "peach" : "peachpuff", # css color
    "peachpuf" : "peachpuff",
    "rose" : "mistyrose", # css color
    "grey" : "gray",
    "darkgrey" : "darkgray",
    "lightgrey" : "lightgray",
}

def _get_color(color, roof):
    # process RGB hex color code
    if color[0] == '#':
        try:
            c = int(color[1:], 16)
            if len(color) == 7:
                c = c | 0x0ff000000 # add alpha
            #/* hardcoded colors are way too saturated for my taste */
            #return ColorUtil.modHsv(c, 1.0, 0.4, HSV_V, true);
            return c
        except ValueError as e:
            print("Invalid hex color: %s" % color)
            return None

    # clean all delimiters
    color = re.sub(r'[\-_\s]', '', color)

    # check aliases
    if color in color_aliases:
        color = color_aliases[color]

    # look for predefined values
    if roof and color in roof_colors:
        return roof_colors[color]

    if color in colors:
        return colors[color]

    try:
        # try to get color by name
        r, g, b = name_to_rgb(color)
        #return ColorUtil.modHsv(css, 1.0, HSV_S, HSV_V, true);
        return _color(r, g, b)
    except ValueError as e:
        # if failed try to treat is a RGB hex without prefix
        if len(color) == 6:
            try:
                c = int(color, 16)
                c = c | 0x0ff000000 # add alpha
                return c
            except:
                pass

    print("Unknown color: %s" % color)
    return None


def _get_material_color(material, roof):
    if roof and material == "glass":
        return _color(130, 224, 255)

    if material in material_colors:
        return material_colors[material]

    print("Unknown material: %s" % material)

    return None


def _building_color(color, material, roof):
    if color is not None:
        return _get_color(color, roof)
    if material is not None:
        return _get_material_color(material, roof)
    return None


def get_building_properties(tags):
    if 'building' not in tags and 'building:part' not in tags:
        return (None, None, None, None)

    height = _building_calc_height(tags.get('height'), tags.get('building:levels'), _building_calc_levels)
    min_height = _building_calc_height(tags.get('min_height'), tags.get('building:min_level'), _building_calc_min_levels)

    color = _building_color(tags.get('building:colour'), tags.get('building:material'), False)
    roof_color = _building_color(tags.get('roof:colour'), tags.get('roof:material'), True)

    return (height, min_height, color, roof_color)