#!/bin/bash
# FX3 (firmware 7.02): apply the default state without the screen step (open gate in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K).
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --no-screen "$@"
