#!/usr/bin/env python3

import argparse
import collections as col
import json
import math
import numpy as np
import os
import slugid
import sqlite3
import struct
import sys
import zlib

from io import BytesIO
from PIL import Image


def grey_to_rgb(arr, to_rgba=False):
    if to_rgba:
        rgb = np.zeros(arr.shape + (4,))
        rgb[:, :, 3] = 255
    else:
        rgb = np.zeros(arr.shape + (3,))

    rgb[:, :, 0] = 255 - arr * 255
    rgb[:, :, 1] = rgb[:,:,0]
    rgb[:, :, 2] = rgb[:,:,0]

    return rgb


def is_within(start1, end1, start2, end2, width, height):
    return start1 < width and end1 > 0 and start2 < height and end2 > 0


def np_to_png(arr, comp=9):
    sz = arr.shape

    # Add alpha values
    if arr.shape[2] == 3:
        out = np.ones(
            (sz[0], sz[1], sz[2] + 1)
        )
        out[:, :, 3] = 255
        out[:, :, 0:3] = arr
    else:
        out = arr

    return write_png(
        np.flipud(out).astype('uint8').flatten('C').tobytes(),
        sz[1],
        sz[0],
        comp
    )


def png_pack(png_tag, data):
    chunk_head = png_tag + data
    return (struct.pack("!I", len(data)) +
            chunk_head +
            struct.pack("!I", 0xFFFFFFFF & zlib.crc32(chunk_head)))


def write_png(buf, width, height, comp=9):
    """ buf: must be bytes or a bytearray in Python3.x,
        a regular string in Python2.x.
    """

    # reverse the vertical line order and add null bytes at the start
    width_byte_4 = width * 4
    raw_data = b''.join(
        b'\x00' + buf[span:span + width_byte_4]
        for span in np.arange((height - 1) * width_byte_4, -1, - width_byte_4)
    )

    return b''.join([
        b'\x89PNG\r\n\x1a\n',
        png_pack(b'IHDR', struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)),
        png_pack(b'IDAT', zlib.compress(raw_data, comp)),
        png_pack(b'IEND', b'')])


def get_snippet_from_image_tiles(
    tiles,
    tile_size,
    tiles_x_range,
    tiles_y_range,
    tile_start1_id,
    tile_start2_id,
    from_x,
    to_x,
    from_y,
    to_y
):
    im = (
        tiles[0]
        if len(tiles) == 1
        else Image.new(
            'RGB',
            (tile_size * len(tiles_x_range), tile_size * len(tiles_y_range))
        )
    )

    # Stitch them tiles together
    if len(tiles) > 1:
        i = 0
        for y in range(len(tiles_y_range)):
            for x in range(len(tiles_x_range)):
                im.paste(tiles[i], (x * tile_size, y * tile_size))
                i += 1

    # Convert starts and ends to local tile ids
    start1_rel = from_x - tile_start1_id * tile_size
    end1_rel = to_x - tile_start1_id * tile_size
    start2_rel = from_y - tile_start2_id * tile_size
    end2_rel = to_y - tile_start2_id * tile_size

    # Ensure that the cropped image is at least 1x1 pixel otherwise the image
    # is not returned as a numpy array but the Pillow object... (odd bug)
    x_diff = end1_rel - start1_rel
    y_diff = end2_rel - start2_rel

    if x_diff < 1.0:
        x_center = start1_rel + (x_diff / 2)
        start1_rel = x_center - 0.5
        end1_rel = x_center + 0.5

    if y_diff < 1.0:
        y_center = start1_rel + (y_diff / 2)
        start2_rel = y_center - 0.5
        end2_rel = y_center + 0.5

    # Notice the shape: height x width x channel
    return np.array(im.crop((start1_rel, start2_rel, end1_rel, end2_rel)))


