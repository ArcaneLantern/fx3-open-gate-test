# FX3 open gate: test kit (firmware 7.02)

<p><b>Open gate works on the FX3 (two testers, 2026-11-24).</b> This kit is the A7S III open-gate kit ported to the Sony FX3 (ILME-FX3) firmware 7.02. It records a true 3840 × 2560 picture of the whole sensor area at 23.98p (and, new, at 29.97p in NTSC and 25p in PAL), shows it at 3:2 on the rear screen, and sets the FX3's own De-Squeeze Display for it. The patch only writes to the camera's memory.</p>

**Where it stands (2026-11-26):**

- **New in this version: open gate at 25p and 30p too.** The same apply now also covers 29.97p (NTSC) and 25p (PAL), in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K, so you can change the frame rate in the menu without a new apply. 25p is a tester's design that recorded open gate on his FX3 in PAL (`FX3-PAL25-MODE-0x820-REPORT-2026-11-25.md`); 29.97p is the same design at 30p and has **not run yet**. The sensor step now also works on a camera set to PAL (the previous one refused it). `open_gate_apply_only_24p.cmd` gives the previous, 24p-only sensor step (NTSC only).
- **50p, 60p, 100p and 120p cannot be open gate.** The sensor's only full-height read-out takes about 26 ms a frame (Sony's own fastest full-height mode runs at 36.7 fps), so 30p is the highest rate it serves. The fast 4K modes read only the 16:9 band, and that window is fixed inside the sensor. While the kit is applied those rates refuse to record.
- **The file is right.** Recorded in XAVC HS 4K (HEVC) and XAVC S 4K (AVC) at 23.98p: a true 3840 × 2560 picture. Against a full-sensor photo it covers 99.7–99.99% of the width and height (a second tester's measurement, `FX3-UPSTREAM-TEST-REPORT-2026-11-24.md`).
- **The screen is right.** The movie live view is 3:2. The dump read the rear panel's type: it is a **4:3** panel, as the firmware suggested.
- **The MP4 header fix (since 655784f), not run yet:** the files' MP4 headers (`tkhd`, the `stsd` sample entry and Sony's PROF/VPRF) now say 3840 × 2560, so editors open them at 3:2 without a remux. This is the A7 IV kit's header fix, which works on that camera, ported to the FX3. `open_gate_apply_no_meta.cmd` gives the first version's encoder step instead.
- **New in this version, not run yet: XAVC S-I 4K.** The same apply now also makes XAVC S-I 4K (All-Intra 4:2:2 10-bit) at 24p record 3840 × 2560. It is one more step at the end of `open_gate_apply.cmd`, so after one run you can switch between XAVC HS 4K, XAVC S 4K and XAVC S-I 4K in the menu without a battery pull or a second patch. It is the A7 IV kit's S-I step at the FX3's addresses, emulated on the FX3's own code. `open_gate_apply_no_si.cmd` leaves it out.
- **Do not play clips back on the camera** unless you are testing the playback step. On both testers' cameras an open-gate clip would not play ("unable to display"), and a second try froze the camera until the battery was pulled. Check the clips on a computer. The cause is found: the FX3 opens every playback at 4096 × 2160, too small for a 3840 × 2560 picture (the A7 IV uses its 8K size).
- **New, optional, not run on any camera: the playback step** (`playback_fix_apply.cmd`). It makes the FX3 open playback the way the A7 IV does, at 7690 × 4320 with that size's memory. It is a new kind of change for this kit (four instructions of the camera's AV code), so it is a separate launcher and the open-gate apply does not run it. See "The playback step".
- **Still not right:** Sony's XML (in the file and the sidecar) says 3840 × 2160, 16:9. The stream's level label (HEVC 5.0 / AVC 5.1) is below what a 3840 × 2560 picture needs; computers decode it anyway. The LCD goes black for under half a second when an XAVC S recording starts (the file is not affected).
- **A power-off removes the patch:** apply it again after every power-on.

