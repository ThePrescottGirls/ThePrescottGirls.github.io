#!/bin/bash
cd "$(dirname "$0")"
python3 build_research_docs.py
echo
echo "Press Return to close."
read