def get_images(
    db,
    imtiles_info,
    x_from,
    x_to,
    y_from,
    y_to,
    zoom_from=0,
    zoom_to=math.inf,
    padding=0,
    tile_size=256,
    max_size=512
):
    div = 1
    width = 0
    height = 0

    ims = []

    max_zoom = imtiles_info['max_zoom']
    max_width = imtiles_info['max_width']
    max_height = imtiles_info['max_height']

    for zoom_level in range(zoom_from, zoom_to + 1):
        div = 2 ** (max_zoom - zoom_level)

        x1 = x_from / div
        x2 = x_to / div
        y1 = y_from / div
        y2 = y_to / div
        width = max_width / div
        height = max_height / div

        if not is_within(x1, x2, y1, y2, width, height):
            ims.append(None)
            continue

        if (
            x2 - x1 > max_size or
            y2 - y1 > max_size
        ):
            print('Too big for a preview')
            ims.append(None)
            continue

        # Get tile ids
        tile_start1_id = int(x1 // tile_size)
        tile_end1_id = int(x2 // tile_size)
        tile_start2_id = int(y1 // tile_size)
        tile_end2_id = int(y2 // tile_size)

        tiles_x_range = range(tile_start1_id, tile_end1_id + 1)
        tiles_y_range = range(tile_start2_id, tile_end2_id + 1)

        # Extract image tiles
        tiles = []
        for y in tiles_y_range:
            for x in tiles_x_range:
                tiles.append(Image.open(BytesIO(db.execute(
                    'SELECT image FROM tiles WHERE z=? AND y=? AND x=?',
                    (zoom_level, y, x)
                ).fetchone()[0])))

        im_snip = get_snippet_from_image_tiles(
            tiles,
            tile_size,
            tiles_x_range,
            tiles_y_range,
            tile_start1_id,
            tile_start2_id,
            x1,
            x2,
            y1,
            y2
        )

        ims.append((zoom_level, np_to_png(im_snip)))

    return ims


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


def create_img_cache(db):
    db.execute('''
        CREATE TABLE images
        (
            id int NOT NULL,
            z INT NOT NULL,
            image BLOB,
            PRIMARY KEY (id, z)
        )
        ''')
    db.commit()


def pre_fetch_and_save_img(
    db,
    imtiles_db,
    imtiles_info,
    id,
    x_from,
    x_to,
    y_from,
    y_to,
    zoom_from,
    zoom_to,
    max_size,
):
    query_insert_image = 'INSERT INTO images VALUES (?,?,?)'

    images = get_images(
        imtiles_db,
        imtiles_info,
        x_from,
        x_to,
        y_from,
        y_to,
        zoom_from=zoom_from,
        zoom_to=zoom_to,
        max_size=max_size
    )

    for image in images:
        if image is not None:
            db.execute(
                query_insert_image,
                (id, image[0], sqlite3.Binary(image[1]))
            )
            db.commit()


def snapshots_to_db(
    snapshots_path,
    output_file,
    tileset_info,
    max_per_tile,
    pre_fetch,
    pre_fetch_zoom_from,
    pre_fetch_zoom_to,
    pre_fetch_max_size,
    from_x,
    to_x,
    from_y,
    to_y,
    xlim_rel,
    ylim_rel,
    limit_excl,
    overwrite,
    verbose
):
    if not os.path.isfile(snapshots_path):
        sys.exit('Snapshots file not found! ☹️')

    # Read snapshots
    with open(snapshots_path, 'r') as f:
        snapshots = json.load(f)
        snapshots = sorted(snapshots, key=lambda x: -x['snapshot']['views'])

    base_dir = os.path.dirname(snapshots_path)

    if not os.path.isfile(tileset_info):
        tileset_info = os.path.join(base_dir, tileset_info)
        if not os.path.isfile(tileset_info):
            tileset_info = os.path.join(base_dir, 'info.json')
            if not os.path.isfile(tileset_info):
                sys.exit('Tile set info file not found! 😫')
            print('Info: using default tile set info file. 🤓')

    if not output_file:
        output_file = '{}.multires.db'.format(base_dir)

    if os.path.isfile(output_file):
        if overwrite:
            try:
                os.remove(output_file)
            except OSError:
                pass
        else:
            sys.exit(
                'Output exists already! 😬  Please check and remove it if ' +
                'necessary.'
            )

    # Read tile set info
    with open(tileset_info, 'r') as f:
        info = json.load(f)

    if not info:
        sys.exit('Tile set info broken! 😤')

    assert(from_x < to_x)
    assert(from_y < to_y)

    if from_x > -math.inf and xlim_rel:
        from_x = info['max_width'] * from_x

    if to_x > -math.inf and xlim_rel:
        to_x = info['max_width'] * to_x

    if from_y > -math.inf and xlim_rel:
        from_y = info['max_width'] * from_y

    if to_y > -math.inf and xlim_rel:
        to_y = info['max_width'] * to_y

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

    if pre_fetch:
        if not os.path.isfile(pre_fetch):
            pre_fetch = os.path.join(base_dir, pre_fetch)
            if not os.path.isfile(pre_fetch):
                sys.exit('Imtiles for pre-fretching is not a file! 💩')

        tileset = sqlite3.connect(pre_fetch)
        create_img_cache(db)

    counter = 0
    tile_counts = col.defaultdict(
        lambda: col.defaultdict(lambda: col.defaultdict(int))
    )
    pre_fetched = set()

    # Convert snapshots to dict
    for snapshot in snapshots:
        snapshot = snapshot['snapshot']
        snapshot['xmin'] = math.floor(snapshot['xmin'])
        snapshot['xmax'] = math.ceil(snapshot['xmax'])
        snapshot['ymin'] = math.floor(snapshot['ymin'])
        snapshot['ymax'] = math.ceil(snapshot['ymax'])

        if (
            snapshot['xmin'] > to_x or
            snapshot['xmax'] < from_x or
            snapshot['ymin'] > to_y or
            snapshot['ymax'] < from_y
        ):
            # Skip because it's outside the specified limits
            continue

        if (
            limit_excl and
            (
                snapshot['xmax'] > to_x or
                snapshot['xmin'] < from_x or
                snapshot['ymax'] > to_y or
                snapshot['ymin'] < from_y
            )
        ):
            # Skip because it's not fully inside the specified limits
            continue

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
                    json.dumps({
                        'id': snapshot['id'],
                        'created_at': snapshot['created_at'],
                        'name': snapshot['name'],
                        'description': snapshot['description'],
                    }),  # fields text
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

                if pre_fetch and tileset and counter not in pre_fetched:
                    pre_fetch_and_save_img(
                        db,
                        tileset,
                        info,
                        counter,
                        snapshot['xmin'], snapshot['xmax'],
                        snapshot['ymin'], snapshot['ymax'],
                        max(pre_fetch_zoom_from, 0),
                        min(pre_fetch_zoom_to, info['max_zoom']),
                        pre_fetch_max_size
                    )
                    pre_fetched.add(counter)

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
        default=25,
        help='maximum number of annotations per tile',
        type=int
    )

    parser.add_argument(
        '-p', '--pre-fetch',
        help='preload image pyramind for annotations from this imtiles file',
        type=str
    )

    parser.add_argument(
        '--pre-fetch-zoom-from',
        default=0,
        help='initial zoom of for preloading (farthest zoomed out)',
        type=int
    )

    parser.add_argument(
        '--pre-fetch-zoom-to',
        default=math.inf,
        help='final zoom of for preloading (farthest zoomed in)',
        type=int
    )

    parser.add_argument(
        '--pre_fetch_max_size',
        default=512,
        help='max size (in pixel) for preloading a snapshot',
        type=int
    )

    parser.add_argument(
        '--from-x',
        default=-math.inf,
        help='only include tiles which end-x is greater than this value',
        type=float
    )

    parser.add_argument(
        '--to-x',
        default=math.inf,
        help='only include tiles which start-x is smaller than this value',
        type=float
    )

    parser.add_argument(
        '--from-y',
        default=-math.inf,
        help='only include tiles which end-y is greater than this value',
        type=float
    )

    parser.add_argument(
        '--to-y',
        default=math.inf,
        help='only include tiles which start-y is smaller than this value',
        type=float
    )

    parser.add_argument(
        '--xlim-rel',
        default=False,
        action='store_true',
        help=(
            'x limits, defined via `--from-x` etc., are in percentage '
            'relative to the full size'
        ),
    )

    parser.add_argument(
        '--ylim-rel',
        default=False,
        action='store_true',
        help=(
            'y limits, defined via `--from-y` etc., are in percentage '
            'relative to the full size'
        ),
    )

    parser.add_argument(
        '--limit-excl',
        default=False,
        action='store_true',
        help=(
            'if limits are defined via `--from-x` etc. elements have to be '
            'fully inside them'
        ),
    )

    parser.add_argument(
        '-w', '--overwrite',
        default=False,
        action='store_true',
        help=(
            'overwrite output if exist'
        ),
    )

    parser.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true'
    )

    args = parser.parse_args()

    snapshots_to_db(
        args.file,
        args.output,
        args.info,
        args.max,
        args.pre_fetch,
        args.pre_fetch_zoom_from,
        args.pre_fetch_zoom_to,
        args.pre_fetch_max_size,
        args.from_x,
        args.to_x,
        args.from_y,
        args.to_y,
        args.xlim_rel,
        args.ylim_rel,
        args.limit_excl,
        args.overwrite,
        args.verbose
    )

if __name__ == '__main__':
    main()
