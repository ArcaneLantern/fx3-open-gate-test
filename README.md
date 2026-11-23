# FX3 open gate: test kit (firmware 7.02)

<p><b>Not run on an FX3 yet.</b> This kit is the A7S III open-gate kit, which works on one tester's A7S III (2026-11-22), ported to the Sony FX3 (ILME-FX3) firmware 7.02. It records a true 3840 × 2560 picture of the whole sensor area at 23.98p, shows it at 3:2 on the rear screen, and sets the FX3's own De-Squeeze Display for it. The patch only writes to the camera's memory.</p>

**What it does.** A true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only. A battery pull removes it. On the A7S III, switching the camera off and on removes it too.

**Why it should work, and what is not known:**

- **Same software.** The FX3 7.02 image processor runs the A7S III 5.01 image-processor software, rebuilt at other addresses. It has the same sensor (IMX510), the same 40 video modes, the same sensor tables byte for byte, the same record calculator and the same scaler code.
- **Same designs.** Every step of this kit is the A7S III's working step at the FX3's addresses. Each was checked against the FX3's own code in emulation (`PORT_NOTES.md`).
- **Kits cannot be mixed up.** An A7S III kit run on an FX3 refuses to start, and so does this kit on an A7S III. Checked in emulation.
- **Not yet on a camera:** that the FX3 behaves like the A7S III did, the rear panel's shape, and what the De-Squeeze Display shows.

**No C3 preview routine.** The A7S III kit adds an anamorphic preview on its C3 key. The FX3 has its own **De-Squeeze Display**, so this kit keeps that instead and sets its shapes for the 3:2 picture (see "De-Squeeze Display").

**The rear screen.** Sony gives the FX3's monitor as 3.0-type, 1,440,000 dots, the same as the A7S III's. In the firmware's display table the only geometry with that many dots is 800 × 600, a **4:3** panel, so a 4:3 panel is the likely one. The panel's type is read from the camera's settings memory while it runs. The screen step is made to work on a 4:3 and on a 3:2 panel. The closing session of the apply reads the panel type and prints it: please send it back.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 7.02 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | The same, plus facts for the port: memory map, the camera's own logs, sensor register state, internal tables, the display tables (panel type, screen shape, de-squeeze shapes) | No |
| `open_gate_apply.cmd` | Applies the default state in four steps: open gate, then the screen at 3:2 with De-Squeeze Display set for it. Ends with one read-only session | **Yes: memory only** |
| `open_gate_apply_no_screen.cmd` | Only the three open-gate steps | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts the four steps back | Yes: memory only |
| `screen_putback.cmd` | Puts the screen step back | Yes: memory only |

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
3. Each Windows launcher has a macOS twin with the same name: `macos/check_readonly.command`, `dump_info.command`, `open_gate_apply.command`, `open_gate_apply_no_screen.command`, `open_gate_putback.command`, `screen_putback.command`. Everything below that says `.cmd` works the same with the `.command` file.

Each live run asks for your Mac password: macOS keeps its own driver on the camera's USB connection, and only an administrator can hand the camera over to the script. The script unmounts the camera's memory card first; it does not erase anything on it. The results go to the same `windows/camera_private` folder.

If macOS refuses to open a .command file ("unidentified developer" or "could not verify"), open System Settings > Privacy & Security, scroll down and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the .command file into the window, and press Return.

## Android (not run on a phone or camera yet)

`android/FX3-OpenGate.apk` runs this kit from a phone connected to the camera by USB-C (or an OTG adapter). It carries exactly the files in `windows/tools` of this commit and runs them unchanged; only the USB access, the dialogs and the folder for the results are the phone's.

1. Install the APK (allow installing from unknown sources). It installs beside the A7 IV and A7S III apps; they do not share anything on the phone.
2. Set the camera as for the PC (below), and also **USB Power Supply: Off**, or it charges from the phone.
3. **1. Read-only check** first: the apply starts only after a check on this phone said READY. Then **2. Apply to camera**. The "Screen step" box chooses between the four-step apply (ticked) and the three open-gate steps only.
4. When Android asks to open *FX3 Open Gate* for the camera, tick **Always** and press OK. It comes up twice: once in Mass Storage, once in service mode.
5. When the log says **unplug and plug in again**, do that with the phone cable. Never switch the camera off.
6. **Stop waiting** ends a wait for the camera. It never interrupts a step that is talking to the camera.
7. Afterwards, **Export logs** writes a zip to `Download/FX3-OpenGate/` on the phone: send that zip back.

**Self-test** and **Dry run** need no camera and send nothing.

## The read-only steps

Each launcher asks for the firmware version the menu shows. Each run makes a new folder in `windows/camera_private`.

- **Check or dump in the stills state:** a still mode, connect, run the launcher.
- **Dump of the 4K state:** set File Format XAVC S 4K (or XAVC HS 4K) at 24p, S&Q off, APS-C/Super 35 off, SteadyShot not on Active. Set Movie, record a few seconds, stop. **Stay in Movie**, connect, run `dump_info.cmd`.

