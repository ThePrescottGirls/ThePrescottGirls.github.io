#!/bin/bash

# ------------------------------------------------------------------
# Shared header generation
#
# Disabled for now while evaluating conversion of the TPG website to
# a shared header template. Re-enable this line when ready.
# ------------------------------------------------------------------


cd "$(dirname "$0")"

HTML_DIR="../.."


echo
echo "Shared header generation is currently DISABLED."
echo


# python3 buildsite.py \
#    "$HTML_DIR/index.html" 

echo
echo "Press any key to close..."
read -n 1 -s