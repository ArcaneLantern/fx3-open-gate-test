# FX3 7.02 in PAL: open gate at 25p needs drive mode 0x820 (physical results)

Test date: 2026-11-25. One Sony ILME-FX3, firmware 7.02, PAL (50 system), XAVC S 4K, 25p, 140M 4:2:2 10-bit. Same tester and camera as `FX3-UPSTREAM-TEST-REPORT-2026-11-24.md`.

## Scope and provenance

These are physical results from the same separate, locally instrumented implementation as the first report (three write stages, preimage checks, readback, cold-start verification). They do **not** certify this repository's launchers, helpers, Android app or macOS transport. The sensor design below is `ogsq_fx3_v1` moved to another drive mode; it was built on a PC from `cpapp-b.bin` 7.02 and this repository's published design, and is contributed as data (`windows/tools/modding/designs/ogsq_fx3_pal25_mode0x820_contrib.json`), not as a tested step of this kit.

## Summary

- **At 25p the FX3 does not use drive mode 0x8c0.** It uses 0x820 (index 10). With the 0x8c0 sensor cells and stored record applied, a PAL 25p recording is a 16:9 picture stretched into 3840 × 2560 with a wrong black level and an empty band at the bottom.
- **The same design on mode 10's rows, with a 25 fps timing row, gives open gate at 25p.** 3840 × 2560, full sensor field, 25.00 fps, including one continuous take of 13 min 41 s.
- **Two instruction words that set the height in `tkhd` and the `stsd` entry were run on the camera.** The unmodified card files import into Premiere Pro as 3840 × 2560.
- **Entering Movie from a still mode after the apply is unreliable on this camera**: two of four attempts ended in a flickering picture and a restart.
- **Applying with the camera left in Movie avoids that** (one attempt so far): no flicker, no restart, and a good 3840 × 2560 clip, here in S-Log3.

## What went wrong with the 0x8c0 design at 25p

Applied: the 19 sensor cells and stored record of mode 12 (with the 50-system timing row changed to 25 fps), the output size word, the encoder tables, 20 screen words and the two header instructions. Recorded: `YM_1704.MP4`, 972 frames.

| Measured | Value |
|---|---|
| Decoded raster | 3840 × 2560, AVC High 4:2:2 10-bit, 25/1 |
| Rows with picture | 0–2223; rows 2224–2559 are digital zero (Y 0, Cb/Cr 512) in every frame checked |
| Field against a 4240 × 2832 photo | 98.7 % of the width; the valid part covers 73 % of the height; all 2560 rows would cover 84.2 % (the 16:9 band) |
| Shape | vertical scale about 1.17 × the horizontal one |
| Levels | luma floor near 268 (10-bit) instead of 64–76; strong blue/purple cast |
| Cadence | 24.99 fps measured optically: the stock 25p timing, not the patched row |

So the shared picture records were in their full-height form while the sensor and the stored record in use were stock.

**Why.** In `cpapp-b.bin` 7.02 there are two sibling selector functions:

