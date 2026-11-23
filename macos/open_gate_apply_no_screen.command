#!/bin/bash
# FX3 (firmware 7.02): apply only the three open-gate steps (sensor, output size, encoder), without the screen step.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --no-screen "$@"
