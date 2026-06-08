#!/bin/bash
cd "$(dirname "$0")"
python3 build_teacher_guides.py
echo
echo "Press Return to close."
read
