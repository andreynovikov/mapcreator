class Element:
    geom_type = {0: 'unknown', 1: 'node', 2: 'way', 3: 'relation'}

    def __init__(self, id, geom, tags, mapping=None):
        self.id = id
        self.geom = geom  # original geometry
        self.tags = tags
        self.mapping = mapping
        self.label = None
        self.area = None
        self.kind = None
        self.type = None
        self.building = None
        self.geometry = None  # tile processed temporary geometry

    def osm_id(self):
        t = 0
        id = None
        if self.id:
            t = self.id & 0x0000000000000003
            id = self.id >> 2
        return "%s/%s" % (Element.geom_type[t], id)

    def __str__(self):
        # geom = transform(mercator_to_wgs84, self.geom)
        # return "%s: %s\n%s\n%s\n" % (str(self.id), geom, self.tags, self.mapping)
        return "%s: %s\n%s\n%s\n" % (self.osm_id(), self.geom.__repr__(), self.tags, self.mapping)

    def __repr__(self):
        return str(self)

    def clone(self, geom):
        el = Element(self.id, geom, self.tags, self.mapping)
        el.label = self.label
        el.area = self.area
        el.kind = self.kind
        el.type = self.type
        el.building = self.building
        return el
