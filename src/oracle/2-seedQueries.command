#!/bin/bash

set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv

    source .venv/bin/activate

    echo "Installing Python packages..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
else
    source .venv/bin/activate
fi

clear

echo "==========================================="
echo "SEED QUERIES"
echo "==========================================="
echo "Oracle Query Generator"
echo "Python: $(python --version)"
echo

python seedQueries.py

echo
echo "Press Return to close."
read