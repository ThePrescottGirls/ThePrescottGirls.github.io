#!/bin/bash

# Change to the Oracle project root
cd "$(dirname "$0")"

# Activate the local virtual environment
source .venv/bin/activate

# Generate API documentation
python -m pdoc *.py -o docs/api

# Open the documentation
open docs/api/index.html