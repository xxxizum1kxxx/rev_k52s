#!/usr/bin/env python3
"""Prepare the Ricoh/PENTAX firmware files this project expects under fw/.

The firmware is NOT shipped with this repository. Download it yourself from
the official RICOH IMAGING support page (you must own the camera and accept
Ricoh's software license agreement), then let this tool verify, extract and
decode it locally:

  firmware_setup.py info                       # official pages, expected hashes
  firmware_setup.py open  [k5iis|k5]           # open the official download page
  firmware_setup.py import <file.zip|file.bin> # verify + extract + decode into fw/
  firmware_setup.py status                     # what is present in fw/

Nothing is downloaded automatically and nothing leaves your machine.
"""
import hashlib
import io
import pathlib
import sys
import webbrowser
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FW = ROOT / "fw"
sys.path.insert(0, str(ROOT / "tools"))
import pentax_fw  # noqa: E402

MAIN_SEC2_END = 0xA80000

TARGETS = {
    "k5iis": {
        "camera": "PENTAX K-5 IIs, firmware 1.07",
        "page_en": "https://www.ricoh-imaging.co.jp/english/support/digital/k-5_2_s.html",
        "page_ja": "https://www.ricoh-imaging.co.jp/japan/support/download/digital/k5_2_s.html",
        "archive": "k5_2s107.zip",
        "archive_sha256": "c2352d91669c8dce47fe84298baa47dedaa438b156a834a8a8a130f84e14db1f",
        "member": "fwdc218b.bin",
        "bin_sha256": "36b626a9ecd02e22161a1f3ef4e764f7641c2565bb82c866977aeb9eaad5ac97",
        "outputs": {
            "fwdc218b.bin": "36b626a9ecd02e22161a1f3ef4e764f7641c2565bb82c866977aeb9eaad5ac97",
            "fwdc218b_dec.bin": "8379b15c058dfa6cb597ef159b3920c50722c033c7e83a0e8a55a46a91ffecd1",
            "fwdc218b_full_dec.bin": "a31b6c8e88fefc634280235a3540486475aa349927b93137f0cfdf287eb4f4d3",
            "subcpu_arm.bin": "8d105c94b344ff11bb9ba159ac72e8ad4fe489e593af96bb70c14d1e971a4b84",
        },
    },
    "k5": {
        "camera": "PENTAX K-5, firmware 1.16 (only used for the K-5 vs K-5 IIs comparison)",
        "page_en": "https://www.ricoh-imaging.co.jp/english/support/digital/k-5_s.html",
        "page_ja": "https://www.ricoh-imaging.co.jp/japan/support/download/digital/k5_s.html",
        "archive": "k5_v116m.zip",
        "archive_sha256": None,
        "member": "fwdc209b.bin",
        "bin_sha256": "ac347bdcc9f80cce63fe13f7546223616f29812eafec8aaf95ce14da12b7bfd6",
        "outputs": {
            "k5-v116-fwdc209b.bin": "ac347bdcc9f80cce63fe13f7546223616f29812eafec8aaf95ce14da12b7bfd6",
            "k5-v116_dec.bin": "e9dac980fa20a19a9a08a70c355fcdfe319b10789e8b51fb95cc2e370fcb91d8",
        },
    },
}


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def identify_bin(data):
    h = sha256(data)
    for key, t in TARGETS.items():
        if h == t["bin_sha256"]:
            return key
    return None


def read_input(path):
    p = pathlib.Path(path)
    raw = p.read_bytes()
    if zipfile.is_zipfile(io.BytesIO(raw)):
        h = sha256(raw)
        known = [k for k, t in TARGETS.items() if t["archive_sha256"] == h]
        print(f"archive {p.name}: sha256 {h} ({'matches ' + known[0] if known else 'not a known archive hash'})")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = {n.lower().rsplit("/", 1)[-1]: n for n in z.namelist()}
            for t in TARGETS.values():
                if t["member"] in members:
                    return z.read(members[t["member"]])
        raise SystemExit(f"no fwdc218b.bin / fwdc209b.bin inside {p.name}")
    return raw


def derive(key, data):
    if key == "k5iis":
        full = pentax_fw.transform(data)
        return {
            "fwdc218b.bin": data,
            # pfwtool-compatible image: main + sec2 decoded, sub-CPU section left as shipped
            "fwdc218b_dec.bin": full[:MAIN_SEC2_END] + data[MAIN_SEC2_END:],
            "fwdc218b_full_dec.bin": full,
            "subcpu_arm.bin": full[MAIN_SEC2_END:],
        }
    return {"k5-v116-fwdc209b.bin": data, "k5-v116_dec.bin": pentax_fw.transform(data)}


def cmd_import(path):
    data = read_input(path)
    key = identify_bin(data)
    if key is None:
        raise SystemExit(
            f"firmware sha256 {sha256(data)} is not the expected version.\n"
            "This project was built against K-5 IIs 1.07 (and K-5 1.16 for comparison); "
            "other versions will not line up with the addresses in notes/.")
    t = TARGETS[key]
    print(f"identified: {t['camera']}")
    FW.mkdir(exist_ok=True)
    ok = True
    for name, blob in derive(key, data).items():
        good = sha256(blob) == t["outputs"][name]
        ok &= good
        (FW / name).write_bytes(blob)
        print(f"  fw/{name:24} {len(blob):#9x}  {'OK' if good else 'HASH MISMATCH'}")
    if not ok:
        raise SystemExit("some derived files do not match the reference hashes")
    print("done. fw/ is git-ignored; keep it out of commits.")


def cmd_status():
    for key, t in TARGETS.items():
        print(f"[{key}] {t['camera']}")
        for name, h in t["outputs"].items():
            f = FW / name
            state = "missing" if not f.exists() else ("OK" if sha256(f.read_bytes()) == h else "MISMATCH")
            print(f"  fw/{name:24} {state}")


def cmd_info():
    for key, t in TARGETS.items():
        print(f"[{key}] {t['camera']}")
        print(f"  official page (EN): {t['page_en']}")
        print(f"  official page (JA): {t['page_ja']}")
        print(f"  download          : {t['archive']}  ->  {t['member']}")
        if t["archive_sha256"]:
            print(f"  archive sha256    : {t['archive_sha256']}")
        print(f"  {t['member']} sha256: {t['bin_sha256']}")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "info":
        cmd_info()
    elif a[0] == "open":
        t = TARGETS[a[1] if len(a) > 1 else "k5iis"]
        print(f"opening {t['page_en']}\nRead and accept Ricoh's license agreement there, "
              f"download {t['archive']}, then run: firmware_setup.py import <path>")
        webbrowser.open(t["page_en"])
    elif a[0] == "import" and len(a) == 2:
        cmd_import(a[1])
    elif a[0] == "status":
        cmd_status()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
