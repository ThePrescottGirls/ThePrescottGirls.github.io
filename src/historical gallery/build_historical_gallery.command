#!/bin/bash
cd "$(dirname "$0")"
python3 build_historical_gallery.py
echo
echo "Press Return to close."
read