What they do to the camera: they switch it to service mode, write one small program file to the service partition, which the camera loads once, and delete that file again in the same session. The program only reads and creates one file, its report, on the camera's RAM disk. Its source is `windows/tools/camera_tests/CT6_memory_read_check/helper_fx3/fx3read.c`.

## The write step

**What it changes.** Four groups of bytes in the running camera's memory, one per step:

1. The sensor read-out and the two 4K picture records of the image processor: full sensor height instead of the 16:9 band (the A7S III's sensor step v5).
2. One size word: 3840 × 2160 becomes 3840 × 2560.
3. The encoder's tables for XAVC HS 4K and XAVC S 4K at 23.98p and 25p.
4. The screen (30 words):
   - The height of a 16:9 picture on the rear screen goes from width × 9/16 to width × 2/3. The live view is a 16:9 frame holding the whole sensor area, so this shows it at its true 3:2 shape: thin black bars above and below on a 4:3 screen, the whole screen on a 3:2 one.
   - The focus frames are told where the picture now is.
   - De-Squeeze Display's shapes are set for the 3:2 picture (below).

Each step first checks that every byte it is about to change holds its stock value, writes, reads back, and undoes its own writes if anything does not match. `open_gate_apply_no_screen.cmd` runs only the first three.

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

- Use only XAVC HS 4K or XAVC S 4K at 24p. **On the A7S III 60p distorted the picture and crashed the camera**; other formats, frame rates, S&Q and APS-C/Super 35 are likely to fail or hang too.
- Every 16:9 picture on the rear screen takes the 3:2 shape, and De-Squeeze Display uses the 3:2 shapes, so other movie formats look wrong on the screen. 2.0x shows any picture at 3:1. HDMI output is not part of this kit and has not been checked.
- **Do not switch the camera off:** on the A7S III the power switch removes the patch. Assume it does here too, and apply it again after every power-off.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p. APS-C/Super 35 off, S&Q off. De-Squeeze Display Off for now.
2. Select a still mode. Then pull the battery for 10 seconds and switch on, so that nothing of an earlier run is left. The camera starts in the still mode. Do not go into Movie yet.
3. Connect USB and run `windows/check_readonly.cmd`. It must say VERDICT READY.
4. Run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
5. It runs four steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until the script says it is finished: either one removes what was applied.
6. After the four steps the script asks for one more session, which only reads. **Unplug USB, set Movie, look at the screen, and plug in again.** The script then runs the read-only dump by itself and prints the rear panel's type.
7. When it says so, unplug. The live view should be the whole picture at 3:2.
8. Record 20 to 30 seconds, stop, and play the clip back. Then try De-Squeeze Display at each setting.
9. To return to stock: battery out for 10 seconds (or switch off and on, if it works as on the A7S III), or `open_gate_putback.cmd`.

**The glitchy live view** (seen on the A7S III; the FX3 runs the same software)

- When Movie is entered from a still mode, the live view may be glitchy: purple, with the lower part black.
- Starting a recording corrects it. So does a read-only dump session in Movie, which is why the apply ends with one.
- On the A7S III it stays right until the next visit to a still mode. The file itself was right in every test. The cause is not found.

So, if you see it: **start and stop a short recording.**

**If the camera restarts by itself** at any point: do not pull the battery. Select a still mode, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds.

**Please send back**

- The zipped `windows/camera_private` folder, with the closing dump of the apply in it (it holds the rear panel's type).
- The clip, or its properties: size, frame rate, codec. Do the same with XAVC S 4K if you can.
- The rear screen with De-Squeeze Display Off and at each setting: a phone photo with something round in the picture helps.
- Whether the focus frames are drawn with De-Squeeze Display Off.
- **One check after a power-off.** When you are done: switch the camera off and on with the power switch (no battery pull), select a still mode, run `windows/check_readonly.cmd`, and include that folder. It tells us whether the power switch removes the patch on the FX3.
- Your settings: file format and record setting, frame rate, NTSC or PAL, SteadyShot, Log shooting.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Select a still mode, connect USB, run `dump_info.cmd`, and send the folder. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery. `open_gate_apply_no_screen.cmd` applies open gate without the screen step.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

**To remove only the screen step:** select a still mode and run `windows/screen_putback.cmd`.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 7.02 update*: another firmware or model. Nothing further is sent.
- *DIFFERS from the 7.02 update* in a check: not an FX3 on 7.02 (an A7S III gives this too). The apply will not start.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug, and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/`:
  - the scripts, the pinned program files and their source;
  - the four patch designs;
  - the builders and emulations of the designs (`tools/modding/fx3`).
- `macos/`: `setup.command` and one `.command` launcher per Windows launcher; they run `windows/tools`.
- `android/FX3-OpenGate.apk`: the phone app, carrying `windows/tools` as published here.
- `PORT_NOTES.md`: how the A7S III kit maps onto the FX3, what was checked and how, and what is not known.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
