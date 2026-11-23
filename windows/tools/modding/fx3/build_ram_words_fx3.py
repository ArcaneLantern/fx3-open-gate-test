"""Build `outsz2560_fx3_v1`: the FX3 7.02 counterpart of the A7S III's working `outsz2560_s3_v1` (one word of coprocessor RAM).

  C:/Python313/python.exe -B build/build_ram_words_fx3.py

The movie size table is filled at run time by 0x4008ec (the A7S III's 0x40af34 relinked: same 904-byte body, only
relocated branch targets and MOVW/MOVT pairs differ). build/emu_size_table.py runs it on the FX3 image: base 0x13c3144,
table at 0x13c3190, 16 entries identical to the A7S III's. The word changed is the second entry of size class 3:
3840 x 2160 -> 3840 x 2560; the two guards are the entry before it and the memory id after it, as on the A7S III.
Design only; never run on a camera.
"""
import hashlib
import json
import struct
from pathlib import Path

import emu_size_table

ROOT = Path(__file__).resolve().parent.parent
BUILD, REF, NAME = "fx3_702", "a7s3_501", "outsz2560_fx3_v1"
SHA = "c90d00d807874a5309dc1b65b203287e83608ceee513cc57b53409333fb6bcba"


def main():
    t, rows, writes = emu_size_table.table(BUILD)
    r_t, r_rows, _ = emu_size_table.table(REF)
    assert t == 0x13C3190 and rows == r_rows, "the FX3 size table differs from the A7S III's"
    site = t + 8 * 7
    assert rows[6] == (3840, 2160, 0x43E) and rows[7] == (3840, 2160, 0x2D9)
    ref = json.loads((ROOT / "modding/designs/outsz2560_s3_v1.json").read_text(encoding="utf8"))
    img = emu_size_table.Path(ROOT / "work/extracted" / BUILD / "0700_part_image/dev/nflasha8/cpapp-b.bin").read_bytes()
    assert hashlib.sha256(img).hexdigest() == SHA
    out = {"design": NAME, "build": BUILD, "camera": "ILME-FX3 (FX3), firmware 7.02", "kind": "ram_words",
           "title": "Output size of the stock 4K movie request: 3840 x 2160 -> 3840 x 2560 (size class 3, second entry)",
           "status": "addresses from emulating the FX3's own size-table function; never read or written on an FX3. The same word change "
                     "(outsz2560_s3_v1) works on an A7S III",
           "emulated_image_sha256": SHA,                  # not `artifact_sha256`: the word is RAM the camera fills at run time, not a byte of the file
           "generated_by": "build/build_ram_words_fx3.py", "ported_from": "outsz2560_s3_v1 (A7S III 5.01, RAM 0x13ec2e4)",
           "sites": [{"ram_address": hex(site), "old": struct.pack("<HH", 3840, 2160).hex(), "new": struct.pack("<HH", 3840, 2560).hex(),
                      "what": "size class 3, second entry: width, height"}],
           "guards": [{"ram_address": hex(site - 8), "bytes": struct.pack("<HHI", 3840, 2160, 0x43E).hex(), "what": "size class 3, first entry and the raw write buffer id"},
                      {"ram_address": hex(site + 4), "bytes": struct.pack("<I", 0x2D9).hex(), "what": "the output buffer's memory id"}],
           "precondition": ref["precondition"], "restore": ref["restore"],
           "emulated": {"function": "0x4008ec", "table": hex(t), "entries_equal_a7s3_501": True, "stores_into_block": len(writes)},
           "not_shown": ["anything on an FX3"] + ref["not_shown"]}
    for s, g in ((out["sites"], ref["sites"]), (out["guards"], ref["guards"])):
        assert [(x.get("old"), x.get("new"), x.get("bytes")) for x in s] == [(x.get("old"), x.get("new"), x.get("bytes")) for x in g]
    dst = ROOT / "modding" / "designs" / f"{NAME}.json"
    dst.write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"size table {t:#x} (A7S III {r_t:#x}): 16 entries equal; site {site:#x}")
    print("wrote", dst)


if __name__ == "__main__":
    main()
