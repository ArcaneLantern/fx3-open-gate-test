# Port notes: A7S III 5.01 kit → FX3 7.02

Everything here was read from the FX3 7.02 firmware update (`BODYDATA.DAT`, SHA-256 `f040affe…c854`). Every step of the kit was emulated: Unicorn and qemu-arm ran the FX3's own code where it mattered, and the built helper libraries ran against a model camera. The reference is the A7S III kit, which works on an A7S III (seventh and ninth tests, 2026-11-22): open gate with right colours and the full sensor, and the rear screen at 3:2.

## First camera results (2026-11-24)

**Tester 1 ran this kit (macOS, the four-step apply, twice).** Every session used this kit's pinned libraries and read firmware 7.02.

- **Checks.** Four checks said VERDICT READY, with all 7 identity checks the same.
- **Apply 1 (22:30 UTC).** L5, L16, L19 and S16 said DONE. The closing dump (22:33) shows:
  - every open-gate and screen site TARGET;
  - the sensor in its full-height mode (register shadow = matrix column 1, as on the A7S III);
  - the second scaler taking the whole 4240 × 2392 picture to 3840 × 2560, vertical scale 2392/2832;
  - the 30 screen words applied;
  - **the rear panel's type byte: 2 = a 4:3 panel.**
- **Between the two applies.** The camera was started afresh: the coprocessor's kprint log was initialised again, so no crash report survived, and the boot log's power-key fields differ. The second apply's L5 said DONE, not NOTHING TO DO, so the patch was gone.
- **Apply 2 (22:40).** Every step said DONE. The closing dump was taken in a still mode (sensor in a stills mode), which a dump in that state shows as expected.
- **Tester 1's words.** It records and displays open gate. The first run was unreliable. On the second run the only problems were the metadata and that clips do not play back on the camera.

**Tester 2 used a separate implementation of the same three open-gate steps, with no screen step** (`FX3-UPSTREAM-TEST-REPORT-2026-11-24.md`):

- **Recordings.** XAVC HS 4K (HEVC 4:2:2 10-bit) and XAVC S 4K (AVC 4:2:2 10-bit), 23.976p, 3840 × 2560 decoded. Full decode and cadence checks pass.
- **Field of view.** It covers 99.7–99.99% of a 4240 × 2832 reference photo in width and height; a 16:9 crop would cover 84.2% of the height.
- **Metadata.** `tkhd`, the `avc1`/`hvc1` sample entry, Sony's VPRF and the XML say 3840 × 2160. The level label is AVC 5.1, while the picture has 38,400 macroblocks, above level 5.1/5.2's MaxFS of 36,864.
- **Playback.** In-camera playback showed "unable to display", and a retry froze the camera (battery pull).
- **LCD.** It is black for under 0.5 s at the start of an XAVC S recording; the file holds every frame.

## Why in-camera playback fails (traced 2026-11-25, static)

**Cause: the FX3 opens every movie playback decode at 4096 × 2160.**
- **On the FX3.** av-cam.bin's decode channel set-up (ImolaCreateCh, decode side; FX3 `0xffffffc001218cc4`) always takes row 0 of its channel table: `mov x23, xzr` at file 0x218e14.
  - Row 0 is 4096 × 2160, 8 reference pictures (table at file 0xbf8e70; it has only three rows).
  - The memory is fixed to the 4K decode ids 0x47d / 0x47f (`mov w2, #0x47d` at 0x218ab4, `#0x47f` at 0x218b30).
