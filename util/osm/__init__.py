import numbers
import re


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
        if value in ('yes', 'true', '1', 'y'):
            return 1
        if value == '-1':
            return -1
    return None


def sane(value, limit):
    if abs(value) > limit:
        return None
    else:
        return value


meter_pattern = re.compile('([+-]?[0-9.]+)\s*m')
feet_pattern = re.compile('([+-]?[0-9.]+)\s*ft')
feet_or_inch_pattern = re.compile('([+-]?[0-9.]+)\'(?: *([+-]?[0-9.]+)")?')
number_pattern = re.compile('([+-]?[0-9.]+)')


def height(value):
    """
    Converts number, number with unit to number in meters
    """
    if value is None:
        return None

    limit = 15000  # Mount Everest: 8849 m, Mariana Trench: 10985 m, Kola Superdeep Borehole: 12262 m

    if isinstance(value, numbers.Number):
        return sane(value, limit)

    # trim whitespace to simplify further matching
    value = value.strip()
    # normalize punctuation
    value = value.replace(',', '.')
    try:
        return sane(float(value), limit)
    except ValueError:
        pass

    # try meters
    meters_match = meter_pattern.match(value)
    if meters_match is not None:
        meters = meters_match.group(1)
        try:
            return sane(float(meters), limit)
        except ValueError:
            pass

    # try feet
    feet_match = feet_pattern.match(value)
    if feet_match is not None:
        feet = feet_match.group(1)
        try:
            return sane(float(feet) * 0.3048, limit)
        except ValueError:
            pass

    # try if it looks like an expression in feet via ' "
    feet_match = feet_or_inch_pattern.match(value)
    if feet_match is not None:
        feet = feet_match.group(1)
        inches = feet_match.group(2)
        try:
            feet_as_float = float(feet)
        except (ValueError, TypeError):
            feet_as_float = None
        try:
            inches_as_float = float(inches)
        except (ValueError, TypeError):
            inches_as_float = None
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
            return sane(meters, limit)

    # try and match the first number that can be parsed
    for number_match in number_pattern.finditer(value):
        potential_number = number_match.group(1)
        try:
            return sane(float(potential_number), limit)
        except ValueError:
            pass

    return None


def is_area(tags):
    if not tags:
        return True  # or False?

    result = True
    for k, v in tags.items():
        if k == 'area':
            return v == 'yes'
        if k in ['building', 'building:part']:
            return True
        # as specified by http://wiki.openstreetmap.org/wiki/Key:area
        if k in ['aeroway', 'landuse', 'leisure', 'natural', 'amenity']:
            return True
        if k == 'highway':
            if v not in ['services', 'rest_area']:
                result = False
        if k == 'barrier':
            result = False
        if k == 'railway':
            # There is more to the railway tag then just rails, this excludes the
            # most common railway lines from being detected as areas if they are closed.
            # Since this method is only called if the first and last node are the same
            # this should be safe
            if v in ['rail', 'tram', 'subway', 'monorail', 'narrow_gauge', 'preserved', 'light_rail', 'construction']:
                result = False
        if k == 'piste:type':
            # These piste types are supposed to be lines even if closed
            if v in ['nordic', 'sled', 'hike', 'sleigh']:
                result = False

    return result
