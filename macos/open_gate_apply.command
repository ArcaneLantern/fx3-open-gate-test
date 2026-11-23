#!/bin/bash
# FX3 (firmware 7.02): apply the A7S III's default state: 3840x2560 open gate and the rear screen at 3:2, with De-Squeeze Display set for it (four steps, then one read-only session). Not yet run on an FX3.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply "$@"
