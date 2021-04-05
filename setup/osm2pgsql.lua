-- Useful queries:
-- SELECT key, COUNT(key) AS count FROM (SELECT skeys(tags) AS key FROM osm_polygons) AS keys GROUP BY key ORDER BY count;

inspect = require('inspect')

local srid = 3857

local prefix = 'osm_'

local tables = {}

tables.points = osm2pgsql.define_node_table(prefix .. 'points', {
    { column = 'tags', type = 'hstore' },
    { column = 'names', type = 'hstore' },
    { column = 'geom', type = 'point', projection = srid },
})

tables.lines = osm2pgsql.define_way_table(prefix .. 'lines', {
    { column = 'tags', type = 'hstore' },
    { column = 'names', type = 'hstore' },
    { column = 'geom', type = 'linestring', projection = srid },
})

tables.highways = osm2pgsql.define_way_table(prefix .. 'highways', {
    { column = 'type', type = 'text', not_null = true },
    { column = 'geom', type = 'linestring', projection = srid },
})

tables.boundaries = osm2pgsql.define_way_table(prefix .. 'boundaries', {
    { column = 'admin_level', type = 'int', not_null = true },
    { column = 'maritime', type = 'boolean', not_null = true },
    { column = 'disputed', type = 'boolean', not_null = true },
    { column = 'geom', type = 'linestring', projection = srid },
})

tables.polygons = osm2pgsql.define_area_table(prefix .. 'polygons', {
    { column = 'tags', type = 'hstore' },
    { column = 'names', type = 'hstore' },
    { column = 'label_node', type = 'int8' },
    { column = 'geom', type = 'geometry', projection = srid },
    { column = 'area', type = 'area' },
})

tables.buildings = osm2pgsql.define_area_table(prefix .. 'buildings', {
    { column = 'tags', type = 'hstore' },
    { column = 'names', type = 'hstore' },
    { column = 'label', type = 'point', projection = srid, create_only = true },
    { column = 'geom', type = 'geometry', projection = srid },
})

tables.routes = osm2pgsql.define_relation_table(prefix .. 'routes', {
    { column = 'type', type = 'text', not_null = true },
    { column = 'tags', type = 'hstore' },
    { column = 'names', type = 'hstore' },
    { column = 'geom', type = 'multilinestring', projection = srid },
})

tables.building_outlines = osm2pgsql.define_relation_table(prefix .. 'building_outlines', {
    { column = 'ref_id', type = 'int8', not_null = true },
})

local highway_types = {
    'motorway',
    'trunk',
    'primary',
    'secondary'
}

-- Prepare table "highways" for quick checking of highway types
local highways = {}
for _, k in ipairs(highway_types) do
    highways[k] = 1
end

-- This will be used to store information about relations queryable by member
-- way id. It is a table of tables. The outer table is indexed by the way id,
-- the inner table indexed by the relation id. This way even if the information
-- about a relation is added twice, it will be in there only once. It is
-- always good to write your osm2pgsql Lua code in an idempotent way, i.e.
-- it can be called any number of times and will lead to the same result.
local way2boundary = {}

