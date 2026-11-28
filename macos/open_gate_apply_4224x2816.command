#!/bin/bash
# FX3 (firmware 7.02): apply the 4224x2816 state (NOT RUN ON A CAMERA YET): the central 4224x2816 of the sensor pixel for pixel in XAVC HS 4K and XAVC S 4K at 24p and at 30p (NTSC) / 25p (PAL), and the screen step. No XAVC S-I in this state.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply4224 "$@"
