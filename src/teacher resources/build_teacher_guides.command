#!/bin/bash
cd "$(dirname "$0")"
/usr/local/bin/python3 build_teacher_guides.py
echo
echo "Press Return to close."
read
