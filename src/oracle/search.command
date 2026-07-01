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
echo "SEARCH"
echo "==========================================="
echo "Oracle Search Queries"
echo "Python: $(python --version)"
echo

python search.py

echo
echo "Press Return to close."
read