#!/bin/bash
# FX3 (firmware 7.02): TEST (NOT RUN ON A CAMERA YET): the new sensor step alone with the proven 3840x2560 output, encoder, screen and S-I steps.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply realrows "$@"
