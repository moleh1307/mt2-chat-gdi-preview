# Normal Tahoma / native Windows GDI export

Isolated font exporter and chat diagnostic. No game, save, UI layout or other font files are modified. Python standard library only; no font download, package installation, system-font changes or raw-font redistribution.

## Native export

On Windows:

```text
python bake_chat_gdi.py --sizes 9,12,14 --output out
```

The exporter refuses macOS, Linux, Wine, font substitution, unexpected metrics and unexpected Win32 structure sizes. It requests `Tahoma`, **positive lfHeight9/12/14**, weight400 (`FW_NORMAL`), non-italic, Turkish charset162, quality4 (`ANTIALIASED_QUALITY`). It uses `CreateFontIndirectW`, per-character `GetCharABCWidthsFloatW`/`GetTextExtentPoint32W`, `TextOutW` into a32-bit top-down DIB and `GdiFlush` before reading pixels. Glyph crop and `ceil(A+B+C)` advance follow the archived client's `GrpFontTexture::UpdateCharacterInfomation`; every nonzero blue byte becomes opaque white. There is no outline, stroke dilation, FreeType approximation or bitmap enlargement.

Outputs: a `tahomaN-gdi.json` and `tahomaN-gdi.png` for each requested height. The default remains12; compare.html accepts only the original chat size12. Metadata records Windows build, actual font metrics, selected TrueType-font SHA256 and atlas SHA256. No user name, machine name, private paths, source font file or game data is exported.

## Local comparison

Open `compare.html` in a browser. Select the reference screenshot and the exported JSON. Both stay in the browser; this page performs no network requests. The native glyphs are shown at1× with the existing chat's21px row spacing. Optional2× inspection enlarges both images equally and is explicitly a viewing zoom.

This establishes native Windows GDI output. It does **not** establish that the archived source, installed Tahoma version, Windows build or video scaling match an unknown reference client. Do not label a missing export, Wine rasterizer, synthetic fixture or macOS approximation as genuine GDI.

## Optional cloud export

The included GitHub Actions workflow is manual-only, one `windows-2022` job with a5-minute timeout and1-day artifact retention. It runs the standard-library checks, exports normal Tahoma9/12/14 and uploads only their six output files. It needs no project files, reference screenshot, game save, external secrets or raw font.

It is a locally prepared proposal. Creating a remote repository, publishing these files or starting a cloud job requires the user's authorization. Standard public GitHub-hosted Windows jobs are free under GitHub's published standard-runner rules; private-repository jobs can consume the account's quota and incur charges. No remote job is started by opening this folder or preview.

## Checks

```text
python test_baker.py
```

On a non-Windows host, these check source metric rounding, Turkish character coverage, PNG pixels/CRC and refusal to generate a substitute. Native GDI execution must be tested on Windows before claiming that an atlas exists.

Source references:

- `https://github.com/NakiuS/Metin2Client`, commit `40e2d9fef3bed9fa56a113001ae678efb72e06d3`, `source/EterLib/GrpFontTexture.cpp`, `GrpTextInstance.cpp` and `Util.cpp`.
- `https://github.com/d1str4ught/m2dev-client`, commit `ecef2dcdb89f5d0344677b2902ad175809b70f52`, Turkish and English `locale_game.txt`: Tahoma12/14/9.
- `https://docs.github.com/en/actions/reference/runners/github-hosted-runners`.
