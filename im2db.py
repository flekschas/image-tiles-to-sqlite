#!/usr/bin/env python3

import os
import math
import sqlite3
import sys
import argparse
import json


def store_meta_data(
    db, zoom_step, max_length, assembly, chrom_names,
    chrom_sizes, tile_size, max_zoom, max_size,
    width, height, dtype
):
    db.execute('''
        CREATE TABLE tileset_info
        (
            zoom_step INT,
            max_length INT,
            assembly TEXT,
            chrom_names TEXT,
            chrom_sizes TEXT,
            tile_size INT,
            max_zoom INT,
            max_size INT,
            width INT,
            height INT,
            dtype TEXT
        )
        ''')

    db.execute(
        'INSERT INTO tileset_info VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
            zoom_step,
            max_length,
            assembly,
            chrom_names,
            chrom_sizes,
            tile_size,
            max_zoom,
            max_size,
            width,
            height,
            dtype
        )
    )
    db.commit()

    pass


def image_tiles_to_db(
    source_dir, output_file, tileset_info, im_type, verbose
):
    if not os.path.isdir(source_dir):
        sys.exit('Source directory not found! ☹️')

    tileset_info = os.path.join(source_dir, tileset_info)
    if not os.path.isfile(tileset_info):
        tileset_info = os.path.join(source_dir, 'info.json')
        if not os.path.isfile(tileset_info):
            sys.exit('Tile set info file not found! 😫')
        print('Info: using default tile set info file. 🤓')

    if not output_file:
        output_file = '{}.imtiles'.format(source_dir)

    if os.path.isfile(output_file):
        sys.exit(
            'Output exists already! 😬  Please check and remove it if ' +
            'necessary.'
        )

    # Read tile set info
    with open(tileset_info, 'r') as f:
        info = json.load(f)

    if not info:
        sys.exit('Tile set info broken! 😤')

    # Create a new SQLite db
    # this script stores data in a sqlite database
    db = sqlite3.connect(output_file)

    store_meta_data(
        db, 1, -1, None, None, None,
        info['tile_size'], info['max_zoom'],
        info['tile_size'] * (2 ** info['max_zoom']),
        info['max_width'], info['max_height'],
        im_type,
    )

    db.execute(
        '''
        CREATE TABLE tiles
        (
            z INT NOT NULL,
            y INT NOT NULL,
            x INT NOT NULL,
            image BLOB,
            PRIMARY KEY (z, y, x)
        )
        ''')
    db.commit()

    query_insert_tile = 'INSERT INTO tiles VALUES (?,?,?,?)'

    for z in range(info['max_zoom'] + 1):
        div = 2 ** (info['max_zoom'] - z)
        wt = int(math.ceil((info['max_width'] / div) / info['tile_size']))
        ht = int(math.ceil((info['max_height'] / div) / info['tile_size']))
        for y in range(ht):
            for x in range(wt):
                tile_id = '{}.{}.{}'.format(z, y, x)
                file_name = '{}.{}'.format(tile_id, im_type)
                file_path = os.path.join(source_dir, 'tiles', file_name)

                if verbose:
                    print('Insert {}'.format(file_path))

                if os.path.isfile(file_path):
                    with open(file_path, 'rb') as f:
                        im_blob = f.read()
                        db.execute(
                            query_insert_tile,
                            (z, y, x, sqlite3.Binary(im_blob))
                        )
                        db.commit()
                else:
                    sys.exit(
                        'Tile "{}" not found! 😵  Tile set is corrupted.'
                        .format(file_path)
                    )

    db.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'dir',
        help='directory of image tiles to be converted',
        type=str
    )

    parser.add_argument(
        '-o', '--output',
        help='name of the sqlite database to be generated',
        type=str
    )

    parser.add_argument(
        '-i', '--info',
        default='info.json',
        help='name of the tile set info file',
        type=str
    )

    parser.add_argument(
        '-t', '--imtype',
        default='jpg',
        choices=['jpg', 'png', 'gif'],
        help='image tile data type',
        type=str
    )

    parser.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true'
    )

    args = parser.parse_args()

    image_tiles_to_db(
        args.dir, args.output, args.info, args.imtype, args.verbose
    )

if __name__ == '__main__':
    main()
