#!/usr/bin/env python3

import os
import sqlite3
import sys
import argparse
import json
import slugid
import math
import collections as col


def store_meta_data(
    db, zoom_step, max_length, assembly, chrom_names,
    chrom_sizes, tile_size, max_zoom, max_size, width, height
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
            height INT
        )
        ''')

    db.execute(
        'INSERT INTO tileset_info VALUES (?,?,?,?,?,?,?,?,?,?)', (
            zoom_step,
            max(width, height),
            assembly,
            chrom_names,
            chrom_sizes,
            tile_size,
            max_zoom,
            max_size,
            width,
            height
        )
    )
    db.commit()

    pass


def snapshot_to_bedpe(snapshot):
    return snapshot


def snapshots_to_db(
    snapshots_path, output_file, tileset_info, max_per_tile, verbose
):
    if not os.path.isfile(snapshots_path):
        sys.exit('Snapshots file not found! ☹️')

    # Read snapshots
    with open(snapshots_path, 'r') as f:
        snapshots = json.load(f)
        snapshots = sorted(snapshots, key=lambda x: -x['snapshot']['views'])

    base_dir = os.path.dirname(snapshots_path)

    tileset_info = os.path.join(base_dir, tileset_info)
    if not os.path.isfile(tileset_info):
        tileset_info = os.path.join(base_dir, 'info.json')
        if not os.path.isfile(tileset_info):
            sys.exit('Tile set info file not found! 😫')
        print('Info: using default tile set info file. 🤓')

    if not output_file:
        output_file = '{}.multires.db'.format(base_dir)

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
    # sqlite3.register_adapter(np.int64, lambda val: int(val))
    db = sqlite3.connect(output_file)

    store_meta_data(
        db, 1, -1, None, None, None,
        info['tile_size'], info['max_zoom'],
        info['tile_size'] * (2 ** info['max_zoom']),
        info['max_width'], info['max_height']
    )

    db.execute('''
        CREATE TABLE intervals
        (
            id int PRIMARY KEY,
            zoomLevel int,
            importance real,
            fromX int,
            toX int,
            fromY int,
            toY int,
            chrOffset int,
            uid text,
            fields text
        )''')

    db.execute('''
        CREATE VIRTUAL TABLE position_index USING rtree(
            id,
            rFromX, rToX,
            rFromY, rToY
        )''')

    counter = 0
    tile_counts = col.defaultdict(
        lambda: col.defaultdict(lambda: col.defaultdict(int))
    )

    # Convert snapshots to dict
    for snapshot in snapshots:
        snapshot = snapshot['snapshot']
        snapshot['xmin'] = math.floor(snapshot['xmin'])
        snapshot['xmax'] = math.ceil(snapshot['xmax'])
        snapshot['ymin'] = math.floor(snapshot['ymin'])
        snapshot['ymax'] = math.ceil(snapshot['ymax'])

        for z in range(info['max_zoom'] + 1):
            tile_width = info['tile_size'] * 2 ** (info['max_zoom'] - z)

            # Tile IDs (not tiles)
            tile_id_start_x = math.floor(snapshot['xmin'] / tile_width)
            tile_id_end_x = math.ceil(snapshot['xmax'] / tile_width)
            tile_id_start_y = math.floor(snapshot['ymin'] / tile_width)
            tile_id_end_y = math.ceil(snapshot['ymax'] / tile_width)

            tile_is_full = False

            # check if any of the tiles at this zoom level are full
            for i in range(tile_id_start_x, tile_id_end_x + 1):
                if tile_is_full:
                    continue

                for j in range(tile_id_start_y, tile_id_end_y + 1):
                    if tile_counts[z][i][j] > max_per_tile:

                        tile_is_full = True
                        continue

            if not tile_is_full:
                # they're all not full yet so add this interval
                for i in range(tile_id_start_x, tile_id_end_x + 1):
                    for j in range(tile_id_start_y, tile_id_end_y + 1):
                        tile_counts[z][i][j] += 1

                annotation = (
                    counter,
                    z,
                    float(snapshot['views']),  # importance real
                    snapshot['xmin'],  # fromX int,
                    snapshot['xmax'],  # toX int,
                    snapshot['ymin'],  # fromY int,
                    snapshot['ymax'],  # toY int,
                    0,  # chrOffset int,
                    slugid.nice().decode('utf-8'),  # uid text,
                    snapshot['description'],  # fields text
                )

                insert_anno =\
                    'INSERT INTO intervals VALUES (?,?,?,?,?,?,?,?,?,?)'

                db.execute(insert_anno, annotation)
                db.commit()

                insert_pos = 'INSERT INTO position_index VALUES (?,?,?,?,?)'
                db.execute(
                    insert_pos,
                    (
                        counter,
                        snapshot['xmin'], snapshot['xmax'],
                        snapshot['ymin'], snapshot['ymax']
                    )
                )
                db.commit()

                counter += 1
                break


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'file',
        help='snapshots file to be converted',
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
        '-m', '--max',
        default=20,
        help='maximum number of annotations per tile',
        type=int
    )

    parser.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true'
    )

    args = parser.parse_args()

    snapshots_to_db(
        args.file, args.output, args.info, args.max, args.verbose
    )

if __name__ == '__main__':
    main()