- **On the A7 IV 6.02.** The same function takes row 3 for ordinary playback: 7690 × 4320, with the 8K ids 0x47c / 0x47e. A 3840 × 2560 stream fits that channel, which is why the A7 IV plays its open-gate clips.
- **Fit.** A 3840 × 2560 stream is over the FX3's channel in rows (2560 > 2160) and in pixels (9.83 M > 8.85 M).
- **Everything else is the same.** The codec firmware is the same file on all bodies, and the FX3's main-processor memory configuration holds the A7 IV's 8K decode ids at the same sizes. The FX3 never asks for them.
- **Other bodies.** The A7S III 5.01, A9 III, A1, ZV-E1 and FX2 have the A7 IV's form. The FX30 and A7C II have the FX3's.
- **Ruled out:**
  - appFw: its one content check (`is_movie_playable_content`, FX3 0x2a50774) sees an ordinary 4K clip: libmpr's size classifier puts every 3840-wide size that is not 8K in the 4K class, so the header size does not matter.
  - libmpr: its playback path is the A7 IV's, and passes no picture size to the codec.
  - The kit's changes: none of them is on the decode path.
- **What the camera does.**
  - "Unable to display." is the dialog for "player start failed" (dlg_ply034: event 0x300a5 from `start_playback_movie` 0x2d30924 after `mpr::PbStart` fails).
  - The freeze on a second try fits an untimed wait: appFw's PbStart wrapper 0x2e75064 waits on a `std::future` with no timeout. libmpr sets its play state even when the start completes with an error, and the codec firmware's decodable check ends in its assert/exit path. That chain is inferred.
- **Side effect, the same on both bodies.** The kit's 2560-row format table also reaches MEDIAPRO.XML's clip info, whose videoType then reads 3840_2560 while the camera's own MEDIAPRO height parser knows no 2560.

## The playback step: `avdec8k_fx3_v1`, steps P29 / P30 (built 2026-11-25, NOT RUN ON ANY CAMERA)

**The design** (`build/build_avdec_fx3.py`; FX3 av-cam.bin, file offset = kernel address − 0xffffffc001000000):

| Where | Stock | Changed | What |
|---|---|---|---|
| code 0x218ab4 | `mov w2, #0x47d` | `mov w2, #0x47c` | first decode-memory id: 4K (2 units of 152.3 MB) → 8K (the whole 536.2 MB of region 0x6c4) |
| code 0x218ac0 | `mov w20, #0x47d` | `mov w20, #0x47c` | its copy, used only in the failure log line |
| code 0x218b30 | `mov w2, #0x47f` | `mov w2, #0x47e` | second id: 2 units of 38.6 MB → 135.0 MB in region 0x6dd |
| code 0x218b3c | `mov w21, #0x47f` | `mov w21, #0x47e` | its copy for the log line |
| data 0xbf8e70 | 4096 × 2160 | 7690 × 4320 | decode table row 0: width, height. The rest of the row is already the A7 IV's row 3 |

**Why this is the A7 IV's behaviour, not a guess.** The builder checks each of these against both firmwares:
- The A7 IV's allocation (0x20e3d8) asks for 0x47c / 0x47e unless the clip type (+0x54) is 14, and its row choice (0x20e788) takes row 3 unless the type is 14. The FX3's caller (0x22a198) makes types 11, 12, 13 and 10 only. The A7 IV's extra branch, type 14 for its formats 0x26 / 0x27, is not in the FX3. So for every clip the FX3 makes, the A7 IV would choose the 8K channel and memory.
- The FX3's three rows are the A7 IV's rows 0–2, byte for byte. The A7 IV's row 3 is the FX3's row 0 with 7690 × 4320. The A7S III 5.01 holds the A7 IV's four rows.
- Only create-ch (0x218e54) reads the table. The allocator called (FX3 0x22d394 = A7 IV 0x222bd0) and its arguments are the same.
- Every other `mov wN, #0x47c..0x47f` in the FX3's av-cam is the line number of a log or assert call, or the same as in the A7 IV.
- The main-processor DmmCfg holds 0x47c..0x47f at the A7 IV's sizes.
- The other allocation path (types 12/13, rows 1/2, ids 0x4f5 / 0x4f6) is the same on both and is not changed.