- `0x407b2c` returns the 24p family: `0x8c0`, or `0x28c0` when its fourth argument is 2 (plus the `…c1`, `…c4`, `…c5`, `0x5c1`, `0xbc0` variants);
- `0x407c48` returns the 30p family: `0x820`, or `0x2820` when its fourth argument is 2 (it tries `0x880` / `0x2880` first, which this sensor's id table does not hold).

The caller picks the function from the frame-rate setting (state +0x630: 3 or 4 → 24p family, 2 → 30p family) and passes state +0x63c, +0x668 and +0x6a4 as arguments. The drive-parameter calculator run for the 50 system gives mode 10 (0x820) 268 × 5364 = 25.000 fps and mode 12 (0x8c0) 268 × 5580 = 24.000 fps. Mode 12 is the 24p mode in both systems.

The meaning of the fourth argument (0x820 against 0x2820) was not traced. That the camera chose 0x820 here is inferred from the pictures (with 0x2820 the picture records would have been stock too) and from the result below; the active mode id was not read from the camera.

## The design on mode 10

Every cell of `ogsq_fx3_v1` has a counterpart in row 10 of the same table. For all cells except the timing and frame-length fields, row 10's stock bytes equal row 12's, and the new bytes are the same.

| Table + column | Mode 12 (ogsq_fx3_v1) | Mode 10 | Stock | New |
|---|---|---|---|---|
| colmap +0 | `0xc53598` | `0xc53588` | `0b000000` | `01000000` |
| rx +0 | `0xc54040` | `0xc54028` | `0500` | `0000` |
| rx +4 | `0xc54044` | `0xc5402c` | `0300` | `0200` |
| rx2 +0 | `0xc549d0` | `0xc549b0` | `0500` | `0000` |
| rx2 +4 | `0xc549d4` | `0xc549b4` | `0300` | `0200` |
| d +4 | `0xc54ce4` | `0xc54cac` | `de01` | `e401` |
| tim_b +0 | `0xc54670` | `0xc54640` | 268, 5364, P 149, E 68 | **313, 4600, P 23, E 1** |
| win +18 | `0xd47186` | `0xd4713a` | `26000600` | `7a001600` |
| win +26 | `0xd4718e` | `0xd47142` | `5809` | `100b` |
| st1 +22 | `0xd4777a` | `0xd4772e` | `0100` | `0000` |
| st1 +26 | `0xd4777e` | `0xd47732` | `1900` | `1d00` |
| st1 +30 | `0xd47782` | `0xd47736` | `0200` | `0300` |
| lc +8 | `0xd47c3c` | `0xd47c20` | `dc00` | `0000` |
| lc +12 | `0xd47c40` | `0xd47c24` | `eb00` | `2500` |
| crop +6 | `0xc53926` | `0xc538fe` | `dc00` | `0000` |
| crop +18 | `0xc53932` | `0xc5390a` | `0200` | `0000` |
| geometry row of 0x820, +10 | `0xbfb192` | `0xbfb17a` | `dc00` | `0000` |
| rl +10 | `0xd47e9e` | `0xd47e7a` | 1104, 1318, 618, 618 | 1104, **1127**, 728, 728 |

- **Timing.** (313 + 1/23) × 4600 = 1,440,000 units = 25 fps at 36 MHz. It meets the rules derived in the A7S III notes: E < P, P odd and a divisor of VMAX, VMAX a multiple of 4, E/P the reduced fraction of the line length. 0xe011 itself runs 312 × 3140.
- **Read-out table.** The 50-system frame-length field follows VMAX / 4 − 23, so 1318 → 1127. The 59.94-system field (1104) and mode 10's 59.94-system timing row (`0xc54280`) are left stock: this is a PAL-only design.
- **Geometry table.** Its rows are 12 bytes and start with the mode id; 0x820's row is at `0xbfb170`.
- **Picture records.** Unchanged: the pair `0xbb31d8` / `0xbb3d90` is shared by 0x8c0 and 0x820.
- **Stored record.** Index 10, `0x1fde30c`. The calculator run for the 50 system with the cells applied, plus the 16/19 ratio, changes 62 bytes, at the same offsets as mode 12's record. Against mode 12's design in the same system 32 bytes differ, all of them timing-dependent.
- **Self-check.** The same emulation, fed this repository's 19 cells, reproduces `ogsq_fx3_v1`'s published stock and design records for mode 12 byte for byte, and changes only record 12.

On the camera, all 18 cells and all 62 record bytes held the expected stock values before the first write (cold start, a still mode).

## Results with the mode-10 design

Two recordings, both XAVC S 4K 25p 140M 4:2:2 10-bit, lens E 28-75mm F2.8.

| | `YM_1705.MP4` | `YM_1706.MP4` |
|---|---|---|
| Frames / duration | 696 / 27.84 s | 20,520 / 820.8 s (13 min 41 s) |
| Decoded raster | 3840 × 2560, AVC High 4:2:2 10-bit | the same |
| Timeline | 25/1, regular | 20,520 packets, every step 1/25 s, key frame every 12 |
| Full video and audio decode | passes | passes (`ffmpeg -xerror -err_detect explode`) |
| Rows with picture | all 2560; luma floor near 91 | all 2560 in 15 samples across the take |
| Field against a 4240 × 2832 photo | 99.0–99.2 % of the width and of the height; vertical/horizontal scale 0.998 | not measured (handheld, outdoors) |
| Optical cadence | clock in frame: 27.80 s over 695 frame intervals, 25.00 ± 0.03 fps; no repeated or skipped frame in 696 | not measured |
| Audio sync | not measured | hand claps at 0.97 s and 813.98 s: sound within one frame of the picture at both ends |
| Conditions | indoors | outdoors, about 0 °C, walking |

The cadence figure is the first measurement of the 313 × 4600 row: the field of view shows the sensor was in the full-height mode. The time base is a browser clock on a 60 Hz monitor, not a calibrated instrument. The owner reports autofocus, menus and ISO working normally and custom white balance slightly slower.

SHA-256: `YM_1704.MP4` `7b0af6fa…2eea`, `YM_1705.MP4` `79de054c…12cb`, `YM_1706.MP4` `743e0ba3…bf16`.

Not qualified: heat (the long take was at 0 °C), takes longer than 14 minutes, several takes in a row, rolling shutter, the rear screen during recording, 0x2820, the 59.94 system at 29.97p, XAVC HS and S-I at 25p.

## MP4 headers: a second way, run on the camera

The implementation used here does not change the track config's height. It changes two readers of it in libmpr.so:

| Site | Stock | New | Effect |
|---|---|---|---|
| `0x2234e8` (tkhd function `0x223460`) | `mov w3, w23` | `mov w3, #0xa000000` | track header height 2560; `w23` still feeds the matrix builder |
| `0x22149c` (stsd entry `0x221464`) | `ldrh w1, [x2, #0x28]` | `mov w1, #0xa00` | sample entry height 2560 |

Result in the original card files (`YM_1704`, `YM_1705`): `tkhd` 3840 × 2560, `avc1` 3840 × 2560, `avcC` `01 7a 00 33`, VPRF 3840 × 2160, XML 3840 × 2160 16:9. Premiere Pro 2026 imports the unmodified `YM_1704.MP4` as 3840 × 2560, 25.00 fps, pixel aspect 1.0 and shows the picture. So instruction words written through the recorder's `/proc/self/mem` do take effect on this FX3.

Compared in emulation with `ogfile2560_hs_s_fx3_v2` (not run here), combs 0, 2, 5, 7, 23.98p and 25p, all 52 bit-rate indices:

| | v2 (two track-config heights) | the two readers above |
|---|---|---|
| Track config height | 2560 | 2160 |
| tkhd, stsd entry | 2560 | 2560 |
| PROF/VPRF size | 2560 | 2160 |
| Other formats while applied | untouched (only 3840 × 2160 configs change) | every format's stsd entry gets height 2560, proxy included |
| Codec configuration record | **level byte changes** | unchanged |

**A point for v2.** The level function `0x21fad0` picks the level from the track config's height: for AVC it knows 1080 and 2160 and returns `0x28` for anything else; for HEVC it knows 2160 and 4320. Its two callers are the AVC configuration builder `0x221570` (level at byte 3) and the HEVC one `0x2216a0` (level at byte 16). With v2's heights the builder's record goes from `01 7a 00 33` to `01 7a 00 28` (AVC 5.1 → 4.0) and from level 150 to 123 (HEVC 5.0 → 4.1), while PROF keeps its profile id. In stock card files those record bytes equal the `avcC` / `hvcC` box header, so a v2 file probably carries a box header that says level 4.0 next to an SPS that says 5.1. The serialisation of the record into the file was not followed, and no v2 file was made here. PORT_NOTES' "The level labels are unchanged too" may need a second look.

## Entering Movie after the apply

All applies were made in a still mode after a cold start. After the last USB session the cable was unplugged and Movie selected.

| Attempt | Playback screen opened by itself after unplugging | Selecting Movie |
|---|---|---|
| 1 | not recorded | worked (after a read-only session with Movie selected, the camera was found in a still mode; Movie was selected again and `YM_1705` recorded) |
| 2 | yes | flickering purple/black picture for about 1 s, then a restart |
| 3 | yes | the same |
| 4 | no | worked; worked again after a read-only session; `YM_1706` recorded |

The card held open-gate clips in all four. Same lens in all four. After each restart a cold-start check found every managed site at its stock value. The cause is not established; the coprocessor log was not read.

**Applying in Movie (added later the same day).** Following issue 2's note, the same 210 sites were applied once with the camera started cold, set to Movie (exposure mode M) and never taken out of it: three write sessions, all with preimage checks and readback passing. So the stored record of mode 10 and its cells were changed while that mode was the active one.

- The playback screen again opened by itself after every USB session. After the last one it was left with one key press and the camera was in Movie with a normal picture: no flicker, no restart.
- `YM_1707.MP4`: 456 frames, 18.24 s, 3840 × 2560, AVC High 4:2:2 10-bit, 25/1, full decode passes, `tkhd` / `avc1` 2560, no empty rows, no colour cast. Recorded in S-Log3 (XML `s-log3-cine`); the earlier clips were Rec.709. Field of view not measured for this clip.
- One attempt only. SHA-256 `6e897beb…8dbd`.

## Suggested maintainer follow-up

- Say in the README that at 25p (PAL) the 0x8c0 sensor step gives a stretched 16:9 picture, until a 0x820 step exists.
- Consider a mode-10 variant of the sensor step from the table above; the timing row and the read-out frame-length field are the only cells that are not copies.
- Check the level byte of `avcC` / `hvcC` in the first v2 card file.
- Keep the "do not play back" warning. On this camera the two restarts came after the playback screen had opened before the first entry into Movie; with the apply made in Movie the same playback screen did no harm.
- Consider making "apply in Movie" the documented way, as issue 2 suggests: it worked here at 25p too.

The footage, reference photos, firmware binaries and device-identifying logs are not part of this contribution.
