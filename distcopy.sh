#!/bin/sh

echo "Copying to $1"
mkdir -p "$1"
cp .tox/dist/* "$1"/
ls "$1"
