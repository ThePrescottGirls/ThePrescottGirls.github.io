#!/bin/bash
cd "$(dirname "$0")"
/usr/local/bin/python3 build_sitemap.py
echo
echo "Press Return to close."
read
