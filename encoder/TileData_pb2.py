# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: TileData.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='TileData.proto',
  package='org.oscim.database.oscimap4',
  syntax='proto2',
  serialized_pb=_b('\n\x0eTileData.proto\x12\x1borg.oscim.database.oscimap4\"\x87\x05\n\x04\x44\x61ta\x12\x0f\n\x07version\x18\x01 \x02(\r\x12\x11\n\ttimestamp\x18\x02 \x01(\x04\x12\r\n\x05water\x18\x03 \x01(\x08\x12\x10\n\x08num_tags\x18\x0b \x02(\r\x12\x13\n\x08num_keys\x18\x0c \x01(\r:\x01\x30\x12\x13\n\x08num_vals\x18\r \x01(\r:\x01\x30\x12\x0c\n\x04keys\x18\x0e \x03(\t\x12\x0e\n\x06values\x18\x0f \x03(\t\x12\x10\n\x04tags\x18\x10 \x03(\rB\x02\x10\x01\x12\x38\n\x05lines\x18\x15 \x03(\x0b\x32).org.oscim.database.oscimap4.Data.Element\x12;\n\x08polygons\x18\x16 \x03(\x0b\x32).org.oscim.database.oscimap4.Data.Element\x12\x39\n\x06points\x18\x17 \x03(\x0b\x32).org.oscim.database.oscimap4.Data.Element\x1a\xad\x02\n\x07\x45lement\x12\x16\n\x0bnum_indices\x18\x01 \x01(\r:\x01\x31\x12\x13\n\x08num_tags\x18\x02 \x01(\r:\x01\x31\x12\n\n\x02id\x18\x04 \x01(\x04\x12\x10\n\x04tags\x18\x0b \x03(\rB\x02\x10\x01\x12\x13\n\x07indices\x18\x0c \x03(\rB\x02\x10\x01\x12\x17\n\x0b\x63oordinates\x18\r \x03(\x11\x42\x02\x10\x01\x12\x10\n\x05layer\x18\x15 \x01(\r:\x01\x35\x12\x11\n\x05label\x18\x1f \x03(\x11\x42\x02\x10\x01\x12\x0c\n\x04kind\x18  \x01(\r\x12\x11\n\televation\x18! \x01(\x11\x12\x0e\n\x06height\x18\" \x01(\x11\x12\x12\n\nmin_height\x18# \x01(\x11\x12\x16\n\x0e\x62uilding_color\x18$ \x01(\r\x12\x12\n\nroof_color\x18% \x01(\r\x12\x13\n\x0bhousenumber\x18& \x01(\t')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)




