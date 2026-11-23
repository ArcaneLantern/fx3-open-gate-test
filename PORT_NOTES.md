# Port notes: A7S III 5.01 kit → FX3 7.02

Everything here was read from the FX3 7.02 firmware update (`BODYDATA.DAT`, SHA-256 `f040affe…c854`). Every step of the kit was emulated: Unicorn and qemu-arm ran the FX3's own code where it mattered, and the built helper libraries ran against a model camera. **Nothing of this kit has run on an FX3.** The reference is the A7S III kit, which works on an A7S III (seventh and ninth tests, 2026-11-22): open gate with right colours and the full sensor, and the rear screen at 3:2.

## The FX3's image processor is the A7S III's, relinked

The coprocessor program (`cpapp-b.bin`, loaded at 0x108000) of the FX3 7.02 is the A7S III 5.01 one, rebuilt at other addresses:

- **Sensor and modes.** The same sensor (IMX510) and the same 40 drive modes in the same order: 0x8c0 (4K 23.98p) is mode 12, and 0xe011, the full-height mode the patch borrows, is mode 37.
- **Tables.** Every sensor table the design touches is byte-identical to the A7S III's (13 tables, all 40 rows each), at fixed shifts:

| What | A7S III 5.01 | FX3 7.02 | shift |
|---|---|---|---|
| mode ids / column map / receiver types / timing | 0xc70624 / 0xc703cc / 0xc70e44 / 0xc71024 | 0xc53790 / 0xc53538 / 0xc53fb0 / 0xc54190 | −0x1ce94 |
| windows / aux stream / LC / read-out table | 0xd67c00 / 0xd681f0 / 0xd687e0 / 0xd68a10 | 0xd46fac / 0xd4759c / 0xd47b8c / 0xd47dbc | −0x20c54 |
| register matrix (489 rows) | 0xf2eb78 | 0xf09f84 | −0x24bf4 |
| geometry row of 0x8c0 | 0xc1801c | 0xbfb188 | −0x1ce94 |
| 0x8c0 / 0x820 picture-record pair | 0xbcfff8 / 0xbd0bb0 | 0xbb31d8 / 0xbb3d90 | −0x1ce20 |
| stored drive-parameter records (0x15c each) | 0x1fe0504 | 0x1fdd574 | |
| sensor object; drive-parameter pointer | 0x12a41f0; control +0x698 | 0x127ab68; control +0x698 | |
| movie size table; the 3840 × 2160 word | 0x13ec2ac; 0x13ec2e4 | 0x13c3190; 0x13c31c8 | |

- **Code.** The functions are the same code: the drive-parameter calculator (0x331538), the record selector (0x2514b8), the scaler packers (CamArc 0x24d6b8, CamNrs 0x6c70da, CamSig 0x6cd22e, CamLrc 0x6c7096, Dev 0x6c6618 / 0x6c64ba, fit 0x6cce8c) and the size-table set-up (0x4008ec). Only relocated branch targets and constants differ.
- **Main processor.** av-cam.bin's encoder tables are the A7S III's, byte for byte, 0x77a0 further on (the clip table 0x7780). libmpr.so's `g_videoParamComb` is 0x9300 lower. av-cam is reserved at physical 0x401000000, as on the A7S III.
- **Memory.** The movie raw write buffer (memory id 0x43e) is 27,864,320 bytes, more than the A7S III's working 26,214,400. The ZV-E1's problem (a buffer too small for the full-height stage) does not arise, and there is no buffer step.
- **USB route.** libsencore.so holds the same login keys. `DeviceInfo.xml` is the same file on every body, so it cannot tell them apart. The helper checks which camera it is on: the hashes of three libraries and of four code and data pages.

The A7 IV kit and the A7S III kit's newer ports were not used as references. The ZV-E1 kit served only as a layout model for the scripts and the app.

## Sensor side: `ogsq_fx3_v1` (the A7S III's `ogsq_s3_v5`)

`build/build_og_fx3.py` does not copy the A7S III's bytes. It builds the design again on the FX3's own files and checks it against v5:

- **Sensor cells.** v5's cell builder (`build_og_s3_v3.cells`) runs on the FX3 image with the FX3's table addresses and v5's timing rows: 313 × 4788 P57 E34, and 313 × 4780 P239 E193. Both pass the E < P rule that v3's failure taught. The result is v5's 19 cells, each at the matching FX3 address with the same old and new bytes.
- **Picture records.** Emulated on the FX3, the record selector gives 0x8c0 and 0x820 the pair 0xbb31d8 / 0xbb3d90, and gives every mode the A7S III's record moved by −0x1ce20.
  - The FX3's stock pair differs from the A7S III's only in three relocated pointers (+0x948, +0x94c, +0x950), and none of them lies in v5's changed bytes. The new records are the FX3's stock records with v5's changed bytes, so the relocated pointers stay the FX3's.
  - The cross-check: the record model, run with the FX3's own packers, builds the same two records byte for byte. The same model reproduces v5 on the A7S III.
