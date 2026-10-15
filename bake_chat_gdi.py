#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bake normal Tahoma:9/12/14 using native Windows GDI; standard library only.

Matches the archived client's LOGFONT, per-character ABC advances, DIB crop
and blue!=0 -> opaque white conversion. No FreeType/GDI+/canvas fallback.
This tool does not read or write game saves, game files, or system settings.
"""
import argparse
import base64
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import zlib


def engine_metrics(a, b, c):
    # GrpFontTexture::UpdateCharacterInfomation assigns B to LONG first.
    width = int(b) + math.ceil(max(0, a)) + math.ceil(max(0, c)) + 1
    return width, math.ceil(a + b + c)


def png_rgba(width, height, pixels):
    if width < 1 or height < 1 or len(pixels) != width * height * 4:
        raise ValueError('Invalid RGBA dimensions')
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data) & 0xffffffff)
    rows = b''.join(b'\0' + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')


def character_set():
    latin = bytes(range(32, 256)).decode('cp1254', errors='ignore')
    return sorted(set(latin + ''.join(chr(n) for n in range(0x100, 0x180)) + '→–—…'), key=ord)


def bake(height=12):
    if height not in (9, 12, 14):
        raise ValueError('Only original locale heights 9, 12 and 14 are supported')
    if sys.platform != 'win32':
        raise RuntimeError('Native Windows GDI is required. No substitute atlas was generated.')
    from ctypes import wintypes as W
    gdi = C.WinDLL('gdi32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    kernel.GetProcAddress.argtypes = [W.HMODULE, C.c_char_p]
    kernel.GetProcAddress.restype = C.c_void_p
    if kernel.GetProcAddress(kernel.GetModuleHandleW('ntdll.dll'), b'wine_get_version'):
        raise RuntimeError('Wine detected. This preview requires native Windows GDI.')

    class LOGFONTW(C.Structure):
        _fields_ = [(k, W.LONG) for k in ['lfHeight', 'lfWidth', 'lfEscapement', 'lfOrientation', 'lfWeight']] + [(k, W.BYTE) for k in ['lfItalic', 'lfUnderline', 'lfStrikeOut', 'lfCharSet', 'lfOutPrecision', 'lfClipPrecision', 'lfQuality', 'lfPitchAndFamily']] + [('lfFaceName', W.WCHAR * 32)]

    class BITMAPINFOHEADER(C.Structure):
        _fields_ = [('biSize', W.DWORD), ('biWidth', W.LONG), ('biHeight', W.LONG), ('biPlanes', W.WORD), ('biBitCount', W.WORD), ('biCompression', W.DWORD), ('biSizeImage', W.DWORD), ('biXPelsPerMeter', W.LONG), ('biYPelsPerMeter', W.LONG), ('biClrUsed', W.DWORD), ('biClrImportant', W.DWORD)]

    class ABCFLOAT(C.Structure):
        _fields_ = [('a', C.c_float), ('b', C.c_float), ('c', C.c_float)]

    class SIZE(C.Structure):
        _fields_ = [('cx', W.LONG), ('cy', W.LONG)]

    class TEXTMETRICW(C.Structure):
        _fields_ = [(k, W.LONG) for k in ['height', 'ascent', 'descent', 'internalLeading', 'externalLeading', 'averageWidth', 'maximumWidth', 'weight', 'overhang', 'digitizedAspectX', 'digitizedAspectY']] + [(k, W.WCHAR) for k in ['firstChar', 'lastChar', 'defaultChar', 'breakChar']] + [(k, W.BYTE) for k in ['italic', 'underlined', 'struckOut', 'pitchAndFamily', 'charSet']]

    if C.sizeof(LOGFONTW) != 92 or C.sizeof(BITMAPINFOHEADER) != 40 or C.sizeof(TEXTMETRICW) != 60:
        raise RuntimeError('Unexpected Windows structure layout')

    def bind(name, result, arguments):
        fn = getattr(gdi, name)
        fn.restype, fn.argtypes = result, arguments
        return fn
    dc_create = bind('CreateCompatibleDC', W.HDC, [W.HDC])
    dib_create = bind('CreateDIBSection', W.HBITMAP, [W.HDC, C.c_void_p, W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD])
    font_create = bind('CreateFontIndirectW', W.HFONT, [C.POINTER(LOGFONTW)])
    select = bind('SelectObject', W.HANDLE, [W.HDC, W.HANDLE])
    delete = bind('DeleteObject', W.BOOL, [W.HANDLE])
    delete_dc = bind('DeleteDC', W.BOOL, [W.HDC])
    text_color = bind('SetTextColor', W.DWORD, [W.HDC, W.DWORD])
    bk_color = bind('SetBkColor', W.DWORD, [W.HDC, W.DWORD])
    face_get = bind('GetTextFaceW', C.c_int, [W.HDC, C.c_int, W.LPWSTR])
    metrics_get = bind('GetTextMetricsW', W.BOOL, [W.HDC, C.POINTER(TEXTMETRICW)])
    abc_get = bind('GetCharABCWidthsFloatW', W.BOOL, [W.HDC, W.UINT, W.UINT, C.POINTER(ABCFLOAT)])
    extent_get = bind('GetTextExtentPoint32W', W.BOOL, [W.HDC, W.LPCWSTR, C.c_int, C.POINTER(SIZE)])
    text_out = bind('TextOutW', W.BOOL, [W.HDC, C.c_int, C.c_int, W.LPCWSTR, C.c_int])
    font_data = bind('GetFontData', W.DWORD, [W.HDC, W.DWORD, W.DWORD, C.c_void_p, W.DWORD])
    flush = bind('GdiFlush', W.BOOL, [])
    caps = bind('GetDeviceCaps', C.c_int, [W.HDC, C.c_int])

    dc = dc_create(None)
    if not dc:
        raise C.WinError(C.get_last_error())
    font = bitmap = old_font = old_bitmap = None
    try:
        header = BITMAPINFOHEADER()
        header.biSize, header.biWidth, header.biHeight = 40, 512, -512
        header.biPlanes, header.biBitCount = 1, 32
        bits = C.c_void_p()
        bitmap = dib_create(dc, C.byref(header), 0, C.byref(bits), None, 0)
        if not bitmap or not bits.value:
            raise C.WinError(C.get_last_error())
        old_bitmap = select(dc, bitmap)
        lf = LOGFONTW()
        lf.lfHeight, lf.lfWeight, lf.lfCharSet = height, 400, 162
        lf.lfQuality, lf.lfFaceName = 4, 'Tahoma'
        font = font_create(C.byref(lf))
        if not font:
            raise C.WinError(C.get_last_error())
        old_font = select(dc, font)
        text_color(dc, 0xffffff)
        bk_color(dc, 0)
        actual_face = C.create_unicode_buffer(64)
        actual = TEXTMETRICW()
        if not face_get(dc, 64, actual_face) or not metrics_get(dc, C.byref(actual)):
            raise C.WinError(C.get_last_error())
        if actual_face.value.casefold() != 'tahoma' or actual.weight != 400 or actual.italic:
            raise RuntimeError('GDI substituted the requested normal Tahoma face')
        length = font_data(dc, 0, 0, None, 0)
        if length == 0xffffffff or length <= 0 or length > 16 * 1024 * 1024:
            raise RuntimeError('Could not identify the selected TrueType font')
        font_bytes = C.create_string_buffer(length)
        if font_data(dc, 0, 0, font_bytes, length) != length:
            raise RuntimeError('Could not hash the selected TrueType font')
        font_hash = hashlib.sha256(font_bytes.raw).hexdigest()
        chars = character_set()
        atlas_width, cell = 512, 32
        atlas_height = math.ceil(len(chars) / 16) * cell
        atlas = bytearray(atlas_width * atlas_height * 4)
        glyphs = []
        for i, char in enumerate(chars):
            abc, size = ABCFLOAT(), SIZE()
            if not abc_get(dc, ord(char), ord(char), C.byref(abc)) or not extent_get(dc, char, 1, C.byref(size)):
                raise RuntimeError('GDI could not measure U+%04X' % ord(char))
            width, advance = engine_metrics(abc.a, abc.b, abc.c)
            if not 0 < width <= cell or not 0 < size.cy <= cell or advance < 0:
                raise RuntimeError('Unexpected glyph dimensions')
            C.memset(bits, 0, 512 * 512 * 4)
            if not text_out(dc, 0, 0, char, 1):
                raise C.WinError(C.get_last_error())
            # GDI batches DIB drawing; synchronize before reading the memory.
            if not flush():
                raise C.WinError(C.get_last_error())
            raw = C.string_at(bits, 512 * size.cy * 4)
            x, y = i % 16 * cell, i // 16 * cell
            ink = 0
            for gy in range(size.cy):
                for gx in range(width):
                    if raw[(gy * 512 + gx) * 4] != 0:
                        j = ((y + gy) * atlas_width + x + gx) * 4
                        atlas[j:j + 4] = b'\xff\xff\xff\xff'
                        ink += 1
            if char in 'Aa1Çğ' and not ink:
                raise RuntimeError('GDI returned an empty required glyph: ' + char)
            glyphs.append({'code': ord(char), 'x': x, 'y': y, 'width': width, 'height': size.cy, 'advance': advance, 'abc': [abc.a, abc.b, abc.c]})
        png = png_rgba(atlas_width, atlas_height, atlas)
        win = sys.getwindowsversion()
        metadata = {'nativeWindowsGdi': True, 'wine': False, 'windows': {'major': win.major, 'minor': win.minor, 'build': win.build}, 'pythonBits': C.sizeof(C.c_void_p) * 8, 'requested': {'face': 'Tahoma', 'lfHeight': height, 'lfWeight': 400, 'lfItalic': 0, 'lfCharSet': 162, 'lfQuality': 4}, 'actual': {'face': actual_face.value, 'weight': actual.weight, 'height': actual.height, 'ascent': actual.ascent, 'descent': actual.descent, 'internalLeading': actual.internalLeading, 'charSet': actual.charSet, 'dpi': caps(dc, 90)}, 'fontDataSha256': font_hash, 'glyphConversion': 'DIB blue byte != 0 -> opaque white; no outline; per-glyph ceil(A+B+C)', 'sourceAlgorithm': 'GrpFontTexture.cpp at40e2d9fef3bed9fa56a113001ae678efb72e06d3'}
        return {'schema': 'mt2-chat-gdi-v1', 'provenance': metadata, 'atlas': {'width': atlas_width, 'height': atlas_height, 'sha256': hashlib.sha256(png).hexdigest(), 'pngBase64': base64.b64encode(png).decode('ascii')}, 'glyphs': glyphs}, png
    finally:
        if old_font:
            select(dc, old_font)
        if old_bitmap:
            select(dc, old_bitmap)
        if font:
            delete(font)
        if bitmap:
            delete(bitmap)
        delete_dc(dc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out'))
    parser.add_argument('--sizes', default='12', help='Comma-separated original locale heights: 9,12,14')
    args = parser.parse_args()
    try:
        sizes = [int(s) for s in args.sizes.split(',')]
        if not sizes or len(sizes) != len(set(sizes)) or any(s not in (9, 12, 14) for s in sizes):
            raise ValueError('Use unique heights from 9,12,14')
        outputs = [(size, *bake(size)) for size in sizes]
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)
    for size, data, png in outputs:
        (args.output / f'tahoma{size}-gdi.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        (args.output / f'tahoma{size}-gdi.png').write_bytes(png)
        print(json.dumps({'face': data['provenance']['actual'], 'fontDataSha256': data['provenance']['fontDataSha256'], 'glyphCount': len(data['glyphs']), 'atlasSha256': data['atlas']['sha256']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