_DATA_ELEMENT = _descriptor.Descriptor(
  name='Element',
  full_name='org.oscim.database.oscimap4.Data.Element',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='num_indices', full_name='org.oscim.database.oscimap4.Data.Element.num_indices', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='num_tags', full_name='org.oscim.database.oscimap4.Data.Element.num_tags', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='id', full_name='org.oscim.database.oscimap4.Data.Element.id', index=2,
      number=4, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='tags', full_name='org.oscim.database.oscimap4.Data.Element.tags', index=3,
      number=11, type=13, cpp_type=3, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
    _descriptor.FieldDescriptor(
      name='indices', full_name='org.oscim.database.oscimap4.Data.Element.indices', index=4,
      number=12, type=13, cpp_type=3, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
    _descriptor.FieldDescriptor(
      name='coordinates', full_name='org.oscim.database.oscimap4.Data.Element.coordinates', index=5,
      number=13, type=17, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
    _descriptor.FieldDescriptor(
      name='layer', full_name='org.oscim.database.oscimap4.Data.Element.layer', index=6,
      number=21, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=5,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='label', full_name='org.oscim.database.oscimap4.Data.Element.label', index=7,
      number=31, type=17, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
    _descriptor.FieldDescriptor(
      name='kind', full_name='org.oscim.database.oscimap4.Data.Element.kind', index=8,
      number=32, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='elevation', full_name='org.oscim.database.oscimap4.Data.Element.elevation', index=9,
      number=33, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='height', full_name='org.oscim.database.oscimap4.Data.Element.height', index=10,
      number=34, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='min_height', full_name='org.oscim.database.oscimap4.Data.Element.min_height', index=11,
      number=35, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='building_color', full_name='org.oscim.database.oscimap4.Data.Element.building_color', index=12,
      number=36, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='roof_color', full_name='org.oscim.database.oscimap4.Data.Element.roof_color', index=13,
      number=37, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='housenumber', full_name='org.oscim.database.oscimap4.Data.Element.housenumber', index=14,
      number=38, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=394,
  serialized_end=695,
)

_DATA = _descriptor.Descriptor(
  name='Data',
  full_name='org.oscim.database.oscimap4.Data',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='version', full_name='org.oscim.database.oscimap4.Data.version', index=0,
      number=1, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='timestamp', full_name='org.oscim.database.oscimap4.Data.timestamp', index=1,
      number=2, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='water', full_name='org.oscim.database.oscimap4.Data.water', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='num_tags', full_name='org.oscim.database.oscimap4.Data.num_tags', index=3,
      number=11, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='num_keys', full_name='org.oscim.database.oscimap4.Data.num_keys', index=4,
      number=12, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='num_vals', full_name='org.oscim.database.oscimap4.Data.num_vals', index=5,
      number=13, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='keys', full_name='org.oscim.database.oscimap4.Data.keys', index=6,
      number=14, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='values', full_name='org.oscim.database.oscimap4.Data.values', index=7,
      number=15, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='tags', full_name='org.oscim.database.oscimap4.Data.tags', index=8,
      number=16, type=13, cpp_type=3, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
    _descriptor.FieldDescriptor(
      name='lines', full_name='org.oscim.database.oscimap4.Data.lines', index=9,
      number=21, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='polygons', full_name='org.oscim.database.oscimap4.Data.polygons', index=10,
      number=22, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='points', full_name='org.oscim.database.oscimap4.Data.points', index=11,
      number=23, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_DATA_ELEMENT, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=48,
  serialized_end=695,
)

_DATA_ELEMENT.containing_type = _DATA
_DATA.fields_by_name['lines'].message_type = _DATA_ELEMENT
_DATA.fields_by_name['polygons'].message_type = _DATA_ELEMENT
_DATA.fields_by_name['points'].message_type = _DATA_ELEMENT
DESCRIPTOR.message_types_by_name['Data'] = _DATA

Data = _reflection.GeneratedProtocolMessageType('Data', (_message.Message,), dict(

  Element = _reflection.GeneratedProtocolMessageType('Element', (_message.Message,), dict(
    DESCRIPTOR = _DATA_ELEMENT,
    __module__ = 'TileData_pb2'
    # @@protoc_insertion_point(class_scope:org.oscim.database.oscimap4.Data.Element)
    ))
  ,
  DESCRIPTOR = _DATA,
  __module__ = 'TileData_pb2'
  # @@protoc_insertion_point(class_scope:org.oscim.database.oscimap4.Data)
  ))
_sym_db.RegisterMessage(Data)
_sym_db.RegisterMessage(Data.Element)


_DATA_ELEMENT.fields_by_name['tags'].has_options = True
_DATA_ELEMENT.fields_by_name['tags']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
_DATA_ELEMENT.fields_by_name['indices'].has_options = True
_DATA_ELEMENT.fields_by_name['indices']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
_DATA_ELEMENT.fields_by_name['coordinates'].has_options = True
_DATA_ELEMENT.fields_by_name['coordinates']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
_DATA_ELEMENT.fields_by_name['label'].has_options = True
_DATA_ELEMENT.fields_by_name['label']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
_DATA.fields_by_name['tags'].has_options = True
_DATA.fields_by_name['tags']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
# @@protoc_insertion_point(module_scope)