-- These tag keys are generally regarded as useless for most rendering. Most
-- of them are from imports or intended as internal information for mappers.
--
-- If a key ends in '*' it will match all keys with the specified prefix.
--
-- If you want some of these keys, perhaps for a debugging layer, just
-- delete the corresponding lines.
local delete_keys = {
    -- cleaned to save space (addr:housenumber specially treated)
    'addr:*',

    -- not needed for trekarta but takes lot of space
    'official_name',
    'official_name:*',
    'old_name',
    'old_name:*',
    'alt_name',
    'alt_name:*',
    'official_status',
    'legal',
    'legal:*',
    'description',
    'description:*',

    'seamark:*',
    'railway:*',

    -- "mapper" keys
    'attribution',
    'comment',
    'created_by',
    'fixme',
    'FIXME',
    'note',
    'note:*',
    'odbl',
    'odbl:note',
    'source',
    'source2',
    'source:*',
    'source_ref',
    '*:source',

    -- "import" keys

    -- Corine Land Cover (CLC) (Europe)
    'CLC:*',
    'clc:*',

    -- Geobase (CA)
    'geobase:*',
    -- CanVec (CA)
    'canvec:*',

    -- osak (DK)
    'osak:*',
    -- kms (DK)
    'kms:*',

    -- ngbe (ES)
    -- See also note:es and source:file above
    'ngbe:*',

    -- Friuli Venezia Giulia (IT)
    'it:fvg:*',

    -- KSJ2 (JA)
    -- See also note:ja and source_ref above
    'KSJ2:*',
    -- Yahoo/ALPS (JA)
    'yh:*',

    -- LINZ (NZ)
    'LINZ2OSM:*',
    'linz2osm:*',
    'LINZ:*',
    'ref:linz:*',

    -- WroclawGIS (PL)
    'WroclawGIS:*',
    -- Naptan (UK)
    'naptan:*',

    -- TIGER (US)
    'tiger:*',
    -- GNIS (US)
    'gnis:*',
    -- National Hydrography Dataset (US)
    'NHD:*',
    'nhd:*',
    -- mvdgis (Montevideo, UY)
    'mvdgis:*',

    -- EUROSHA (Various countries)
    'project:eurosha_2012',

    -- UrbIS (Brussels, BE)
    'ref:UrbIS',

    -- NHN (CA)
    'accuracy:meters',
    'sub_sea:type',
    'waterway:type',
    -- StatsCan (CA)
    'statscan:rbuid',

    -- RUIAN (CZ)
    'ref:ruian:addr',
    'ref:ruian',
    'building:ruian:type',
    -- DIBAVOD (CZ)
    'dibavod:id',
    -- UIR-ADR (CZ)
    'uir_adr:ADRESA_KOD',

    -- GST (DK)
    'gst:feat_id',

    -- Maa-amet (EE)
    'maaamet:ETAK',
    -- FANTOIR (FR)
    'ref:FR:FANTOIR',

    -- 3dshapes (NL)
    '3dshapes:ggmodelk',
    -- AND (NL)
    'AND_nosr_r',

    -- OPPDATERIN (NO)
    'OPPDATERIN',
    -- Various imports (PL)
    'addr:city:simc',
    'addr:street:sym_ul',
    'building:usage:pl',
    'building:use:pl',
    -- TERYT (PL)
    'teryt:simc',

    -- RABA (SK)
    'raba:id',
    -- DCGIS (Washington DC, US)
    'dcgis:gis_id',
    -- Building Identification Number (New York, US)
    'nycdoitt:bin',
    -- Chicago Building Inport (US)
    'chicago:building_id',
    -- Louisville, Kentucky/Building Outlines Import (US)
    'lojic:bgnum',
    -- MassGIS (Massachusetts, US)
    'massgis:*',
    -- Los Angeles County building ID (US)
    'lacounty:*',
    -- Address import from Bundesamt für Eich- und Vermessungswesen (AT)
    'at_bev:addr_date',

    -- misc
    'import',
    'import_uuid',
    'OBJTYPE',
    'SK53_bulk:load',
    'mml:class',
    'LandPro08:*',
    'it:pv:pavia:*',
    'nysgissam:*',
    'gis-lab:*',
    'naturbase:*'
}

-- The osm2pgsql.make_clean_tags_func() function takes the list of keys
-- and key prefixes defined above and returns a function that can be used
-- to clean those tags out of a Lua table. The base_clean_tags function will
-- return true if it removed all tags from the table.
local base_clean_tags = osm2pgsql.make_clean_tags_func(delete_keys)

--- Cleans object tags preserving addr:housenumber and addr:interpolation
--- @param tags table tags table
--- @return boolean true if all tags are removed from the table
local function clean_tags(tags)
    local addr_housenumber = tags['addr:housenumber']
    local addr_interpolation = tags['addr:interpolation']

    if base_clean_tags(tags) and not addr_housenumber and not addr_interpolation then
        return true
    end

    tags['addr:housenumber'] = addr_housenumber
    tags['addr:interpolation'] = addr_interpolation
    return false
end

local delete_border_keys = {
    'boundary',
    'boundary_type',
    'border_type',
    'border_status',
    'maritime',
    'disputed',
    'dispute',
    'disputed_by',
    'left:*',
    'right:*'
}

local clean_border_tags = osm2pgsql.make_clean_tags_func(delete_border_keys)

-- Source for area treatment: https://github.com/gravitystorm/openstreetmap-carto/blob/master/openstreetmap-carto.lua
-- Objects with any of the following keys will be treated as polygon
local polygon_keys = {
    'abandoned:aeroway',
    'abandoned:amenity',
    'abandoned:building',
    'abandoned:landuse',
    'abandoned:power',
    'aeroway',
    'allotments',
    'amenity',
    'area:highway',
    'craft',
    'building',
    'building:part',
    'club',
    'golf',
    'emergency',
    'harbour',
    'healthcare',
    'historic',
    'landuse',
    'leisure',
    'man_made',
    'military',
    'natural',
    'office',
    'place',
    'power',
    'public_transport',
    'shop',
    'tourism',
    'water',
    'waterway',
    'wetland'
}

