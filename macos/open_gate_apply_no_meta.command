#!/bin/bash
# FX3 (firmware 7.02): apply the default state with the first kit's encoder step: the files' MP4 headers keep saying 3840x2160.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --no-meta "$@"
