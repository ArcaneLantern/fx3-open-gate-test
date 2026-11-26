#!/bin/bash
# FX3 (firmware 7.02): apply the default state with the earlier sensor step: open gate at 24p only (NTSC only; the sensor step that ran on FX3s).
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply --only-24p "$@"
