#!/bin/bash
# Build the eight FX3 write libraries from the A7 IV helper's source (helper/readcheck.c), with this build's tables and constants.
# usage: build_fx3_write.sh        (writes libJit_fx3_L<level>.so for levels 5 6 16 17 19 20, and libJit_fx3_S16.so / _S17.so)
# The FX3 counterpart of helper_s3/build_s3_write.sh (the A7S III kit, which ran on an A7S III). Flags are those of helper/rebuild.sh.
# Differences from the A7S III build: the headers of gen_fx3_write.py, the FX3 7.02 libsencore.so to link against, and for levels 5/6
# the sensor object's address (0x127ab68; the drive-parameter pointer is at control +0x698 as on the A7S III; record 0x15c bytes).
# No C19/C20: the FX3 kit has no preview-key routine (the camera's own Anamorphic Desqueeze is kept).
set -e
H="$(cd "$(dirname "$0")" && pwd)"
SEN="$H/../../../work/extracted/fx3_702/0700_part_image/dev/nflasha15/lib/libsencore.so"
cd "$H/../helper"
CC=(../../../work/venv_zig/Scripts/python.exe -m ziglang cc -target aarch64-linux-gnu -std=gnu11 -O1 -Wall -Wextra -Werror -fPIC -shared -nostdlib -ffreestanding
    -fno-stack-protector -fno-builtin -fno-asynchronous-unwind-tables -Wl,-soname,libJit.so -Wl,--no-undefined -Wl,-z,now -g0 -s -Wl,-z,max-page-size=4096)
for L in 5 6; do
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogsq_fx3_v1.h"' '-DDESIGN_LABEL="ogsq_fx3_v1"' -DIMAGER=0x127ab68UL -DCTRL_DRVPARAM=0x698U \
    readcheck.c "$SEN" -o "$H/libJit_fx3_L$L.so"
done
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz2560_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_L$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_L$L.so"
done
# The rear-screen step: the same levels 16/17 with the screen and de-squeeze words.
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_lcd32dsq_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_S$L.so"
done
cd "$H"
for L in 5 6 16 17 19 20; do echo "$(sha256sum libJit_fx3_L$L.so | cut -d' ' -f1) $(stat -c %s libJit_fx3_L$L.so) level $L"; done
for N in S16 S17; do echo "$(sha256sum libJit_fx3_$N.so | cut -d' ' -f1) $(stat -c %s libJit_fx3_$N.so) step $N"; done
