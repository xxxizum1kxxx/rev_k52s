English | [简体中文](firmware-checksum.zh-CN.md)

# Firmware integrity checks (K-5 IIs 1.07 / K-5 1.16)

Conclusions:

1. **Model markers**: the updater checks them. Certain.
2. **Zero word sum**: the image satisfies it, but no code performing this check was found in the main firmware.
3. `tools/pentax_fw.py checksum` / `fix` cover both. After changing any byte, restoring the word sum with `fix` is safer than leaving the image "unbalanced".

This document is for offline tooling only. As agreed in the project plan, **no modified firmware is flashed**.

## 1. Model markers (checked by the updater)

Each marker is 8 bytes: `model * 0x10001`, then `0xA55A5AA5`. The K-5 IIs model code 541 (0x21D) gives `021D021D A55A5AA5`; the K-5 is 505 (0x1F9).

The check is `FUN_104B4EAE(obj, section)`:

- It first compares the model-code word at `0x107817E0[section]` with `obj+0x280`. `FUN_104B3A54` takes the model code from the firmware header, or `obj+0x288` overrides it.
- It then checks the 5 positions in the table at `0x107817F8 + section*0x14`. The table stores halfword indices: multiply by 2 for byte offsets, relative to the decoded image buffer `_DAT_C0004564`.

| Section | Model-code word | Marker offsets (deduplicated) |
| --- | --- | --- |
| 0 main | `0x000010` | `0x1F8`, `0xFFFF0`, `0x7FFFF8`, `0x800008`, `0x9FFFF8` |
| 1 second | `0xA00060` | `0xA00070`, `0xA77FF8`, `0xA7FBF0` |
| 4 sub-CPU | `0xA80110` | `0xA80100`, `0xABFFF0` |

The recovery updater in the boot area, `FUN_100F0CA4`, does the same main-section marker check with its own table `0x100F23F0` and `FUN_100F0D6C`.

K-5 1.16 uses exactly the same marker offsets, minus the sub-CPU section; see [k5-vs-k5iis.md](k5-vs-k5iis.md).

## 2. User update flow (`FWDC218B.BIN`)

`FUN_104B437A`:

1. `FUN_104B6BAC` finds the file and `fwup_load_image(5, buf)` reads it.
2. `FUN_104B4FE0(obj, 5)` → `FUN_101F72BC` decodes sections 0, 1 and 4. It uses the same XOR algorithm as `pentax_fw.py`, with these tables:
   - IV offsets `0x106F200C`
   - start offsets `0x106F1FF4`
   - word counts `0x106F2024`
   - initial block numbers `0x106F203C`
3. `FUN_104B4EAE` checks the model markers of sections 0, 1 and 4; failure is reported by `FUN_101F705C`.
4. `FUN_104B4F3E` shows the old and new versions, and `FUN_101F7280` **forbids downgrades**.
   - The main section requires current version ≤ file version, comparing with the minor byte masked.
   - The second and sub-CPU sections always pass.
5. `FUN_104B5120` and others write the sections.
   - The second section goes to another chip through the `obj+0x248` interface.
   - After writing, `FUN_104B5022` (second section) and `FUN_104B506E` (sub-CPU section) compare the read-back word by word with the buffer, skipping word indices `0x1E000..0x1EFFF`.
6. The main section is flashed by `SUB_C000146C` running from RAM.

There is **no summing loop** on this path. A whole-image search for `LDI:32` loads of length constants such as `0xA00000` or `0x280000` finds nothing either. If the word sum is checked, it may be in the boot ROM, the RAM flasher or the sub-CPU, outside this dump.

## 3. Zero word sum (satisfied by the image)

| Section | Range (decoded offsets) | Big-endian 32-bit word sum | Compensation word |
| --- | --- | --- | --- |
| main | `[0x000000, 0xA00000)`, including the plain header | 0 (both K-5 IIs 1.07 and K-5 1.16) | Factory location unknown. `fix` defaults to `0x9FFFEC`, at the end of the 0xFF padding run `0x9E5F40..0x9FFFF0`, before the trailer marker |
| sub-CPU | `[0xA80000, 0xAC0000)`, including the IV at `0xABFF80` | 0 | Last word, `0xABFFFC` = `0x0764C0A8` |
| second | `[0xA00000, 0xA80000)` | Non-zero. Big- and little-endian prefix sums from any start in the first 0x800 bytes never reach zero | Unknown (the content looks like another encoding layer, left for the receiving chip to verify) |

This matches the K-30 PentaxFirmwareTool, where the K-30 also uses "model markers + zero big-endian 32-bit word sum".
- The K-30 tool frees 4 bytes for the compensation value by shortening an unused string. This tool uses the padding area instead and never touches strings.
- The K-30 documentation mentions "the check is skipped when the overwrite word is `0xFFFFFFFF`". No matching code was found on the K-5 IIs; do not rely on it.

## 4. Tool usage

```bash
python3 tools/pentax_fw.py checksum fw/fwdc218b.bin          # encoded or decoded image
python3 tools/pentax_fw.py fix IN OUT                        # main section, compensation word 0x9FFFEC
python3 tools/pentax_fw.py fix IN OUT --section sub          # sub-CPU section, compensation word 0xABFFFC
python3 tools/pentax_fw.py fix IN OUT --at 0x9FFFE8          # explicit compensation word position
```

`fix` keeps the encoding of its input (encoded in, encoded out). The compensation word must be inside the section, 4-byte aligned, and must not overlap any model marker.

## 5. Offline verification log (2026-10-21)

| Input | Result |
| --- | --- |
| Factory `fwdc218b.bin` (encoded) | Markers correct in all three sections; main and sub-CPU sums are 0 |
| Factory full decode `fwdc218b_full_dec.bin` | Same |
| K-5 1.16 `fwdc209b.bin` (0xA80000 container) | Markers correct in both sections (model 505); main sum is 0 |
| One byte changed at `0x6F2481` (main string) and at `0xA90000` (sub-CPU), re-encoded | Main sum `0xFFFF0000`, sub-CPU sum `0x80000000`; reported as errors |
| `fix` (main), then `fix --section sub` | Both sums back to 0; after decoding, differs from factory only in the 2 changed bytes and 2 compensation words |
| `fix --at 0x1F8` | Refused: overlaps a model marker |
