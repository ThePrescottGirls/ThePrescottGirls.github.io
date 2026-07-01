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

echo
echo "==========================================="
echo "ORACLE"
echo "==========================================="
echo "Python: $(python --version)"
echo

# Default property during development
PROPERTY="${1:-https://www.theprescottgirls.com}"

python oracle.py "$PROPERTY"

echo
echo "Press Return to close."
read