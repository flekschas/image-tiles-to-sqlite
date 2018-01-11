#!/usr/bin/env bash

rm -f test/54825.imtiles
rm -rf test/out

./im2db.py test/54825 -o test/54825.imtiles -v
./test.py test/54825.imtiles -o test/out -v
