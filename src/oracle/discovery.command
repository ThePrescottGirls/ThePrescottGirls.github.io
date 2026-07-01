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
echo "DISCOVERY"
echo "==========================================="
echo "Oracle Website Discovery"
echo "Python: $(python --version)"
echo

# ------------------------------------------------------------
# Development defaults
# ------------------------------------------------------------

PROPERTY="${1:-https://www.theprescottgirls.com}"
SITEMAP="${2:-../../sitemap.xml}"

python discovery.py "$PROPERTY" "$SITEMAP"

echo
echo "Press Return to close."
read