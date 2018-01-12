# Image Tiles to SQLite

> Aggregate an image tile set into a single SQLite database for easier and faster access.

[![demo](https://img.shields.io/badge/higlass-👍-red.svg?colorB=0f5d92)](http://higlass.io)

Querying several million of small files is not super efficient. This script creates a single SQLite database containing metadata and the image tiles as binary data to speed up file handling and tile querying.

This script can aggregate tile sets from the [Gigapan Downloader](https://github.com/flekschas/gigapan-downloader) out of the box and the created database can be imported into [HiGlass Server](https://github.com/hms-dbmi/higlass-server) to be viewed in [HiGlass](https://github.com/hms-dbmi/higlass).

## Installation

**Prerequirements**:

- Python `v3.6`

```bash
git clone https://github.com/flekschas/image-tiles-to-sqlite && cd image-tiles-to-sqlite
mkvirtualenv -a $(pwd) -p python3 im2db  // Not necessary but recommended
pip install --upgrade -r ./requirements.txt
```

---

## CLI

### Image tiles to SQLite db

```bash
usage: im2db.py [-h] [-o OUTPUT] [-i INFO] [-t {jpg,png,gif}] [-v] dir

positional arguments:
  dir                   directory of image tiles to be converted

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        name of the sqlite database to be generated
  -i INFO, --info INFO  name of the tile set info file
  -t {jpg,png,gif}, --imtype {jpg,png,gif}
                        image tile data type
  -v, --verbose         increase output verbosity
```

**Example:**

```
./im2db.py test/54825
// -> 54825.imtiles
```

**Tests:**

This runs an end-to-end test on the test data (`test/54825`)

```
./run_test.sh
```

#### What's Going On?

Take a look at [im2db.py](im2db.py); trust me, it's a short file. Under the hood the script creates a SQLite database holding following two tables:

- tileset_info
- tiles

`tileset_info` is an extension of [clodius](https://github.com/hms-dbmi/clodius)'s metadata table and holds the following columns:

- **zoom_step** [_INT_]: _not used_
- **max_length** [_INT_]: _not used_
- **assembly** [_TEXT_]: _not used_
- **chrom_names** [_TEXT_]: _not used_
- **chrom_sizes** [_TEXT_]: _not used_
- **tile_size** [_INT_]: Size in pixel of the tiles
- **max_zoom** [_INT_]: Max. zoom level.
- **max_size** [_INT_]: Max. width, i.e., `tile_size * 2^max_zoom`.
- **width** [_INT_]: Width of the image
- **height** [_INT_]: Height of the image
- **dtype** [_TEXT_]: Data type of the images. Either _jpg_, _png_, or _gif_.

`tiles` is storing the tiles's binary image data and position and consist of the following columns. The primary key is composed of `z`, `y`, and `x`.

- **z** [_INT_]: Z position of the tile.
- **y** [_INT_]: Y position of the tile.
- **x** [_INT_]: X position of the tile.
- **image** [_BLOB_]: The binary image data of a tile.

#### Display in HiGlass

```
./manage.py ingest_tileset \
  --filename imtiles/<IMTILES-NAME>.imtiles \
  --filetype imtiles \
  --datatype <jpg,png,gif> \
  --coordSystem pixel \
  --coordSystem2 pixel \
  --uid <IMTILES-NAME> \
  --name '<IMTILES-NAME>' \
  --no-upload
```


### Gigapan snapshots to BEDPE SQLite database

```
usage: snapshots2db.py [-h] [-o OUTPUT] [-i INFO] [-m MAX] [-v] file

positional arguments:
  file                  snapshots file to be converted

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        name of the sqlite database to be generated
  -i INFO, --info INFO  name of the tile set info file
  -m MAX, --max MAX     maximum number of annotations per tile
  -v, --verbose         increase output verbosity
```

#### What's Going On?

Take a look at [snapshots2db.py](snapshots2db.py). Under the hood the script creates a SQLite database holding following three tables:

- tileset_info
- tiles

`tileset_info` is an extension of [clodius](https://github.com/hms-dbmi/clodius)'s metadata table and holds the following columns:

- **zoom_step** [_INT_]: _not used_
- **max_length** [_INT_]: _not used_
- **assembly** [_TEXT_]: _not used_
- **chrom_names** [_TEXT_]: _not used_
- **chrom_sizes** [_TEXT_]: _not used_
- **tile_size** [_INT_]: Size in pixel of the tiles
- **max_zoom** [_INT_]: Max. zoom level.
- **max_size** [_INT_]: Max. width, i.e., `tile_size * 2^max_zoom`.
- **width** [_INT_]: Width of the image
- **height** [_INT_]: Height of the image

`intervals` is storing the tiles's binary image data and position and consist of the following columns. The primary key is composed of `z`, `y`, and `x`.

- **id** [_INT_]: Primary key
- **zoomLevel** [_INT_]: Zoom level
- **importance** [_REAL_]: Number of views
- **fromX** [_INT_]: Start x position
- **toX** [_INT_]: End x position
- **fromY** [_INT_]: Start y position
- **toY** [_INT_]: End y position
- **chrOffset** [_INT_]: _not used_
- **uid** [_TEXT_]: Random uuid
- **fields** [_TEXT_]: Other fields; currently holding the snapshot description

`position_index` is storing the tiles's binary image data and position and consist of the following columns. The primary key is composed of `z`, `y`, and `x`.

- **id** [_INT_]: Primary key
- **rFromX** [_INT_]: Start x position
- **rToX** [_INT_]: End x position
- **rFromY** [_INT_]: Start y position
- **rToY** [_INT_]: End y position

#### Display in HiGlass

```
./manage.py ingest_tileset \
  --filename imtiles/<IMTILES-NAME>.snapshots.db \
  --filetype 2dannodb \
  --datatype 2d-rectangle-domains \
  --coordSystem pixel \
  --coordSystem2 pixel \
  --uid <IMTILES-NAME>-snapshots \
  --name '<IMTILES-NAME> Snapshots' \
  --no-upload
```