- **Link format.** The 12-bit link-format rule holds on all 46 FX3 stock records, and both new records pass it.
- **Stored record.** The FX3's own calculator gives all 40 stock records equal to the A7S III's. With the cells applied, mode 12's record (plus the 16/19 sampling ratio, with the run-time bytes left alone) equals v5's exactly: 62 bytes.

## Output size and encoder: `outsz2560_fx3_v1`, `ogfile2560_hs_s_fx3_v1`

- **Output size.** The size-table set-up was run on the FX3 image. Its 16 entries equal the A7S III's. One word changes: 0x13c31c8, from 3840 × 2160 to 3840 × 2560. It has two guards, as on the A7S III.
- **Encoder.** The same 29 descriptors are chosen: 101 av-cam sites and 4 libmpr sites. Each has the A7S III design's old and new bytes, at the shifts above. Adding the FX3 to the builder changed none of the other bodies' 36 design files.

## Rear screen and De-Squeeze Display: `lcd32dsq_fx3_v1` (30 words)

**What the firmware does.**

- **Panel shape.** It is a panel-type byte (rear output: RAM 0x14909e4) that the camera copies from its settings memory at start-up: type 2 = 4:3, 3 = 3:2, 1 = 16:9 (function 0x1e0050, tables 0x1e00f4 / 0xb7f034, as on the A7S III).
  - Sony gives the monitor as 1,440,000 dots. The display timing table (0xd7231c) has one geometry with that count, **800 × 600 (4:3)**; its 3:2 geometries are 720 × 480 and 1024 × 682. So a 4:3 panel is expected, like the A7S III's. Not read on a camera.
- **16:9 pictures.** The layout function (0x1df884) letterboxes a 16:9 picture on both panel shapes: fit words 0x1df4a8 / 0x1df4ac are both 3. The height is width × n / d, taken from the picture-ratio function 0x1df794.
  - **This function has the A7 IV's instruction form, not the A7S III's**, so the A7S III's `lcdratio32_s3_v1` words cannot be reused. Its 16:9 case is at 0x1df7b8: `mov.w lr, #9` / `movs r0, #16`.
- **De-squeeze active.** While De-Squeeze Display is on (0x60eb6e: the code set by `SendVDF_DeSqueeze` → VdfInput command 0x327 → `DevCmdSetDeSqueeze`), the layout uses the de-squeeze calculator 0x1df680 instead:
  - full width, centred, height = (width × n + 2d) / d & ~3, with **fixed ratios per factor for a 16:9 picture**: 1.3x 45/104, 1.5x 3/8, 1.65x 15/44, 2.0x 3/8;
  - 2.0x also crops the input to its centre 4:3 (0x5faf04).
  - A 3:2 picture would come out 32/27 too wide at every factor.
  - The A7S III has the same de-squeeze code (with a 1.8x factor instead of 1.65x).

**What the design changes.**