**What it does.** A true 3840 × 2560 (3:2) recording in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 23.98p and (new) 29.97p in NTSC, or 24p and 25p in PAL, set in the camera's memory only. A battery pull removes it. On the A7S III, switching the camera off and on removes it too.

**Why it works:**

- **Same software.** The FX3 7.02 image processor runs the A7S III 5.01 image-processor software, rebuilt at other addresses. It has the same sensor (IMX510), the same 40 video modes, the same sensor tables byte for byte, the same record calculator and the same scaler code.
- **Same designs.** Every step of this kit is the A7S III's working step at the FX3's addresses. Each was checked against the FX3's own code in emulation (`PORT_NOTES.md`).
- **Kits cannot be mixed up.** An A7S III kit run on an FX3 refuses to start, and so does this kit on an A7S III. Checked in emulation.
- **Not reported yet:** what the De-Squeeze Display shows, the focus frames, long recordings, exposure and autofocus, 29.97p, 25p with this kit's own launchers (the tester used his own tools).

**No C3 preview routine.** The A7S III kit adds an anamorphic preview on its C3 key. The FX3 has its own **De-Squeeze Display**, so this kit keeps that instead and sets its shapes for the 3:2 picture (see "De-Squeeze Display").

**The rear screen.** Sony gives the FX3's monitor as 3.0-type, 1,440,000 dots, the same as the A7S III's. In the firmware's display table the only geometry with that many dots is 800 × 600, a **4:3** panel, and the first tester's dump read the panel's type: 2, a 4:3 panel. The 3:2 picture therefore has thin black bars above and below. The screen step works on a 4:3 and on a 3:2 panel.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 7.02 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | The same, plus facts for the port: memory map, the camera's own logs, sensor register state, internal tables, the display tables (panel type, screen shape, de-squeeze shapes) | No |
| `open_gate_apply.cmd` | Applies the default state in five steps: open gate (24p, and 30p / 25p), the screen at 3:2 with De-Squeeze Display set for it, then XAVC S-I 4K. Ends with one read-only session | **Yes: memory only** |
| `open_gate_apply_only_24p.cmd` | The default state with the previous sensor step: open gate at 24p only, NTSC only | **Yes: memory only** |
| `open_gate_apply_no_screen.cmd` | Only the three open-gate steps | **Yes: memory only** |
| `open_gate_apply_no_si.cmd` | The default state without the XAVC S-I 4K step (XAVC HS 4K and XAVC S 4K only, as the first version) | **Yes: memory only** |
| `open_gate_apply_no_meta.cmd` | The default state with the first version's encoder step: the MP4 headers keep saying 3840 × 2160 | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts the five steps back | Yes: memory only |
| `screen_putback.cmd` | Puts the screen step back | Yes: memory only |
| `playback_fix_apply.cmd` | **Optional, not run on any camera.** In-camera playback of the 3840 × 2560 clips, the A7 IV's way (see "The playback step") | **Yes: memory only** |
| `playback_fix_putback.cmd` | Puts the playback step back | Yes: memory only |

Nothing in this kit writes to the camera's firmware or to its settings.

## Before you start

1. The camera's menu must show **Ver. 7.02**. On any other version, stop and tell us the version.
2. **USB Connection Mode: Mass Storage.**
3. A charged battery. Do not record or play back while a step runs.
4. **Shooting mode on the FX3** is set with the **MODE** button: press MODE, turn the control wheel to the mode, press the centre of the wheel. "A still mode" below means Program Auto, Aperture Priority, Shutter Priority or Manual Exposure; "Movie" is Movie (not S&Q Motion).

## Windows, once

