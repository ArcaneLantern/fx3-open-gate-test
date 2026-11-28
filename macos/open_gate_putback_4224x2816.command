#!/bin/bash
# FX3 (firmware 7.02): put the 4224x2816 state back to stock. After the 300 Mbps apply use open_gate_putback_4224x2816_300mbps.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply putback4224 "$@"