-- Objects with any of the following key/value combinations will be treated as linestring
local linestring_values = {
    golf = { cartpath = true, hole = true, path = true },
    emergency = { designated = true, destination = true, no = true, official = true, yes = true },
    historic = { citywalls = true },
    leisure = { track = true, slipway = true },
    man_made = { breakwater = true, cutline = true, embankment = true, groyne = true, pipeline = true },
    natural = { cliff = true, earth_bank = true, tree_row = true, ridge = true, arete = true },
    power = { cable = true, line = true, minor_line = true },
    tourism = { yes = true },
    waterway = { canal = true, derelict_canal = true, ditch = true, drain = true, river = true, stream = true, tidal_channel = true, wadi = true, weir = true }
}

-- Objects with any of the following key/value combinations will be treated as polygon
local polygon_values = {
    aerialway = { station = true },
    boundary = { aboriginal_lands = true, national_park = true, protected_area = true },
    highway = { services = true, rest_area = true },
    junction = { yes = true },
    railway = { station = true }
}

--- Check if an object with given tags should be treated as polygon
-- @param tags OSM tags
-- @return true if area, false if linear
function has_area_tags(tags)
    -- Treat objects tagged as area=yes polygon, other area as no
    if tags['area'] then
        return tags['area'] == 'yes'
    end

    -- Search through object's tags
    for k, v in pairs(tags) do
        -- Check if it has a polygon key and not a linestring override, or a polygon k=v
        for _, ptag in ipairs(polygon_keys) do
            if k == ptag and v ~= 'no' and not (linestring_values[k] and linestring_values[k][v]) then
                return true
            end
        end

        if (polygon_values[k] and polygon_values[k][v]) then
            return true
        end
    end
    return false
end

function osm2pgsql.process_node(object)
    if clean_tags(object.tags) then
        return
    end

    object.tags.layer = layer(object.tags.layer)
    local names = names(object.tags)

    tables.points:add_row({
        tags = object.tags,
        names = names
    })
end

function osm2pgsql.process_way(object)
    local boundaries = way2boundary[object.id]
    if boundaries or object.tags.boundary == 'administrative' then
        -- closure segments are ways added at the limits of the projection to close boundaries for valid multipolygon building
        if object.tags.closure_segment == 'yes' then
            return
        end
        local admin_level = tonumber(object:grab_tag('admin_level')) or 12
        local maritime = is_maritime(object.tags)
        local disputed = is_disputed(object.tags)

        if boundaries then
            for _, boundary in pairs(boundaries) do
                if boundary.admin_level < admin_level then
                    admin_level = boundary.admin_level
                    if boundary.disputed and not disputed then
                        disputed = boundary.disputed
                    end
                end
                if boundary.maritime and not maritime then
                    maritime = boundary.maritime
                end
            end
        end

        if admin_level < 5 then
            tables.boundaries:add_row({
                admin_level = admin_level,
                maritime = maritime,
                disputed = disputed,
                tags = object.tags,
                geom = { create = 'line' }
            })
        end

        clean_border_tags(object.tags)
    end

    if object.tags.natural == 'coastline' then
        object.tags.natural = nil
    end

    local names = names(object.tags)

    if clean_tags(object.tags) then
        return
    end

    object.tags.layer = layer(object.tags.layer)

    if object.is_closed and has_area_tags(object.tags) then
        if is_building(object.tags) then
            tables.buildings:add_row({
                tags = object.tags,
                names = names,
                geom = { create = 'area' }
            })
        else
            tables.polygons:add_row({
                tags = object.tags,
                names = names,
                geom = { create = 'area' }
            })
        end
    else
        if highways[object.tags.highway] then
            tables.highways:add_row({
                type = object.tags.highway
            })
        end

        tables.lines:add_row({
            tags = object.tags,
            names = names
        })
    end
end

function osm2pgsql.select_relation_members(relation)
    if (relation.tags.type == 'boundary' or (relation.tags.type == 'multipolygon' and relation.tags.boundary)) and relation.tags.boundary == 'administrative' and relation.tags.admin_level then
        local admin_level = tonumber(relation.tags.admin_level) or 12
        if admin_level < 5 then
            return { ways = osm2pgsql.way_member_ids(relation) }
        end
    end
