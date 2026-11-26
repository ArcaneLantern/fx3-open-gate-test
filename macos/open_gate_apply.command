#!/bin/bash
# FX3 (firmware 7.02): apply the default state: 3840x2560 open gate in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 24p and at 30p (NTSC) / 25p (PAL), and the rear screen at 3:2 with De-Squeeze Display set for it (five steps, then one read-only session). Open gate at 24p and the screen ran on FX3s, 25p on a tester's FX3; 30p and the S-I step are new.
# WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" apply apply "$@"
