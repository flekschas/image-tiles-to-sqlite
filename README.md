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
mkvirtualenv -a $(pwd) -p python3 im2sql  // Not necessaru but recommended
pip install --upgrade -r ./requirements.txt
```

---

## CLI

```bash
usage: im2sql.py [-h] [-o OUTPUT] [-i INFO] [-t {jpg,png,gif}] [-v] dir

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
./im2sql.py test/54825
// -> 54825.imtiles
```

**Tests:**

This runs an end-to-end test on the test data (`test/54825`)

```
./run_test.sh
```
---

## What's Going On?

Take a look at [im2sql.py](im2sql.py); trust me, it's a short file. Under the hood the script creates a SQLite database holding following two tables:

- tileset_metadata
- tiles

`tileset_metadata` is an extension of [clodius](https://github.com/pkerp/clodius)'s metadata table and holds the following columns:

- **zoom_step** [_INT_]: _not used_
- **max_length** [_INT_]: _not used_
- **assembly** [_TEXT_]: _not used_
- **chrom_names** [_TEXT_]: _not used_
- **chrom_sizes** [_TEXT_]: _not used_
- **tile_size** [_INT_]: Size in pixel of the tiles
- **max_zoom** [_INT_]: Max. zoom level.
- **max_height** [_INT_]: Max. height, i.e., height at max. zoom level.
- **max_width** [_INT_]: Max. width, i.e., width at max. zoom level.
- **dtype** [_TEXT_]: Data type of the images. Either _jpg_, _png_, or _gif_.

`tiles` is storing the tiles's binary image data and position and consist of the following columns:

- **id** [_VARCHAR(18)_]: Primary key and tile ID. (zz.yyyyyyy.xxxxxxx)
- **x** [_INT_]: X position of the tile.
- **y** [_INT_]: Y position of the tile.
- **z** [_INT_]: Z position of the tile.
- **image** [_BLOB_]: The binary image data of a tile.