end

function osm2pgsql.process_relation(object)
    local type = object:grab_tag('type')

    if clean_tags(object.tags) then
        return
    end

    if type == 'building' then
        for _, member in ipairs(object.members) do
            if member.role == 'outline' then
                local ref_id = member.ref
                if member.type == 'r' then
                    ref_id = -member.ref
                end
                tables.building_outlines:add_row({
                    ref_id = ref_id
                })
            end
        end
        return
    end

    object.tags.layer = layer(object.tags.layer)
    local names = names(object.tags)

    if type == 'route' then
        local route = object:grab_tag('route')
        if not route then
            return
        end
        -- https://www.openstreetmap.org/relation/2195143 - nested relations?
        tables.routes:add_row({
            type = route,
            tags = object.tags,
            names = names,
            geom = { create = 'line' }
        })
        return
    end

    if type == 'boundary' or (type == 'multipolygon' and object.tags.boundary) then
        if object.tags.boundary == 'administrative' then
            local admin_level = tonumber(object.tags.admin_level) or 12
            local maritime = is_maritime(object.tags)
            local disputed = is_disputed(object.tags)
            if admin_level < 5 then
                local boundary = {
                    admin_level = admin_level,
                    maritime = maritime,
                    disputed = disputed
                }

                -- Go through all the members and store relation ids and refs so they
                -- can be found by the way id.
                for _, member in ipairs(object.members) do
                    if member.type == 'w' then
                        if not way2boundary[member.ref] then
                            way2boundary[member.ref] = {}
                        end
                        way2boundary[member.ref][object.id] = boundary
                    end
                end
            end
            if not object.tags.place then
                return
            end
            clean_border_tags(object.tags)
        end

        tables.polygons:add_row({
            tags = object.tags,
            names = names,
            label_node = relation_label(object.members, true),
            geom = { create = 'area' }
        })
        return
    end

    if type == 'multipolygon' then
        if is_building(object.tags) then
            tables.buildings:add_row({
                tags = object.tags,
                names = names,
                geom = { create = 'area' }
            })
        else
            tables.polygons:add_row({
                tags = object.tags,
                names = names,
                label_node = relation_label(object.members, false),
                geom = { create = 'area' }
            })
        end
    end
end

function is_building(tags)
    return tags.building or tags['building:part']
end

local maritime_tags = {
    'boundary_type',
    'border_type',
    'boundary'
}
local maritime_values = {
    'eez',
    'maritime',
    'territorial_waters',
    'territorial waters'
}

function is_maritime(tags)
    if tags.maritime then
        return true
    end
    if tags.natural == 'coastline' then
        return true
    end
    for k, v in pairs(tags) do
        for _, mk in ipairs(maritime_tags) do
            for _, mv in ipairs(maritime_values) do
                if k == mk and v == mv then
                    return true
                end
            end
        end
    end
    return false
end

function is_disputed(tags)
    if tags.disputed or tags.dispute or tags.border_status == 'dispute' then
        return true
    end
    return false
end

--- Normalizes layer tags
--- @param v string The layer tag value
--- @return number An integer for the layer tag
function layer(v)
    return v and string.find(v, "^-?%d+$") and tonumber(v) < 100 and tonumber(v) > -100 and v or nil
end

--- Put all name:* tags in their own substructure
--- @param tags table Object tags
--- @return table Extracted names
function names(tags)
    local object_names = {}
    for k, v in pairs(tags) do
        if k == 'name' then
            object_names[''] = v
            tags.name = nil
        elseif osm2pgsql.has_prefix(k, "name:") then
            -- extract language
            local lang = k:sub(6, -1)
            tags[k] = nil
            if lang == 'en' or lang == 'de' or lang == 'ru' then
                object_names[lang] = v
            end
        end
    end
    return object_names
end

--- Get label node reference for relation
--- @param members table Relation members
--- @param is_admin boolean Relation is administrative boundary
--- @return number node id or nil
function relation_label(members, is_admin)
    local label_ref
    for _, member in ipairs(members) do
        if member.type == 'n' then
            if member.role == 'label' then
                label_ref = member.ref
            end
            if is_admin and member.role == 'admin_centre' and not label_ref then
                label_ref = member.ref
            end
        end
    end
    return label_ref
end
