import logging
from numbers import Number

from . import TileData_pb2

from . import GeomEncoder
from . import StaticVals
from . import StaticKeys

# custom keys/values start at attrib_offset
attrib_offset = 1024

# coordindates are scaled to this range within tile
extents = 4096

# tiles are padded by this number of pixels for the current zoom level (OSciMap uses this to cover up seams between tiles)
padding = 5

def encode(features, mappings=None):
    vector_tile = VectorTile(extents, mappings)
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
        self.cur_key = attrib_offset

        self.valdict = {}
        self.cur_val = attrib_offset

        self.tagdict = {}
        self.num_tags = 0

        self.out = TileData_pb2.Data()
        self.out.version = 1


    def complete(self):
        if self.num_tags == 0:
            logging.debug("empty tags")

        self.out.num_tags = self.num_tags

        if self.cur_key - attrib_offset > 0:
            self.out.num_keys = self.cur_key - attrib_offset

        if self.cur_val - attrib_offset > 0:
            self.out.num_vals = self.cur_val - attrib_offset


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

            tag = str(k), str(v)

            tags.append(self.getTagId(tag))

        if len(tags) == 0:
            logging.warning('missing tags')
            return

        geom.parseGeometry(feature.geometry.wkb)
        f = None;

        geometry_type = None
        if geom.isPoint:
            geometry_type = 'Point'
            f = self.out.points.add()
            # add number of points (for multi-point)
            if len(geom.coordinates) > 2:
                logging.info('points %s' %len(geom.coordinates))
                f.indices.add(geom.coordinates/2)
        else:
            # empty geometry
            if len(geom.index) == 0:
                logging.debug('empty geom: %s %s' % row[1])
                return

            if geom.isPoly:
                geometry_type = 'Polygon'
                f = self.out.polygons.add()
            else:
                geometry_type = 'LineString'
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
            geom.parseGeometry(feature.label.wkb)
            if geom.isPoint:
                f.label.extend(geom.coordinates)

        # add tags
        f.tags.extend(tags)
        if len(tags) > 1:
            f.num_tags = len(tags)

        # add id
        if id is not None and id >= 0:
            f.id = id

        # add osm layer
        if layer is not None and layer != 5:
            f.layer = layer

        if elevation is not None:
            f.elevation = int(elevation)

        if feature.height is not None:
            try:
                f.height = int(feature.height * 100)
            except:
                pass

        if feature.min_height is not None:
            try:
                f.min_height = int(feature.min_height * 100)
            except:
                pass

        if feature.kind is not None:
            f.kind = feature.kind

        if feature.building_color is not None:
            f.building_color = feature.building_color

        if feature.roof_color is not None:
            f.roof_color = feature.roof_color

        if housenumber is not None:
            f.housenumber = housenumber

        #logging.debug('tags %d, indices %d' %(len(tags),len(f.indices)))


    def getLayer(self, val):
        try:
            l = max(min(10, int(val)) + 5, 0)
            if l != 0:
                return l
        except ValueError:
            logging.debug("layer invalid %s" %val)

        return None

    def getKeyId(self, key):
        if key in StaticKeys.staticKeys:
            return StaticKeys.staticKeys[key]

        if key in self.keydict:
            return self.keydict[key]

        self.out.keys.append(key);

        r = self.cur_key
        self.keydict[key] = r
        self.cur_key += 1
        return r

    def getAttribId(self, var):
        if var in StaticVals.staticValues:
            return StaticVals.staticValues[var]

        if var in self.valdict:
            return self.valdict[var]

        self.out.values.append(var);

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
        if tag[0] not in ('ref','iata','icao','population') and (key > attrib_offset or val > attrib_offset):
            logging.warning("add tag %s - %d/%d" % (tag, key, val))
        r = self.num_tags
        self.tagdict[tag] = r
        self.num_tags += 1
        return r
