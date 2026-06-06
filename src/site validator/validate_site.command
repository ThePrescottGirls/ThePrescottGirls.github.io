#!/bin/bash
cd "$(dirname "$0")"
/usr/local/bin/python3 validate_site.py
echo
echo "Press Return to close."
read