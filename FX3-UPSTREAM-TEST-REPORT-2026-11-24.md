# FX3 7.02: physical 23.976p HS and S recording results

Test date: 2026-11-24. One Sony ILME-FX3, firmware 7.02.

## Scope and provenance

These are physical results from a separate, locally instrumented implementation of the three-stage sensor/output/encoder approach, with preimage checks, readback, cleanup and cold-start verification. They do **not** certify this repository's launchers, Android APK, macOS transport or screen step. No screen changes were applied. This report does not add a firmware patch.

## Recorded files

| Original card file | Codec | Decoded raster | Rate | Frames / duration | Audio |
| --- | --- | --- | --- | --- | --- |
| YM_1701.MP4 | HEVC, 4:2:2 10-bit | 3840 x 2560 | 24000/1001 | 216 / 9.009 s | stereo PCM, 48 kHz |
| YM_1702.MP4 | AVC High 4:2:2, 10-bit | 3840 x 2560 | 24000/1001 | 216 / 9.009 s | stereo PCM, 48 kHz |

The selected camera profiles were XAVC HS 4K and XAVC S 4K respectively, 23.98p, 100M 4:2:2 10-bit, APS-C/S35 Off. Full video/audio decode and frame cadence checks passed. These are short tests, not sustained-recording qualification.

SHA-256:
- YM_1701.MP4: `77c11c5db7ab0c4745afb358ac598ce9ce8053df800356b565a52dd3330e446c`
- YM_1702.MP4: `7bc4d55d4d8d9db13333479cfd949468613342405294d69a4a16ac5933cab63e`
- YM_1702M01.XML: `f608edd30327e459ab81b4947ffd024f2471e54de5643dc45ec36c271213ade7`
- DSC04630.JPG (S reference): `5d35222c8903ddb17bd5a2edeccfef7b2e7fa859910460747fbb638c8539dae9`

## Field of view, not just pixel count

Fixed-setup 4240 x 2832 reference photos were compared with decoded frames using SIFT and local patch registration.

- HS: approximately 99.9% of photo width and 99.7–99.9% of photo height.
- S: frames 0, 108 and 215 measured 99.963–99.992% of photo width and 99.884–99.963% of photo height across the two methods.
- A full-width 16:9 crop would cover about 84.216% of photo height. An artificial crop/stretch control measured about 84.285%, versus the predicted 84.283%.

This supports essentially the complete reference-photo field, not a vertically stretched 16:9 crop. It does not prove individual photosite readout. Sparse features on the upper wall limit exact edge precision.

## Container metadata remains inconsistent

For original YM_1702, the decoded AVC/SPS raster is 3840 x 2560, but:
- MP4 tkhd display height and avc1 sample height remain 2160.
- Sony VPRF remains 3840 x 2160.
- Embedded and sidecar XML remain 3840 x 2160, 16:9.
- avcC/SPS/VPRF signal level 5.1. The picture contains 38,400 macroblocks, exceeding the 36,864 MaxFS limit of both AVC levels 5.1 and 5.2.

YM_1701 has analogous 2160-height presentation metadata despite decoded 2560-height HEVC. The owner reported Premiere imported the HS original with the wrong height; a separate metadata-corrected copy imported as 3840 x 2560. This does not establish native-file compatibility or camera playback.

For S, local diagnostic copies were tested:
1. Only tkhd/avc1 presentation height corrected: four MP4 bytes changed.
2. Geometry/XML and level signaling normalized: 18 MP4 bytes and nine sidecar XML bytes changed.

The complete mdat payload remains identical in both S copies. Decoded video, PCM and rtmd frame/packet hashes match the original, including timestamps. Level-6 labeling is a diagnostic picture-size correction, not a full AVC conformance certificate. **Premiere import of these S copies has not yet been confirmed.** No corrected copy was put back on the camera.

## Observed problems and recovery

- Playback of the earlier HS test YM_1700 showed “unable to display”; retrying froze the camera, which did not respond to OFF. With card activity stopped, battery removal recovered it. The cause is not established. Subsequent test clips were deliberately not played on-camera. The README's playback instruction deserves a warning for this configuration.
- At S recording start the owner saw a black LCD for less than half a second. All first 24 stored frames (0–0.959 s) contain the scene; no matching black interval was found in the file. Button-to-first-recorded-frame latency cannot be inferred from the file alone.
- After battery removal, a different boot ID, all 189 original values and 38 guard fields were verified, helpers were removed, and the ordinary Sony remote connection returned with recording stopped. Some service STOP transfers reported a pipe error; exit was established by observing the matching normal MSC device, not by claiming a successful STOP acknowledgement.

## Still unverified

PAL 25p Open Gate, 140M Open Gate, rear-screen 3:2/De-Squeeze behavior, camera playback, native-file Premiere compatibility, long recording, thermal behavior, autofocus/exposure behavior and rolling shutter are not qualified by these tests. No claim is made that a normal power-switch cycle alone always removes the changes.

## Suggested maintainer follow-up

Retain separate labels for successful card recording, corrected display metadata, LCD behavior and camera playback. Consider adding a playback caution before asking testers to replay a generated clip. The next useful work is native writer metadata compatibility and separately controlled PAL/screen validation.

Basic independent file checks (on preserved originals):

```sh
ffprobe -v error -show_streams -show_format -of json YM_1702.MP4
ffmpeg -nostdin -v error -xerror -err_detect explode -i YM_1702.MP4 -map 0:v:0 -map '0:a?' -f null -
ffprobe -v error -select_streams v:0 -show_frames -show_entries frame=width,height,pix_fmt,interlaced_frame,best_effort_timestamp_time -of json YM_1702.MP4
```

These commands do not independently establish field of view or inspect every Sony metadata field. The original footage, reference photos, proprietary binaries and device-identifying logs are not included in this documentation contribution.