1. Install Python 3.10 or later from python.org (with the "py launcher").
2. Run `windows/setup.cmd`.
3. Install the libusb-win32 driver for the camera with [Zadig](https://zadig.akeo.ie): Options, List All Devices, pick the camera, choose libusb-win32, Replace Driver. The first run switches the camera to service mode, where it shows up as a new device (054C:0336): install the driver for that one too, then run the step again.

## macOS, once (not run on an FX3 yet)

The macOS kit is the A7 IV kit's macOS port, carried over unchanged apart from the launcher names. It runs the same scripts as Windows (`windows/tools`).

1. Python 3.9 or later: the one macOS offers with the Xcode Command Line Tools (run `xcode-select --install` in Terminal) works, or install it from python.org.
2. Double-click `macos/setup.command`. It sets up Python and the USB library the scripts use. No Homebrew and no driver are needed.
3. Each Windows launcher has a macOS twin with the same name: `macos/check_readonly.command`, `dump_info.command`, `open_gate_apply.command`, `open_gate_apply_no_screen.command`, `open_gate_apply_no_si.command`, `open_gate_apply_no_meta.command`, `open_gate_apply_only_24p.command`, `open_gate_putback.command`, `screen_putback.command`, `playback_fix_apply.command`, `playback_fix_putback.command`. Everything below that says `.cmd` works the same with the `.command` file.

Each live run asks for your Mac password: macOS keeps its own driver on the camera's USB connection, and only an administrator can hand the camera over to the script. The script unmounts the camera's memory card first; it does not erase anything on it. The results go to the same `windows/camera_private` folder.

If macOS refuses to open a .command file ("unidentified developer" or "could not verify"), open System Settings > Privacy & Security, scroll down and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the .command file into the window, and press Return.

## Android (not run on a phone or camera yet)

`android/FX3-OpenGate.apk` runs this kit from a phone connected to the camera by USB-C (or an OTG adapter). It carries exactly the files in `windows/tools` of this commit and runs them unchanged; only the USB access, the dialogs and the folder for the results are the phone's.

1. Install the APK (allow installing from unknown sources). It installs beside the A7 IV and A7S III apps; they do not share anything on the phone.
2. Set the camera as for the PC (below), and also **USB Power Supply: Off**, or it charges from the phone.
3. **1. Read-only check** first: the apply starts only after a check on this phone said READY. Then **2. Apply to camera**. The "Screen step" box chooses between the four-step apply (ticked) and the three open-gate steps only. The "XAVC S-I 4K step" box (ticked) adds the S-I step to the apply and the put back (app 0.4). The "24p only" box (unticked) takes the previous, 24p-only sensor step (app 0.6).
4. When Android asks to open *FX3 Open Gate* for the camera, tick **Always** and press OK. It comes up twice: once in Mass Storage, once in service mode.
5. When the log says **unplug and plug in again**, do that with the phone cable. Never switch the camera off.
6. **Stop waiting** ends a wait for the camera. It never interrupts a step that is talking to the camera.
7. Afterwards, **Export logs** writes a zip to `Download/FX3-OpenGate/` on the phone: send that zip back.

**Playback fix (untested)** and **Playback put back** run the playback step and its put back (app 0.3). Like the apply, they start only after a check on this phone said READY.

**Self-test** and **Dry run** need no camera and send nothing.

## The read-only steps

Each launcher asks for the firmware version the menu shows. Each run makes a new folder in `windows/camera_private`.

- **Check or dump in the stills state:** a still mode, connect, run the launcher.
- **Dump of the 4K state:** set File Format XAVC S 4K (or XAVC HS 4K) at 24p, S&Q off, APS-C/Super 35 off, SteadyShot not on Active. Set Movie, record a few seconds, stop. **Stay in Movie**, connect, run `dump_info.cmd`.

What they do to the camera: they switch it to service mode, write one small program file to the service partition, which the camera loads once, and delete that file again in the same session. The program only reads and creates one file, its report, on the camera's RAM disk. Its source is `windows/tools/camera_tests/CT6_memory_read_check/helper_fx3/fx3read.c`.

## The write step

**What it changes.** Five groups of bytes in the running camera's memory, one per step:

1. The sensor read-out and the two 4K picture records of the image processor: full sensor height instead of the 16:9 band (the A7S III's sensor step v5), for the 24p video mode and (new) the 30p/25p one, and each mode's stored settings in the form your camera holds (NTSC or PAL).
2. One size word: 3840 × 2160 becomes 3840 × 2560.
3. The encoder's tables for XAVC HS 4K and XAVC S 4K at 23.98p, 25p and (new) 29.97p, and the two height values the MP4 writer puts in the file's headers, 2160 → 2560. `open_gate_apply_no_meta.cmd` leaves the headers at 2160, as the first version did.
4. The screen (30 words):
   - The height of a 16:9 picture on the rear screen goes from width × 9/16 to width × 2/3. The live view is a 16:9 frame holding the whole sensor area, so this shows it at its true 3:2 shape: thin black bars above and below on a 4:3 screen, the whole screen on a 3:2 one.
   - The focus frames are told where the picture now is.
   - De-Squeeze Display's shapes are set for the 3:2 picture (below).
5. XAVC S-I 4K (25 sites): the S-I encoder request's height, and the six S-I 4K descriptors for 23.98p, 25p and 29.97p (both bit-rate classes) with their profiles: height 2560, and the rows the first of the two encoder cores takes, 1072 → 1280. The bit rate stays the menu's (240M at 24p, 300M at 30p), so a bigger picture gets the same bits. No memory change is needed: at 3840 × 2560 the S-I encoder asks the same memory blocks as XAVC S 4K, and the codec firmware's own calculation needs 44 of their 101 MB. XAVC HS 4K and XAVC S 4K are not touched by this step, and its sites are none of step 3's.

Each step first checks that every byte it is about to change holds its stock value, writes, reads back, and undoes its own writes if anything does not match. `open_gate_apply_no_screen.cmd` leaves out step 4, `open_gate_apply_no_si.cmd` step 5.

**Already applied?** Running `open_gate_apply.cmd` again in the same power-on is fine: steps that find their bytes already in place say NOTHING TO DO. So on a camera patched with the previous version in the same power-on, one more run adds only the new 30p/25p parts.

**De-Squeeze Display** (MENU > Setup > Display Option > De-Squeeze Display; Sony's own feature, in Movie). The camera works out each shape for a 16:9 picture. With the open-gate picture, which is 3:2, every shape would be about 18% too wide, so step 4 gives it the shapes of the 3:2 frame:

| Setting | Stock FX3, 16:9 picture | With this kit, the 3:2 open-gate picture |
|---|---|---|
| 1.3x | 2.31:1 | **1.95:1** |
| 1.5x | 2.67:1 | **2.25:1** |
| 1.6x (1.65x) | 2.93:1 | **2.475:1** |
| 2.0x | 2.67:1 (the centre 4:3 of the frame) | **3:1: the whole frame** (the centre crop is turned off) |

All of it is the preview only: the recorded file does not change. The camera itself sets manual focus while De-Squeeze Display is on (Sony's Help Guide).

**What we do not know yet.** Everything on an FX3. From the A7S III, expect:

- The live view may be glitchy when Movie is entered from a still mode (see "The glitchy live view").
- Exposure and autofocus in this mode are not reported.
- The sensor is read more slowly: expect more rolling shutter (about 26 ms top to bottom).

**While it is applied**

- Use only XAVC HS 4K, XAVC S 4K or XAVC S-I 4K at 24p, or 30p (NTSC) / 25p (PAL); with `open_gate_apply_only_24p.cmd`, 24p only. 50p, 60p and faster will not record. **On the A7S III 60p distorted the picture and crashed the camera**; other formats, S&Q and APS-C/Super 35 are likely to fail or hang too.
- Every 16:9 picture on the rear screen takes the 3:2 shape, and De-Squeeze Display uses the 3:2 shapes, so other movie formats look wrong on the screen. 2.0x shows any picture at 3:1. HDMI output is not part of this kit and has not been checked.
- **Do not switch the camera off:** on the A7S III the power switch removes the patch. Assume it does here too, and apply it again after every power-off.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p (or 30p / 25p). APS-C/Super 35 off, S&Q off. De-Squeeze Display Off for now.
2. Select a still mode. Then pull the battery for 10 seconds and switch on, so that nothing of an earlier run is left. The camera starts in the still mode. Do not go into Movie yet.
3. Connect USB and run `windows/check_readonly.cmd`. It must say VERDICT READY.
4. Run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
5. It runs five steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until the script says it is finished: either one removes what was applied.
6. After the five steps the script asks for one more session, which only reads. **Unplug USB, set Movie, look at the screen, and plug in again.** The script then runs the read-only dump by itself and prints the rear panel's type.
7. When it says so, unplug. The live view should be the whole picture at 3:2.
8. Record 20 to 30 seconds and stop. **Do not play it back on the camera** (see above): check it on a computer. Then try De-Squeeze Display at each setting.
9. 30p (NTSC) or 25p (PAL), new: set the frame rate in the menu, no new apply, and record 20 to 30 seconds. Please say whether the picture is the whole sensor as at 24p, and send the clip's MediaInfo.
10. XAVC S-I 4K: set File Format XAVC S-I 4K, 24p (240M), Proxy Recording Off, a fast card (V90 SD or CFexpress). Record 20 to 30 seconds. Then switch back to XAVC HS 4K and record a short control clip.
11. To return to stock: battery out for 10 seconds (or switch off and on, if it works as on the A7S III), or `open_gate_putback.cmd`.

**The glitchy live view** (seen on the A7S III; the FX3 runs the same software)

- When Movie is entered from a still mode, the live view may be glitchy: purple, with the lower part black.
- Starting a recording corrects it. So does a read-only dump session in Movie, which is why the apply ends with one.
- On the A7S III it stays right until the next visit to a still mode. The file itself was right in every test. The cause is not found.

So, if you see it: **start and stop a short recording.**

**If the camera restarts by itself** at any point: do not pull the battery. Select a still mode, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds.

**Please send back**

- The zipped `windows/camera_private` folder, with the closing dump of the apply in it (it holds the rear panel's type).
- The clip, or its properties: size, frame rate, codec. Do the same with XAVC S 4K if you can. With this version: what MediaInfo says (`mediainfo --Output="Video;%Width%x%Height% original %Width_Original%x%Height_Original%" FILE` should give 3840x2560 with no "original" size), and whether Resolve or Premiere opens the original file at 3:2. ffprobe cannot show this change: it reads the size from the stream, which was always 3840 × 2560.
- The XAVC S-I 4K clip: what MediaInfo says (`mediainfo --Output="Video;%Width%x%Height% %Format_Profile% %BitRate%" FILE`), whether the picture is the whole 3:2 frame (not 16:9 stretched), and whether it recorded to the end.
- The rear screen with De-Squeeze Display Off and at each setting: a phone photo with something round in the picture helps.
- Whether the focus frames are drawn with De-Squeeze Display Off.
- **One check after a power-off.** When you are done: switch the camera off and on with the power switch (no battery pull), select a still mode, run `windows/check_readonly.cmd`, and include that folder. It tells us whether the power switch removes the patch on the FX3.
- Your settings: file format and record setting, frame rate, NTSC or PAL, SteadyShot, Log shooting.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Select a still mode, connect USB, run `dump_info.cmd`, and send the folder. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery. `open_gate_apply_no_screen.cmd` applies open gate without the screen step; if only XAVC S-I 4K misbehaves, `open_gate_apply_no_si.cmd` leaves its step out.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

**To remove only the screen step:** select a still mode and run `windows/screen_putback.cmd`.

## The playback step (optional, not run on any camera yet)

**Why playback fails.** When the FX3 starts playing a clip, its AV code opens the video decoder at a fixed 4096 × 2160 with memory for that size. A 3840 × 2560 picture is taller than that, so playback start fails ("Unable to display"). The A7 IV runs the same code and opens the decoder at 7690 × 4320 with the 8K memory (it opens the 4K size only for one kind of clip that the FX3 does not make), and the A7 IV plays its own 3840 × 2560 clips. The A7S III's software opens it the A7 IV's way; the FX3's always opens the 4K size.

**What it changes.** In the camera's memory only: in its AV code (`av-cam.bin`, which runs in the kernel), the two memory ids the decoder asks for, 4K → 8K (four instruction words; two of them are only the ids written into an error message), and one word of its decode size table, 4096 × 2160 → 7690 × 4320. The rest of that table row is already the A7 IV's.

**Why it is a separate step.** Every other step of this kit changes data. This one changes instructions that the processors may hold in their caches. The step:

- refuses unless every byte of that 4 KB of code is exactly as in the 7.02 firmware file, both as it reads it and as the kernel reads it;
- reads the processors' cache type and refuses unless it can make them fetch the new instructions, and also maps the code so that the cache is reached at the address the kernel runs it from;
- runs that cache sequence once before it writes anything: if the processor did not allow it, the step would end there with nothing changed;
- writes the ids first and the table word last; the put back does the reverse. A 4K size with 8K memory is harmless; the other way round is not, so it never happens;
- puts back everything it wrote if any write is not seen.

The open-gate state is not needed for it, and the open-gate apply and put back leave it alone. A battery pull removes it.

**How to test it**

1. A still mode, connect USB, `windows/check_readonly.cmd` (VERDICT READY), then `windows/playback_fix_apply.cmd`. It asks for the firmware version and a typed YES, and runs one session.
2. Unplug. Press the playback button and open an ordinary 16:9 clip (4K or HD) first: it should play as before.
3. Then **one** open-gate clip. If it says "Unable to display", **do not try again** (a second try froze an FX3 before): leave playback and send the folder. If the camera freezes or restarts, pull the battery for 10 seconds.
4. If it plays: does it show the whole 3:2 frame, and does it play to the end? Does skipping and pausing work?
5. Put it back with `windows/playback_fix_putback.cmd`, or pull the battery.

Please send the `camera_private` folder (the step's report includes the processors' cache type) and what each clip did.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 7.02 update*: another firmware or model. Nothing further is sent.
- *DIFFERS from the 7.02 update* in a check: not an FX3 on 7.02 (an A7S III gives this too). The apply will not start.
- *A library from an earlier session is still on the service partition ... Deleting it now*: an earlier session was cut off after it sent its program file (the camera restarted, the cable came out, Ctrl+C), so the file stayed on the camera. A cold boot does not remove it, but the camera does not load it again by itself. Every launcher now deletes such a file of this kit first and carries on: nothing to do.
- *a libJit.so is already on the service partition ... it is NOT this script's library ... It is left alone*, from a copy of this kit older than 2026-11-26: the same thing, before that fix (one FX3 could not be patched any more because of it). Update the kit and run any launcher, for example `check_readonly`.
- *a libJit.so is already on the service partition ... none of this kit's libraries*: a file another tool left there. It is left alone and its SHA-256 is printed. If you know what it is, `check_readonly.cmd --remove-library <that SHA-256>` (macOS: `./check_readonly.command --remove-library <that SHA-256>`) deletes it and then makes the check.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/`:
  - the scripts, the pinned program files and their source;
  - the patch designs of every step, the playback step's included;
  - the builders and emulations of the designs (`tools/modding/fx3`).
- `macos/`: `setup.command` and one `.command` launcher per Windows launcher; they run `windows/tools`.
- `android/FX3-OpenGate.apk`: the phone app, carrying `windows/tools` as published here.
- `PORT_NOTES.md`: how the A7S III kit maps onto the FX3, what was checked and how, and what is not known.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