**The helper: readcheck.c levels 29 / 30** (new; the other levels are unchanged: every pinned library of the A7 IV, A7S III, ZV-E1, A7C II and FX3 kits rebuilds to its hash). The code words are kernel text, the first code this kit writes outside a process of its own, so the level is stricter than level 19:
- The processors are 4 × Cortex-A35 (the update's device tree). Kernel 4.9 lets a process clean and invalidate caches by address. The level reads CTR_EL0 and refuses unless the instruction cache is PIPT or VIPT.
- It maps the code page through /dev/mem at a user address with the kernel address's offset from a 2 MB boundary (0x18000). On a virtually indexed instruction cache the invalidation then uses the index the kernel's fetches use. It does this with a PROT_NONE reservation and a MAP_FIXED mapping inside it.
- Before anything is written:
  - every byte of the code page apart from the four sites must be as in the file, in the mapping and in the kernel's own view (pread of /dev/mem);
  - the data row's other 56 bytes must be as in the file;
  - each site must hold its stock or its new word.
- **The probe.** It runs the whole maintenance sequence once on the unchanged sites, before any write. If this processor refused it from a process, the process would end there with nothing written.
- **Writes and sync.** Each site is one aligned 32-bit store, read back in both views. After the code stores: `dc cvau` at each site, `dsb ish`, `ic ivau` at each site (both broadcast to every processor), `dsb ish`, `isb`.
- **Order.** Apply writes the code first and the row last; put back writes the row first and the code last. A 4K row with 8K memory is a smaller channel in larger memory and harmless. The other mixed state (8K row with 4K memory) never arises, and if found it is repaired first.
- **Undo.** On any failure everything the run wrote is put back, in the put-back order, and the caches are synced again.

**Emulation** (`helper_fx3/emu_fx3_playback.py`, 35 cases; run by `emu_fx3_write.py` too). The libraries ran in Unicorn with a model of /dev/mem, the reservation, the fixed mapping and the kernel's view. Every store and every cache instruction is logged in order. Cases:
- apply on stock, apply again, put back, put back on stock;
- six reservation addresses: the code page always keeps the 2 MB offset;
- CTR_EL0: PIPT and VIPT are applied; AIVIVT and VPIPT are refused before /dev/mem is opened;
- the four half states;
- refusals: six code-page bytes, a code site and the row holding foreign bytes, each data guard, the kernel's view unreadable, each of the three mappings refused, and the A7S III's and A7 IV's av-cam.bin in memory;
- a write the kernel's view does not follow (row, third code word, put back): everything put back;
- the libraries hold no system instruction but `dc cvau`, `ic ivau`, `dsb ish`, `isb` and one `mrs` of CTR_EL0.

**Risks left for the camera:**
- that playback then works on the FX3 (it does on the A7 IV);
- that 0x47e's unit can be had during playback: the FX3's region 0x6dd has a third group, 0x6f {0x473, 0x476}, which the A7 IV lacks. If not, playback start fails as now;
- that nothing in the kernel checks av-cam's code at run time (none is known);
- the cache model on the real Cortex-A35.

The step is optional and separate (`playback_fix_apply.cmd` / `playback_fix_putback.cmd`; `fx3_apply.py playback` / `playback-putback`). The open-gate apply and put back do not run it.

**Alternatives not built:**
- data only: row 0's height → 2560 with the 4K memory, which is probably 3–10% too small;
- no change: keep playback off.

## Open gate at 25p and 29.97p: `ogsq_fx3_v2`, `ogfile2560_hs_s_fx3_v3`, `ogfilesi2560_fx3_v2` (built 2026-11-26; 29.97p NOT RUN)

The owner asked for 25p, 30p, 50p, 60p and 100p, and 100p in place of NTSC's 120p. **Only 25p and 29.97p are possible at full resolution**, and the owner chose those:
- The only full-height read-out of the sensor is sensor mode 0x01 (matrix column 1), one row per line of at least 312 units of 1/36 MHz (8.7 µs). The camera's own full-height mode 0xe011 runs it at HMAX 312, VMAX 3140: 36.7 fps at most. 2832 rows plus margins need 2998 lines, about 26 ms.
- The fast 4K modes (FF 4K 0x21, the 3840 × 2160 crop 0x23) read two rows per line but only the 16:9 band. The window belongs to the mode number inside the sensor (the A7S III's fourth write test). Even at the 4K band's row rate, 2832 rows would take about 10.4 ms, more than a 100p frame.
- What does exist: binned full-field read-outs (2 × 2 at 2120 × 1416 up to about 89 fps; 3 × 3 at 1412 × 938 up to 120p). They would be 1.8× to 2.7× upscales on a new pipeline; not built (owner's choice).

**Drive modes.** 23.98p (NTSC) and 24p (PAL) run 0x8c0 (index 12); 29.97p (NTSC) and 25p (PAL) run 0x820 (index 10), the selector's 30p family (frame-rate code 2). A tester found the latter on his FX3 in PAL: with v1 at 25p the picture was the 16:9 band stretched, and with v1's cells moved to row 10 it recorded open gate at 25.00 fps (`FX3-PAL25-MODE-0x820-REPORT-2026-11-25.md`). The two modes share the picture-record pair v1 writes.

**Sensor side, `ogsq_fx3_v2`** (`build/build_og_fx3_v2.py`): v1's 19 cells and two records unchanged, plus 19 cells on row 10 by the same recipe:
- timing rows: 59.94 system 266 × 4508 → 313 × 3828, P 29, E 23 = 29.970 fps; 50 system 268 × 5364 → 313 × 4600, P 23, E 1 = 25.000 fps (the tester's row, which ran). Both follow the rule of every stock row, with VMAX ≥ 2998.
- read-out frame-length fields VMAX / 4 − 23: 934 and 1127.
- Every row-10 cell except the 59.94-system ones equals the tester's design byte for byte (the builder asserts it).

**Stored records, NTSC and PAL.** The camera computes each mode's stored record at start-up from the 60 Hz or the 50 Hz timing table. v1 carried only 0x8c0's NTSC record, so its L5 refused a camera set to PAL ("holds neither the stock nor the new bytes"). v2 carries 0x820's and 0x8c0's records in both systems: 62 bytes each, at the same offsets as v1's. The new L5 uses whichever system the camera holds (readcheck.c MULTI_REC, as the FX30 kit). The emulated PAL run takes each read-out row's 50 Hz frame-length field: with that, the PAL 0x820 record equals the tester's stock and new bytes, which he found on his camera at all 62 offsets. NTSC 0x8c0 equals v1's record.

**Encoder.** On the FX3 one encoder core already serves stock 4K up to 59.94p: all 84 long-GOP 3840 × 2160 descriptors at rate codes 0–5 have UseCore 0. So 3840 × 2560 at 29.97p (295 Mpx/s) keeps one core, the same edit as 23.98p and 25p.
- `ogfile2560_hs_s_fx3_v3` = v2 + the 29.97p descriptors and profiles (rate code 2): 48 av-cam sites more (`build_ogfile.py --build fx3_702 --meta --rate30`).
- `ogfilesi2560_fx3_v2` = S-I v1 + descriptors #112 / #115 (classes 12 and 15) and their profiles: 8 sites more (`build_ogfile_si.py --build fx3_702 --rate30`).
- The A7 IV and FX3 designs these builders wrote before regenerate byte for byte.

**Emulated on the FX3's own code** (`build/emu_ogfile30_fx3.py` → `evidence/fx3/ogfile30_fx3_emu.json`, 11 checks):
- the matcher finds all 49 changed descriptors at 3840 × 2560, and every other request from 1920 wide up answers as in stock; 3840 × 2560 at 50p, 59.94p and the high frame rates finds nothing (refused, as at 24p today);
- at 29.97p the memory function asks the same blocks as at 23.98p, and the codec's need fits them;
- the start-block builder takes every changed profile;
- the track config gives 3840 × 2560 for combs 0, 2, 5, 7, 9 at every rate code (1,560 requests).

**Steps and pins.** L5 `99116990` / L6 `a2f67b80` (ogsq_fx3_v2; L6 also puts back v1), L19 `64793d5a` / L20 `ba041c6e` (v3; L20 also puts back v2 and v1), I19 `3a553194` / I20 `0754c501` (S-I v2; I20 also puts back v1). O5 `9fd94c17` is the previous L5 byte for byte (`--only-24p`, `open_gate_apply_only_24p.cmd`). The libraries they replace are in `fx3_run.EARLIER_LIBS`, so one left on a camera is still deleted.

**Write emulation** (`emu_fx3_write.py`, 113 cases, 21 new):
- L5 on a PAL camera, again, and L6;
- records of mixed systems: refused;
- 0x820's record not stock: refused;
- lost writes on PAL;
- O5 on NTSC, the new L5 over it, and L6 after either;
- O5 on PAL: refused;
- the new L19 / I19 / L20 / I20 over the previous kit's state.

**Not known:** 29.97p on a camera; XAVC HS and S-I at 25p (the tester recorded XAVC S); whether movie standby runs 0x820. The A7S III notes read the glitchy live view that way, and now 0x820 is full height too.

## XAVC S-I 4K: `ogfilesi2560_fx3_v1`, steps I19 / I20 (built 2026-11-25, NOT RUN ON ANY CAMERA)

The A7 IV kit's S-I test step (`ogfilesi2560_v1`, request 70, itself not run yet) ported to the FX3 and made the last step of the default apply, so one run gives XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 3840 × 2560 (owner, 2026-11-25: one patcher for both, no reset between). `--no-si` / `open_gate_apply_no_si.cmd` leave it out; the put back starts with I20.

**The design** (`build/build_ogfile_si.py --build fx3_702`; the A7 IV designs regenerate byte for byte). Every assert of the A7 IV builder runs on the FX3's own files and passes:
- libmpr `g_videoParamComb` row 9 (0x2cb1e0; the FX3's rows 0–12 are the A7 IV's) is S-I 4K: AVC, 3840 × 2160, 4:2:2 10-bit, intra. `m_vpcSt` (0x2e0b80) row 9 has the intra flag. Site: the height, 2160 → 2560.
- av-cam: the reachable S-I 4K descriptors at 23.98p / 25p are the A7 IV's #114 / #117 (24p, classes 14 / 19) and #113 / #116 (25p), keys 105205–105209, UseCore 2, each with a never-reached 205xxx twin. Sony's S-I profile rule (+0x4c = 1.5 × width, +0x56 = half the height in whole macroblock rows) holds for every FX3 S-I profile. Sites: descriptor height +0x80; profile heights +0x06 / +0x38; rows for the first core +0x56, 1072 → 1280.
- 17 sites, 42 bytes. Level byte (51), bit budget (240M / 250M), the unit-type table, the clip row and the MP4 headers are left alone; L19 already makes the last two right.

**Emulated on the FX3's own code** (`build/emu_ogfilesi_fx3.py` → `evidence/fx3/ogfilesi_fx3_emu.json`, 11 checks). The functions were found by code (`build/avcam_fnport.py`):
- the matcher (0x225eb8) and the memory function (0x21dd54) are the A7 IV's instruction for instruction;
- the start-block builder (0x221b50) is a different compile, so it was run as the FX3's own.

What the 11 checks found:
- **Encoder request.** Comb 9 is 3840 × 2560 with the step; the other combs are as L19 makes them.
- **MP4 headers.** With L19 v2 an S-I file's headers say 3840 × 2560 with the stock profile id; with `--no-meta` (v1) they say 2160.
- **Matcher.** It finds each changed descriptor at 3840 × 2560. Every other AVC / HEVC / S-I request (all 689 descriptors' own) answers as before, and L19's descriptors are still found.
- **Memory.** The memory function asks unit type 4's row (0x486, 0x474, 0x47a, 0x477, then 0x485), exactly what a stock XAVC S 4K 24p recording asks on the FX3. The codec firmware is the same file as the A7 IV's; its own calculation needs CD 44.3 MB of 100.8 MB, LD 0, multi 3.7 of 14.2 MB.
- **Start block.** The FX3's builder takes each changed profile: crop 3840 × 2560, 1280 rows for the first core; stock gives 1072 at 2160.
- **Clip code.** 3840 × 2560 gets 23, the FX3's 4K code (from L19).
- **No overlap.** No site is one of L19's (v1, v2) or the playback step's.

**DmmCfg note.** On the FX3, 0x47a and 0x690/0x691 are alternatives in a 138.7 MB block (key 0x76a; 0x7d6 on the A7 IV), as are 0x486 and 0x664/0x665 in a 100.8 MB block. The 304.7 MB region 0x668 that holds them has one more alternative on the FX3, {0x479}: the stock long-GOP ES block of unit row 3, which L19 replaces with the 4K row.

**Write emulation** (`emu_fx3_write.py`, 12 cases):
- I19 after L19, again, and after N19: each writes only its sites;
- L19 run again over both: no write;
- I20 returns exactly L19's state; L20 leaves the S-I sites;
- a lost write and a stale kernel view: everything I19 wrote is put back;
- each of its 6 av-cam guards and its libmpr guard wrong: nothing written.

**Left for the camera:**
- that XAVC S-I 4K 24p uses sensor mode 0x8c0, as XAVC S/HS 4K 24p do (if not, the picture is 16:9 stretched to 3:2);
- the image processor's output format in S-I (XAVC S 4:2:2 10-bit records at 3840 × 2560);
- which bit-rate class the menu's 240M asks (both are changed);
- the card speed;
- in-camera playback of an S-I clip (with the playback step).

## The MP4 headers: `ogfile2560_hs_s_fx3_v2` (2026-11-25, not run yet)

This is the A7 IV kit's header fix (its `ogfile2560_hs_s_v2`, which works on that camera: Resolve opens the files at 3:2 without a remux), ported to the FX3.

- **Where the size comes from.** The FX3's MP4 writer is the A7 IV's code relinked. The track config is 0x21fec4 (A7 IV 0x222b18; 36 of 40 instructions the same, its jump table rebuilt). The `stsd` entry is 0x221464, the PROF entry 0x223110 and `tkhd` 0x223460, all matched instruction for instruction. `tkhd`, `stsd` and Sony's PROF/VPRF are all written from the track config's size, and its 4K height comes from one immediate per codec:
  - 0x21ff3c, XAVC S 4K (AVC);
  - 0x220074, XAVC HS 4K (HEVC).
- **What the design changes.** v2 = the first kit's encoder step (v1, which ran on the FX3) plus those two instructions, `mov w6, #0x870` → `#0xa00` (2160 → 2560). The eight instructions around them are guards. They are code in libmpr.so, written through the recorder's own `/proc/self/mem`, as on the A7 IV.
- **Sony's XML (NonRealTimeMeta) is unchanged** (3840 × 2160, 16:9): its size keys the codec-name lookup, and its aspect strings have no 3:2 (as on the A7 IV). The level labels are unchanged too.
- **Emulated** (`build/emu_mp4_meta.py --build fx3_702`, `evidence/fx3/mp4_meta_emu_fx3.json`). The FX3's own track config, `stsd` and PROF functions ran for combs 0, 2, 5, 7 at 23.98p and 25p, with all 52 bit-rate indices:
  - the FX3's stock writer accepts exactly the A7 IV's requests and gives the same profile ids;
  - with v2 every accepted request gives track config, `stsd` and PROF 3840 × 2560, with the stock profile id and 1:1 pixel aspect;
  - nothing the stock code refuses is accepted.
- **Steps.**
  - **L19 is now v2.** On a camera that still holds the first kit's encoder step it writes only the two words.
  - **L20 puts back either version.** The first kit's put back would leave the two heights on a v2 camera, so it is not shipped.
  - **`open_gate_apply_no_meta.cmd`** applies the first kit's step (N19, the same library byte for byte).
- **Helper and tests.** The read-only helper is `fx3read_v2`: it also reports the two height words. 45 write cases and 16 read-only cases pass, including a camera holding v1.

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

## A library left on the camera blocked every later run (found and fixed 2026-11-26)

**Report.** An FX3 tester (macOS) could not apply any more, also after a cold boot: step 1 (L5) and the read-only dump both stopped with "a libJit.so is already on the service partition (25960 bytes, it is NOT this script's library) ... It is left alone".

**What it was.** The dump session's transcript holds the SHA-256 of the camera's answer (status word + file), `3f74e37f…`. It equals that of this kit's own L19 library (`c028f58c…`, 25,960 bytes). So an earlier L19 session sent its library and was cut off before deleting it. The service partition (`/tmp/jiritsu`) is flash, so the file outlives a cold boot. It is not loaded again by itself, and the camera was otherwise normal: the login and the known-answer read passed, and nothing was written in the stopped sessions.

**Why every run stopped.** The runner compared the file on the camera with the current step's library only. Every step has its own library, so a file left by one step was foreign to all the others, the read-only ones included. The one way out (`fx3_run.py L19 --remove-only --go --writes-memory --firmware-shown 7.02`) had no launcher, and the message did not say which step the file belonged to.

**The fix** (scripts only; no library was rebuilt, every pin is unchanged):
- The shared runner has a list of the calling kit's libraries (`ct6_level1_run.KNOWN_LIBS`, empty for the other kits: nothing changes for them). A file on the camera whose SHA-256 is in the list is deleted with the same command every session already ends with, the delete is confirmed by a read, and the run goes on.
- `fx3_run.py` lists all 15 current libraries and the 3 the first kit published and later kits replaced (its L20, check and dump).
- A file that is none of them is still left alone. The message now shows its SHA-256, and `--remove-library <SHA-256>` deletes exactly that file.
- `--remove-only` deletes any library of the kit, not only the named step's.
- `fx3_apply.py`: a stop at step 1 no longer says "Steps before it are applied", and a stop that may have left the library says the next run removes it.

**Checked** (`evidence/fx3/leftover_2026-11-26/`):
- Replay on the simulated camera with the L19 library on the service partition: the runner as published stops with the tester's message for L5, check, dump and I19; with the fix each deletes the file, then makes its normal run (one write, loaded once, gone afterwards).
- Each library's `--selftest` has 8 more cases: another step's library or its own left behind, a file the camera will not delete (stops before the write), `--remove-library` with the right and a wrong SHA-256, `--remove-only`, and the list itself.
- The A7 IV runner's own self-test prints the same 29 lines before and after; the A7S III, ZV-E1, FX2, FX30 and FX6 runners' self-tests pass.

**Not known.** Why that L19 session was cut off: its folder was not sent. **Not run on a camera:** the delete of a left library (the command itself is the one every session sends).

**The other kits** that use this runner have the same dead end; they do not have the list yet.

## The kit

- **Helpers.** `helper_fx3/fx3read.c` is `s3read.c` with text changes only. The write libraries are the A7 IV helper's levels 5/6, 16/17 and 19/20, which ran on the A7S III, with the FX3's tables. The optional playback step is the new levels 29/30 (above). Level 5 follows the sensor object 0x127ab68 → control +0x698 → the drive-parameter object.
- **Read-only emulation** (`emu_fx3.py`), for check and dump:
  - a stock FX3 reads READY;
  - applied, every site reads TARGET;
  - applied without the screen step, its 30 words read STOCK;
  - an A7S III image and a ZV-E1 image are refused (DIFFERS, NOT READY);
  - without the av-cam reservation, av-cam.bin is not read;
  - with an existing result, nothing is done.
  - **And the other way round:** the published A7S III and ZV-E1 check libraries both say NOT READY on an FX3, so neither kit's apply starts on one.
- **Write emulation** (`emu_fx3_write.py`, 113 cases: 45 for the open-gate and screen steps, 12 for the S-I step, 21 for the 25p/30p steps (2026-11-26), and the playback step's 35 from `emu_fx3_playback.py`):
  - apply, apply again, put back byte for byte;
  - foreign bytes, a lost write undone, a null records pointer, a wrong guard (each of the 32 screen guards);
  - the stored record as the A7S III tester's camera held it, with its run-time bytes left alone (the FX3's stock record is identical).
  - **Safety:** the A7S III kit's own L5, S16 and L19 libraries write nothing on an FX3, even with L5's pointer chain made to reach the FX3's real object.
- **Scripts.** `fx3_run.py` and `fx3_apply.py` are `s3_run.py` / `s3_apply.py` with this camera's libraries, pins, dump decoder and texts. The FX3 has no mode dial: the texts use its MODE button. Every library's `--selftest` and every launcher's `--dry-run` pass, also from the published tree. The dump decoder reads the panel type, the ratio, the frame rows, the de-squeeze ratios, the crop and the 30 words.

Library pins (2026-11-26): check `6f99aef2`, dump `fdb83bfe` (`fx3read_v2`), L5 `99116990`, L6 `a2f67b80`, O5 `9fd94c17` (= the 2026-11-25 kit's L5), L16 `cf644fb3`, L17 `5a3c16bf`, L19 `64793d5a`, L20 `ba041c6e`, N19 `47400649` (= the first kit's L19), S16 `bc40334b`, S17 `50a96268`, P29 `c0ccb8c8`, P30 `671de524`, I19 `3a553194`, I20 `0754c501` (full hashes in `fx3_run.py`). The 2026-11-25 kit: L5 `9fd94c17`, L6 `6c8544fb`, L19 `c028f58c`, L20 `b84dd675`, I19 `740ba559`, I20 `5cc2d1a6`. The first kit (run 2026-11-24): check `fcf97a8e`, dump `ad2bae79`, L19 `47400649`, L20 `6ca3ee7d`, header `fx3read_v1`, the other libraries as now. A result belongs to a kit only if its header and each step's manifest name that kit's libraries.

## Not known yet

- Whether the v2 headers change anything on the camera beyond the file (they did not on the A7 IV), and whether editors then open the original files at 3:2.
- **29.97p:** built and emulated, not run; 25p ran on a tester's FX3 with his own tools, not yet with this kit (see "Open gate at 25p and 29.97p" above).
- **XAVC S-I 4K:** built and emulated, not run (see its section above).
- **Why a tester's L19 session was cut off** and left its library on the camera (2026-11-26, see its section above).
- **In-camera playback:** the cause is found and the playback step is built and emulated, not run (see "The playback step" above). Until it is tested, testers are told not to play clips back.
- What made the first apply run unreliable for tester 1. The dumps show no fault, and the camera was started afresh between the two runs.
- What the A7S III left open: the glitchy live view on entering movie mode from stills, exposure and autofocus, 60p (crashed the A7S III).
- Whether the power switch alone removes the patch on the FX3 (it does on the A7S III; tester 1's second boot does not say which way the camera was restarted).
- That the menu's 1.3x / 1.5x / 1.6x / 2.0x send the codes 1 / 2 / 3 / 4. This is inferred from the ratios; appFw's mapping was not read.
- What the FX3's HDMI output shows in the open-gate state, with or without de-squeeze. HDMI is not part of this kit.
- The scaler-state addresses the dump reads were ported by code reference. The second scaler's block and input words are only predicted, as they were on the A7S III.
