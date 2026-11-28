#!/bin/bash
# Build the ten FX3 write libraries from the A7 IV helper's source (helper/readcheck.c), with this build's tables and constants.
# usage: build_fx3_write.sh        (writes libJit_fx3_L<level>.so for levels 5 6 16 17 19 20, libJit_fx3_S16.so / _S17.so, N19 / N20, P29 / P30, I19 / I20 and O5)
# 2026-11-26 (open gate at 25p and 29.97p too): L5/L6 carry ogsq_fx3_v2 (v1's cells + drive mode 0x820, the stored records of 0x820 and 0x8c0 in NTSC
# and PAL form: MULTI_REC), L19/L20 ogfile2560_hs_s_fx3_v3 (+ 29.97p), I19/I20 ogfilesi2560_fx3_v2 (+ 29.97p). O5 is the earlier L5 (ogsq_fx3_v1,
# 24p only, NTSC record only), byte for byte: fx3_apply.py apply --only-24p. Its put back is the new L6, which puts back either.
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
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogsq_fx3_v2.h"' '-DDESIGN_LABEL="ogsq_fx3_v2"' -DIMAGER=0x127ab68UL -DCTRL_DRVPARAM=0x698U \
    readcheck.c "$SEN" -o "$H/libJit_fx3_L$L.so"
done
"${CC[@]}" -DLEVEL=5 '-DSITES_H="expected_sites_ogsq_fx3_v1.h"' '-DDESIGN_LABEL="ogsq_fx3_v1"' -DIMAGER=0x127ab68UL -DCTRL_DRVPARAM=0x698U \
  readcheck.c "$SEN" -o "$H/libJit_fx3_O5.so"
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz2560_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_L$L.so"
done
# Levels 19/20: the encoder side with the MP4 header heights (ogfile2560_hs_s_fx3_v2, 2026-11-25: tkhd, stsd and Sony's PROF say 3840x2560,
# as the A7 IV's ogfile2560_hs_s_v2). N19/N20: the same levels with the first kit's ogfile2560_hs_s_fx3_v1 (no header heights; it ran on an FX3).
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_fx3_v3.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_L$L.so"
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_N$L.so"
done
# The rear-screen step: the same levels 16/17 with the screen and de-squeeze words.
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_lcd32dsq_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_S$L.so"
done
# Levels 29/30 (2026-11-25): the playback decoder in the A7 IV's form (avdec8k_fx3_v1): four code words and one data word of av-cam.bin, with
# the instruction-cache handling of readcheck.c levels 29 and 30. An optional step of its own (P29 apply, P30 put back).
for L in 29 30; do
  "${CC[@]}" -DLEVEL=$L '-DAD_H="expected_ad_avdec8k_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_P$L.so"
done
# I19/I20 (2026-11-25): the same levels 19/20 with ogfilesi2560_fx3_v1, XAVC S-I 4K at 3840x2560 (the A7 IV's ogfilesi2560_v1 at the FX3's tables).
# One more step of the apply, after the others; its sites are none of L19's.
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfilesi2560_fx3_v2.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_I$L.so"
done
# The 4224 x 2816 state (2026-11-28; modding/FX3_PORT.md): the same levels with other tables. H = sensor side with the first stage passed one to one
# (ogh2816_fx3_v1: v2's cells, MULTI_REC), D = output planes (dmm7slot_fx3_v1), K = output size and encoder side at 4224 x 2816, J = the encoder side
# without the MP4 header size (K20 puts it back too), R = the encoder side with the 100M settings at 300 Mbps.
for L in 5 6; do
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogh2816_fx3_v1.h"' '-DDESIGN_LABEL="ogh2816_fx3_v1"' -DIMAGER=0x127ab68UL -DCTRL_DRVPARAM=0x698U \
    readcheck.c "$SEN" -o "$H/libJit_fx3_H$L.so"
done
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_dmm7slot_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_D$L.so"
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz4224_fx3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_fx3_K$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile4224_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_K$L.so"
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile4224r300_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_R$L.so"
done
"${CC[@]}" -DLEVEL=19 '-DMP_H="expected_mp_ogfile4224nm_fx3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_fx3_J19.so"
cd "$H"
for L in 5 6 16 17 19 20; do echo "$(sha256sum libJit_fx3_L$L.so | cut -d' ' -f1) $(stat -c %s libJit_fx3_L$L.so) level $L"; done
for N in N19 N20 S16 S17 P29 P30 I19 I20 O5 H5 H6 D16 D17 K16 K17 K19 K20 J19 R19 R20; do echo "$(sha256sum libJit_fx3_$N.so | cut -d' ' -f1) $(stat -c %s libJit_fx3_$N.so) step $N"; done
