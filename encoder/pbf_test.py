#!/usr/bin/env python

#
# protoc --python_out=. proto/TileData.proto
#

import sys
import TileData_v4_pb2

if __name__ == "__main__" :
    if len(sys.argv) != 2 :
        print("Usage: %s <osmtile>" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    tile = TileData_v4_pb2.Data()

    try:
        f = open(sys.argv[1], "rb")
        tile.ParseFromString(f.read())
        f.close()
    except IOError:
        print(sys.argv[1] + ": Could not open file.  Creating a new one.")

    print(tile)
