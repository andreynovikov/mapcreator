import logging

from . import TileData_pb2

from . import GeomEncoder
from . import StaticVals
from . import StaticKeys

# custom keys/values start at attrib_offset
ATTRIB_OFFSET = 1024

# coordinates are scaled to this range within tile
EXTENTS = 4096

# tiles are padded by this number of pixels for the current zoom level (OSciMap uses this to cover up seams between tiles)
PADDING = 5


def encode(features, mappings=None):
    vector_tile = VectorTile(EXTENTS, mappings)
    vector_tile.addFeatures(features)
    vector_tile.complete()
    return vector_tile.out.SerializeToString()


class VectorTile:
    """
    """
    def __init__(self, extents, mappings):
        self.geomencoder = GeomEncoder.GeomEncoder(extents)
        self.mappings = mappings

        # TODO count to sort by number of occurrences
        self.keydict = {}
        self.cur_key = ATTRIB_OFFSET

        self.valdict = {}
        self.cur_val = ATTRIB_OFFSET

        self.tagdict = {}
        self.num_tags = 0

        self.out = TileData_pb2.Data()
        self.out.version = 1

        self.num_features = 0

    def complete(self):
        if self.num_features > 0 and self.num_tags == 0:
            logging.warning("empty tags")

        self.out.num_tags = self.num_tags

        if self.cur_key - ATTRIB_OFFSET > 0:
            self.out.num_keys = self.cur_key - ATTRIB_OFFSET

        if self.cur_val - ATTRIB_OFFSET > 0:
            self.out.num_vals = self.cur_val - ATTRIB_OFFSET

    def addFeatures(self, features):
        for feature in features:
            self.addFeature(feature)

    def addFeature(self, feature):
        geom = self.geomencoder
        tags = []

        id = None
        layer = None
        housenumber = None
        elevation = None

        for k, v in feature.tags.items():
            if v is None:
                continue

            if k == 'building:outline':
                continue

            if k == 'id':
                id = v
                continue

            if k == 'ele':
                elevation = v
                continue

            # use unsigned int for layer. i.e. map to 0..10
            if k == 'layer':
                layer = self.getLayer(v)
                continue

            if k == 'addr:housenumber':
                housenumber = v
                continue

            if self.mappings[k].get('__strip__', False):
                continue
            if self.mappings[k].get(v, {}).get('__strip__', False):
                continue

            tag = str(k), str(v)

            tags.append(self.getTagId(tag))

        if len(tags) == 0:
            if feature.id:
                logging.error('missing tags in element %s' % str(feature.id))
            else:
                logging.error('missing tags in geom %s' % feature.geometry.type)
            return

        try:
            geom.parseGeometry(feature.geometry.wkb)
        except Exception:
            logging.error("%s:" % str(feature.tags))
            logging.exception("Error parsing geometry %s" % feature.geometry.wkt)
            return

        f = None
        # geometry_type = None
        if geom.isPoint:
            # geometry_type = 'Point'
            f = self.out.points.add()
            # add number of points (for multi-point)
            if len(geom.coordinates) > 2:
                logging.info('points %s' % len(geom.coordinates))
                f.indices.add(geom.coordinates / 2)
        else:
            # empty geometry
            if len(geom.index) == 0:
                logging.debug('empty geom: %d %s' % (id, str(feature.tags)))
                return

            if geom.isPoly:
                # geometry_type = 'Polygon'
                f = self.out.polygons.add()
            else:
                # geometry_type = 'LineString'
                f = self.out.lines.add()

            # add coordinate index list (coordinates per geometry)
            f.indices.extend(geom.index)

            # add indice count (number of geometries)
            if len(f.indices) > 1:
                f.num_indices = len(f.indices)

        # add coordinates
        f.coordinates.extend(geom.coordinates)

        # add label position
        if feature.label is not None:
            if isinstance(feature.label, list):
                """
                # need to fix decoder first
                coordinates = []
                for label in feature.label:
                    geom.parseGeometry(label.wkb)
                    if geom.isPoint:
                        coordinates.extend(geom.coordinates)
                f.label.extend(coordinates)
                """
                geom.parseGeometry(feature.label[0].wkb)
                if geom.isPoint:
                    f.label.extend(geom.coordinates)
            else:
                geom.parseGeometry(feature.label.wkb)
                if geom.isPoint:
                    f.label.extend(geom.coordinates)

        # add tags
        f.tags.extend(tags)
        if len(tags) > 1:
            f.num_tags = len(tags)

        if id is not None and id >= 0:
            f.id = id
            if feature.area:
                area = int(feature.area)  # TODO (add f.)

        if layer is not None and layer != 5:
            f.layer = layer

        if elevation is not None:
            f.elevation = int(elevation)

        if feature.kind is not None:
            f.kind = feature.kind

        if feature.type is not None:
            type = feature.type  # TODO (add f.)

        if housenumber is not None:
            f.housenumber = housenumber

        if feature.building is not None:
            if feature.building.height is not None:
                try:
                    f.height = int(feature.building.height * 100)
                except ValueError:
                    pass

            if feature.building.min_height is not None:
                try:
                    f.min_height = int(feature.building.min_height * 100)
                except ValueError:
                    pass

            if feature.building.color is not None:
                f.building_color = feature.building.color

            if feature.building.roof_color is not None:
                f.roof_color = feature.building.roof_color

            if feature.building.roof_height is not None:
                try:
                    roof_height = int(feature.building.roof_height * 100)  # TODO (add f.)
                except ValueError:
                    pass

            if feature.building.roof_shape is not None:
                roof_shape = feature.building.roof_shape  # TODO (add f.)

            if feature.building.roof_direction is not None:
                roof_direction = int(feature.building.roof_direction * 10)  # TODO (add f.)

            if feature.building.roof_across:
                roof_across = feature.building.roof_across  # TODO (add f.)

        # logging.debug('tags %d, indices %d' %(len(tags),len(f.indices)))
        self.num_features += 1

    def getLayer(self, val):
        try:
            layer = max(min(10, int(val)) + 5, 0)
            if layer != 0:
                return layer
        except ValueError:
            logging.warning("layer invalid %s" % val)

        return None

    def getKeyId(self, key):
        if key in StaticKeys.staticKeys:
            return StaticKeys.staticKeys[key]

        if key in self.keydict:
            return self.keydict[key]

        self.out.keys.append(key)

        r = self.cur_key
        self.keydict[key] = r
        self.cur_key += 1
        return r

    def getAttribId(self, var):
        if var in StaticVals.staticValues:
            return StaticVals.staticValues[var]

        if var in self.valdict:
            return self.valdict[var]

        self.out.values.append(var)

        r = self.cur_val
        self.valdict[var] = r
        self.cur_val += 1
        return r

    def getTagId(self, tag):
        if tag in self.tagdict:
            return self.tagdict[tag]

        key = self.getKeyId(tag[0])
        val = self.getAttribId(tag[1])

        self.out.tags.append(key)
        self.out.tags.append(val)
        if tag[0] not in ('ref', 'iata', 'icao', 'religion', 'osmc:symbol') \
           and (key >= ATTRIB_OFFSET or val >= ATTRIB_OFFSET):
            logging.warning("add tag %s - %d/%d" % (tag, key, val))
        r = self.num_tags
        self.tagdict[tag] = r
        self.num_tags += 1
        return r
