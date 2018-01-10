#!/usr/bin/env python3

import os
import sqlite3
import sys
import argparse
import json
import math
import pathlib


def test(tileset, output, verbose):
    if not os.path.isfile(tileset):
        sys.exit('Gimme an existing file! 😡')

    if not output:
        output = 'test/out'

    basename = os.path.split(tileset)[1].split('.')[0]

    # Connect to SQLite db
    db = sqlite3.connect(tileset)

    (
        _, _, _, _, _,
        tile_size, max_zoom, max_height, max_width, dtype
    ) = db.execute('SELECT * FROM tileset_info').fetchone()

    if not tile_size:
        sys.exit('Tile size ({}) invalid!'.format(tile_size))
    if not max_zoom and max_zoom != 0:
        sys.exit('Max zoom ({}) invalid!'.format(max_zoom))
    if not max_height:
        sys.exit('Max height ({}) invalid!'.format(max_height))
    if not max_width:
        sys.exit('Max width ({}) invalid!'.format(max_width))
    if not dtype:
        sys.exit('Data type ({}) invalid!'.format(dtype))

    pathlib.Path(
        '{}/{}/tiles'.format(output, basename)
    ).mkdir(parents=True, exist_ok=True)

    file_path = os.path.join(output, basename, 'info.json')
    with open(file_path, 'w') as f:
        json.dump({
            "tile_size": tile_size,
            "max_width": max_width,
            "max_height": max_height,
            "max_zoom": max_zoom
        }, f)

    for z in range(max_zoom + 1):
        div = 2 ** (max_zoom - z)
        wt = int(math.ceil((max_width / div) / tile_size))
        ht = int(math.ceil((max_height / div) / tile_size))
        for y in range(ht):
            for x in range(wt):
                id = '{}.{}.{}'.format(z, y, x)

                sql = 'SELECT id, image FROM tiles WHERE id = :id'
                param = {'id': id}
                _, image_blob = db.execute(sql, param).fetchone()

                filename = '{}.{}'.format(id, dtype)
                file_path = os.path.join(output, basename, 'tiles', filename)

                if verbose:
                    print('Write {}'.format(file_path))

                with open(file_path, 'wb') as f:
                    f.write(image_blob)

    db.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "file",
        help="image tile set file to be tested",
        type=str
    )

    parser.add_argument(
        '-o', '--output',
        help='name of the sqlite database to be generated',
        type=str
    )

    parser.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true'
    )

    args = parser.parse_args()

    test(args.file, args.output, args.verbose)

if __name__ == '__main__':
    main()