| Part | Words | Stock → new |
|---|---|---|
| 16:9 letterbox ratio (0x1df7b8 / 0x1df7bc) | 2 | 9/16 → 2/3: the function's own 3:2 case. 800 × 600 gets (0, 33, 800, 534); on 720 × 480 the height would exceed the panel, so it gets the whole panel |
| frame tables 0xd2e510 / 0xd2e588 / 0xd2e600, 16:9 column | 18 | row 0 (rear, 4:3 panel) and row 2 (second output): (0, 60, 640, 360) → (0, 26, 640, 428); row 1 (rear, 3:2 panel): (0, 38, 640, 404) → (0, 0, 640, 480) |
| de-squeeze ratios (0x1df700–0x1df714, 0x1df6a8 / 0x1df6ac) | 8 | 1.3x 20/39, 1.5x 4/9, 1.65x 40/99, 2.0x 1/3 |
| 2.0x crop (0x5faf34, 0x5faf68) | 2 | `cmp r0, #4` → `#5`. The code is always below 5 (checked at 0x5f5442), so the crop never runs and 2.0x shows the whole frame at 3:1 (the owner's choice) |

Left stock: the fit words, the 17:9 ratios, and the HDMI manual-layout copy (0x1dfb18). 2.0x's ratio is the calculator's default for every picture shape, so while the step is applied 2.0x shows any picture at 3:1. Every word was decoded with capstone, and there are 32 guards, none overlapping a site.

**Emulated** (`build/emu_lcd_fx3.py`, 22 cases; `evidence/fx3/lcd32dsq_fx3_v1_emu.json`). The FX3's own functions ran, stock and patched, on 800 × 600 and 720 × 480:

- **Fit mode** of a 16:9 picture: 3 on both panels.
- **Live view with de-squeeze off:** 3:2 on both panels (1.498 and 1.500). Every other picture shape is unchanged.
- **De-squeeze:** 1.94 / 2.25 / 2.47 / 2.99:1 on 800 × 600 and 1.96 / 2.25 / 2.47 / 3.00:1 on 720 × 480, against 1.95 / 2.25 / 2.475 / 3.0. The stock ratios with the 3:2 picture are off by 1.18.
- **2.0x crop:** stock crops 1920 → 1440 at x 240 on both paths; patched leaves the whole frame.
- **Frame check** (0x128438, focus frames): it accepts the patched live view with the patched tables on both panels and on the second output. It rejects it with the stock tables, so the table change is needed. While de-squeeze is on no frame check passes, stock or patched; the camera sets manual focus then.

**qemu-arm cross-check** (`build/lcd_fx3_qemu.py`, in WSL). The two calculators and the fit function ran natively under qemu-arm 10.2.1: 104 cases. All 10 rectangles of the Unicorn run matched exactly, and the shapes the design leaves alone came out unchanged.

## The kit

- **Helpers.** `helper_fx3/fx3read.c` is `s3read.c` with text changes only. The write libraries are the A7 IV helper's levels 5/6, 16/17 and 19/20, which ran on the A7S III, with the FX3's tables. Level 5 follows the sensor object 0x127ab68 → control +0x698 → the drive-parameter object.
- **Read-only emulation** (`emu_fx3.py`), for check and dump:
  - a stock FX3 reads READY;
  - applied, every site reads TARGET;
  - applied without the screen step, its 30 words read STOCK;
  - an A7S III image and a ZV-E1 image are refused (DIFFERS, NOT READY);
  - without the av-cam reservation, av-cam.bin is not read;
  - with an existing result, nothing is done.
  - **And the other way round:** the published A7S III and ZV-E1 check libraries both say NOT READY on an FX3, so neither kit's apply starts on one.
- **Write emulation** (`emu_fx3_write.py`, 37 cases):
  - apply, apply again, put back byte for byte;
  - foreign bytes, a lost write undone, a null records pointer, a wrong guard (each of the 32 screen guards);
  - the stored record as the A7S III tester's camera held it, with its run-time bytes left alone (the FX3's stock record is identical).
  - **Safety:** the A7S III kit's own L5, S16 and L19 libraries write nothing on an FX3, even with L5's pointer chain made to reach the FX3's real object.
- **Scripts.** `fx3_run.py` and `fx3_apply.py` are `s3_run.py` / `s3_apply.py` with this camera's libraries, pins, dump decoder and texts. The FX3 has no mode dial: the texts use its MODE button. Every library's `--selftest` and every launcher's `--dry-run` pass, also from the published tree. The dump decoder reads the panel type, the ratio, the frame rows, the de-squeeze ratios, the crop and the 30 words.

Library pins: check `fcf97a8e`, dump `ad2bae79`, L5 `9fd94c17`, L6 `6c8544fb`, L16 `cf644fb3`, L17 `5a3c16bf`, L19 `47400649`, L20 `6ca3ee7d`, S16 `bc40334b`, S17 `50a96268` (full hashes in `fx3_run.py`). A result belongs to this kit only if its header says `fx3read_v1` and each step's manifest names these libraries.

## Not known until an FX3 runs it

- Everything on a camera. Above all: that the full-height mode and the 2,848-row first stage run as on the A7S III, and the rear panel type (expected 2).
- What the A7S III left open: the glitchy live view on entering movie mode from stills, exposure and autofocus, 60p (crashed the A7S III), PAL, XAVC S 4K.
- Whether the power switch removes the patch on the FX3 (it does on the A7S III).
- That the menu's 1.3x / 1.5x / 1.6x / 2.0x send the codes 1 / 2 / 3 / 4. This is inferred from the ratios; appFw's mapping was not read.
- What the FX3's HDMI output shows in the open-gate state, with or without de-squeeze. HDMI is not part of this kit.
- The scaler-state addresses the dump reads were ported by code reference. The second scaler's block and input words are only predicted, as they were on the A7S III.
