#!/usr/bin/env python3
"""
taverncard_tool.py — PNG / JPEG / WebP JSON helper for TavernCards (V1 & V2)
Bundled with the taverncard Claude skill.
Requires: pip install Pillow

Supported input image formats (detected by MAGIC BYTES, not file extension):
  • PNG  — card JSON in tEXt chunk keyed "chara" / "chara_card_v2" / "ai_chara"
  • JPEG — card JSON in EXIF UserComment (tag 0x9286)
  • WebP — card JSON in EXIF UserComment (tag 0x9286), mirrors KoboldAI Lite logic

A file named .png that is actually JPEG or WebP is handled correctly.

Commands: info, extract, embed, swap-image, convert

Examples
--------
# 1) Inspect any card image (PNG / JPEG / WebP) or JSON
python taverncard_tool.py info <card>.png
python taverncard_tool.py info <card>.jpg

# 2) Extract JSON from any card image
python taverncard_tool.py extract <card>.png -o card.json
python taverncard_tool.py extract <card>.jpg -o card.json

# 3) Embed JSON into a PNG (with artwork — accepts PNG, JPEG, or WebP art)
python taverncard_tool.py embed card.json -o card_v2.png --bg cover.jpg --size 512x512 --wrap v2

# 4) Convert a V1 JSON to V2 JSON
python taverncard_tool.py convert card_v1.json -o card_v2.json --to v2 --format json

# 5) Swap the image in a card (source card may be PNG, JPEG, or WebP)
python taverncard_tool.py swap-image --card <existing-card>.png --image <new-art>.jpg -o output.png

# 6) Convert a card image to V1 PNG
python taverncard_tool.py convert card.jpg -o card_v1.png --to v1 --format png

Use -? or --help for full help.
"""
import argparse, sys, os, platform, json, base64, re, struct
from typing import Optional, Tuple, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

# ─── Magic byte signatures ────────────────────────────────────────────────────

PNG_SIG   = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])  # \x89PNG\r\n\x1a\n
JPEG_SIG  = bytes([0xFF, 0xD8, 0xFF])                                   # JPEG SOI + first marker
WEBP_RIFF = b'RIFF'
WEBP_WEBP = b'WEBP'

# ─── Utilities ────────────────────────────────────────────────────────────────

def _find_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """Return a TrueType font at *size* pt, searching common system paths."""
    system = platform.system()
    if system == "Darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
    elif system == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates = [
            os.path.join(windir, "Fonts", "arial.ttf"),
            os.path.join(windir, "Fonts", "calibri.ttf"),
            os.path.join(windir, "Fonts", "segoeui.ttf"),
        ]
    else:  # Linux: Ubuntu, Arch, Fedora and others
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",         # Ubuntu/Debian
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",                     # Arch
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",       # Fedora
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",                  # Fedora (alt)
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Ubuntu alt
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def detect_image_type(path: str) -> str:
    """Detect actual image format by reading the first 12 bytes (magic bytes).

    Ignores file extension entirely — a file named .png that is really a JPEG
    or WebP is reported correctly.

    Returns: 'PNG', 'JPEG', 'WEBP', or 'UNKNOWN'.
    Raises:  ValueError if the file cannot be opened/read.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(12)
    except OSError as e:
        raise ValueError(f"Cannot read '{path}': {e}") from e
    if header[:8] == PNG_SIG:
        return "PNG"
    if header[:3] == JPEG_SIG:
        return "JPEG"
    if len(header) >= 12 and header[:4] == WEBP_RIFF and header[8:12] == WEBP_WEBP:
        return "WEBP"
    return "UNKNOWN"


def is_png(path: str) -> bool:
    """Return True if path has a PNG magic signature. Kept for backward compatibility."""
    try:
        return detect_image_type(path) == "PNG"
    except Exception:
        return False


def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Cannot parse JSON '{path}': {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read '{path}': {e}") from e


def save_json(path: str, data: Dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise ValueError(f"Cannot write '{path}': {e}") from e


def ascii_escape_json(obj: Dict[str, Any]) -> str:
    """Serialize obj to JSON with all non-ASCII characters escaped as \\uXXXX."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # Match any character outside the ASCII range and replace with \uXXXX
    return re.sub(r"[^\x00-\x7f]", lambda m: "\\u%04x" % ord(m.group(0)), s)


def wrap_v1_to_v2(v1: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": v1.get("name", ""),
            "description": v1.get("description", ""),
            "personality": v1.get("personality", ""),
            "scenario": v1.get("scenario", ""),
            "first_mes": v1.get("first_mes", ""),
            "mes_example": v1.get("mes_example", ""),
            "creator_notes": v1.get("creator_notes", v1.get("notes", "")),
            "system_prompt": v1.get("system_prompt", "{{original}}"),
            "post_history_instructions": v1.get("post_history_instructions", "{{original}}"),
            "alternate_greetings": v1.get("alternate_greetings", []),
            "character_book": v1.get("character_book"),
            "tags": v1.get("tags", []),
            "creator": v1.get("creator", ""),
            "character_version": v1.get("character_version", "1.0.0"),
            "extensions": v1.get("extensions", {}),
        }
    }


def unwrap_v2_to_v1(v2: Dict[str, Any]) -> Dict[str, Any]:
    d = v2.get("data", {})
    return {
        "name": d.get("name", ""),
        "description": d.get("description", ""),
        "personality": d.get("personality", ""),
        "scenario": d.get("scenario", ""),
        "first_mes": d.get("first_mes", ""),
        "mes_example": d.get("mes_example", ""),
        "character_book": d.get("character_book"),
        "tags": d.get("tags", []),
        "creator": d.get("creator", ""),
        "character_version": d.get("character_version", "1.0.0"),
        "creator_notes": d.get("creator_notes", ""),
        "system_prompt": d.get("system_prompt", ""),
        "post_history_instructions": d.get("post_history_instructions", ""),
        "alternate_greetings": d.get("alternate_greetings", []),
        "extensions": d.get("extensions", {}),
    }


def detect_card_obj(obj: Dict[str, Any]) -> str:
    if isinstance(obj, dict) and obj.get("spec") == "chara_card_v2" and "data" in obj:
        return "V2"
    v1_keys = {"name", "description", "personality", "scenario", "first_mes", "mes_example"}
    if isinstance(obj, dict) and v1_keys.issubset(set(obj.keys())):
        return "V1"
    return "UNKNOWN"


# ─── PNG metadata I/O ─────────────────────────────────────────────────────────

def extract_text_chunks(img: Image.Image) -> Dict[str, str]:
    chunks: Dict[str, str] = {}
    if hasattr(img, "text") and isinstance(img.text, dict):
        for k, v in img.text.items():
            if isinstance(v, str):
                chunks[k] = v
    for k, v in img.info.items():
        if isinstance(v, str) and k not in chunks:
            chunks[k] = v
    return chunks


def extract_card_from_png(
    path: str, keys: Optional[List[str]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str], Optional[str]]:
    """Extract TavernCard JSON from a PNG tEXt chunk.

    Returns (card_dict, all_text_chunks, key_found).
    Raises ValueError if the file cannot be opened as a PNG.
    """
    if keys is None:
        keys = ["chara", "chara_card_v2", "ai_chara"]
    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(f"Cannot open PNG '{path}': {e}") from e
    texts = extract_text_chunks(img)
    for key in keys:
        if key in texts:
            raw = texts[key].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), texts, key
                except Exception:
                    pass
            try:
                decoded = base64.b64decode(raw, validate=True).decode("utf-8")
                return json.loads(decoded), texts, key
            except Exception:
                pass
    return None, texts, None


def build_png_with_card(
    out_path: str,
    json_obj: Dict[str, Any],
    key: str = "chara",
    encoding: str = "base64",
    hints: bool = True,
    bg_path: Optional[str] = None,
    size: str = "512x512",
    title: Optional[str] = None,
) -> None:
    """Embed *json_obj* into a PNG file.  *bg_path* accepts PNG, JPEG, or WebP."""
    if bg_path:
        try:
            base = Image.open(bg_path).convert("RGBA")
        except Exception as e:
            raise ValueError(
                f"Cannot open background image '{bg_path}': {e}\n"
                f"  Accepted formats: PNG, JPEG, WebP (detected by content, not extension)."
            ) from e
        m = re.match(r"(\d+)x(\d+)", size)
        if m:
            W, H = int(m.group(1)), int(m.group(2))
        else:
            W, H = base.size
        img = Image.new("RGBA", (W, H), (26, 26, 32, 255))
        img.paste(base.resize((W, H), Image.LANCZOS), (0, 0))
    else:
        m = re.match(r"(\d+)x(\d+)", size)
        W, H = (int(m.group(1)), int(m.group(2))) if m else (512, 512)
        img = Image.new("RGBA", (W, H), (26, 26, 32, 255))
        draw = ImageDraw.Draw(img)
        font = _find_font(24)
        text = title or json_obj.get("data", {}).get("name") or json_obj.get("name", "Character")
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, (H - th) // 2), text, fill=(235, 235, 235, 255), font=font)

    if encoding == "base64":
        payload = base64.b64encode(
            json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
    elif encoding == "plain":
        payload = ascii_escape_json(json_obj)
    else:
        raise ValueError(f"encoding must be 'base64' or 'plain', got: {encoding!r}")

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text(key, payload)
    if hints and encoding == "base64":
        pnginfo.add_text("chara_encoding", "base64")
        if json_obj.get("spec") == "chara_card_v2":
            pnginfo.add_text("chara_spec", "chara_card_v2")

    try:
        img.save(out_path, "PNG", pnginfo=pnginfo, optimize=False)
    except Exception as e:
        raise ValueError(f"Cannot write PNG '{out_path}': {e}") from e


# ─── JPEG / WebP EXIF I/O ─────────────────────────────────────────────────────

def _decode_exif_usercomment_bytes(raw: bytes) -> Optional[str]:
    """Decode an EXIF UserComment value.

    The first 8 bytes are a charset identifier ('ASCII\\0\\0\\0', 'UNICODE\\0', etc.).
    The remainder is the actual text content.
    """
    if not raw:
        return None
    if len(raw) > 8:
        charset = raw[:8].rstrip(b"\x00").lower()
        content = raw[8:]
        if charset in (b"unicode", b"utf-16"):
            try:
                return content.decode("utf-16", errors="replace").strip("\x00").strip()
            except Exception:
                pass
        # ASCII, UNDEFINED, or empty charset → treat as UTF-8
        try:
            return content.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            pass
    # Short / no prefix — decode whole value
    try:
        return raw.decode("utf-8", errors="replace").strip("\x00").strip()
    except Exception:
        return None


def _read_exif_usercomment_pillow(img: Image.Image) -> Optional[str]:
    """Use Pillow's EXIF API to read UserComment (tag 0x9286).

    Tries the modern getexif() path first, then the legacy _getexif() path for
    older Pillow / JPEG-only builds.
    """
    raw = None
    try:
        exif = img.getexif()
        # Preferred: read from ExifIFD sub-IFD (tag 0x8769)
        try:
            exif_ifd = exif.get_ifd(0x8769)
            raw = exif_ifd.get(0x9286)
        except Exception:
            pass
        # Fallback: direct lookup on the root IFD
        if raw is None:
            raw = exif.get(0x9286)
    except Exception:
        pass

    # Legacy API (JPEG-only, Pillow < 6.0 compatibility)
    if raw is None:
        try:
            d = img._getexif()  # type: ignore[attr-defined]
            if d:
                raw = d.get(0x9286)
        except Exception:
            pass

    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.strip("\x00").strip()
    if isinstance(raw, (bytes, bytearray)):
        return _decode_exif_usercomment_bytes(bytes(raw))
    return str(raw).strip()


def _extract_webp_usercomment_raw(data: bytes) -> Optional[str]:
    """Scan raw WebP bytes for EXIF UserComment.

    Mirrors the getTavernExifJSON() logic from KoboldAI Lite (index.html):
    brute-force scan for the EXIF RIFF chunk + UserComment IFD entry + ASCII prefix.
    Used as a fallback when Pillow's EXIF API cannot read the WebP EXIF chunk.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None

    datlen = len(data)
    offset = 0

    # Outer scan: find the EXIF RIFF chunk ("EXIF" FourCC) with "Exif" data signature
    while offset < datlen - 12:
        offset += 1
        # data[offset..+3] = EXIF FourCC, data[offset+8..+11] = "Exif" in the chunk payload
        if (
            data[offset : offset + 4] == b"EXIF"
            and data[offset + 8 : offset + 12] == b"Exif"
        ):
            offset += 12  # move past "EXIF<4-byte-size>Exif\x00\x00"

            found_size = False
            datasize = 0

            # Inner scan: find UserComment tag (0x9286) then its ASCII-prefixed value
            while offset < datlen - 12:
                offset += 1

                if not found_size:
                    # Little-endian tag bytes for 0x9286
                    if data[offset] == 0x86 and data[offset + 1] == 0x92:
                        found_size = True
                        datasize = (
                            data[offset + 4]
                            | (data[offset + 5] << 8)
                            | (data[offset + 6] << 16)
                            | (data[offset + 7] << 24)
                        ) - 8
                    # Big-endian tag bytes for 0x9286
                    elif data[offset] == 0x92 and data[offset + 1] == 0x86:
                        found_size = True
                        datasize = (
                            data[offset + 7]
                            | (data[offset + 6] << 8)
                            | (data[offset + 5] << 16)
                            | (data[offset + 4] << 24)
                        ) - 8

                # ASCII\0\0\0 charset prefix of the UserComment value
                if (
                    found_size
                    and data[offset : offset + 5] == b"ASCII"
                    and data[offset + 5 : offset + 8] == b"\x00\x00\x00"
                ):
                    idx = offset + 8
                    end = min(idx + max(datasize, 0), datlen)
                    content = data[idx:end].decode("utf-8", errors="replace").strip("\x00").strip()
                    return content if content else None
            break

    return None


def _tiff_find_usercomment(tiff: bytes) -> Optional[str]:
    """Parse TIFF/EXIF bytes and return the UserComment (tag 0x9286) value string.

    Walks IFD0 → ExifIFD → UserComment, respecting byte order (II / MM).
    Returns None if the tag is not found or data is truncated.
    """
    if len(tiff) < 8:
        return None
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return None

    try:
        ifd0_off = struct.unpack_from(endian + "I", tiff, 4)[0]

        # Walk IFD0 looking for ExifIFD pointer (tag 0x8769)
        n = struct.unpack_from(endian + "H", tiff, ifd0_off)[0]
        exif_ifd_off: Optional[int] = None
        for i in range(n):
            entry_off = ifd0_off + 2 + i * 12
            if entry_off + 12 > len(tiff):
                break
            tag = struct.unpack_from(endian + "H", tiff, entry_off)[0]
            if tag == 0x8769:  # ExifIFD
                exif_ifd_off = struct.unpack_from(endian + "I", tiff, entry_off + 8)[0]
                break

        if exif_ifd_off is None:
            return None

        # Walk ExifIFD looking for UserComment (tag 0x9286)
        n = struct.unpack_from(endian + "H", tiff, exif_ifd_off)[0]
        for i in range(n):
            entry_off = exif_ifd_off + 2 + i * 12
            if entry_off + 12 > len(tiff):
                break
            tag = struct.unpack_from(endian + "H", tiff, entry_off)[0]
            if tag == 0x9286:  # UserComment
                count = struct.unpack_from(endian + "I", tiff, entry_off + 4)[0]
                val_off = struct.unpack_from(endian + "I", tiff, entry_off + 8)[0]
                if val_off + count > len(tiff):
                    return None
                return _decode_exif_usercomment_bytes(tiff[val_off : val_off + count])
    except struct.error:
        return None

    return None


def _extract_jpeg_usercomment_raw(data: bytes) -> Optional[str]:
    """Scan JPEG APP1/EXIF segments for UserComment (fallback raw parser).

    Parses JPEG markers sequentially, finds the APP1 segment with EXIF data,
    then delegates to the TIFF parser for the actual tag lookup.
    """
    if len(data) < 3 or data[0:3] != bytes([0xFF, 0xD8, 0xFF]):
        return None

    offset = 2  # After SOI (FF D8)
    while offset < len(data) - 4:
        if data[offset] != 0xFF:
            break
        marker = data[offset + 1]

        # Skip fill bytes (0xFF padding before a marker)
        if marker == 0xFF:
            offset += 1
            continue

        # Standalone markers with no length field
        if marker in (0xD8, 0xD9):  # SOI / EOI
            offset += 2
            continue
        if marker == 0xDA:  # SOS — compressed image data starts, stop scanning
            break

        # Segments with a 2-byte length field (big-endian, includes the 2 bytes)
        if offset + 3 >= len(data):
            break
        try:
            seg_len = struct.unpack_from(">H", data, offset + 2)[0]
        except struct.error:
            break
        seg_end = offset + 2 + seg_len

        if marker == 0xE1:  # APP1
            app1_data = data[offset + 4 : seg_end]
            if app1_data[:6] == b"Exif\x00\x00":
                tiff = app1_data[6:]
                result = _tiff_find_usercomment(tiff)
                if result is not None:
                    return result

        if seg_end <= offset:  # guard against malformed length
            offset += 2
        else:
            offset = seg_end

    return None


def _parse_card_text(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse card JSON from a plain or base64-encoded string.

    Tries direct JSON parse first, then base64 → JSON.
    Returns (card_dict, source_label) or (None, None).
    """
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text), "UserComment"
        except json.JSONDecodeError:
            pass
    # Base64 → JSON (add padding if needed)
    try:
        padded = text + "=" * ((-len(text)) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        return json.loads(decoded), "UserComment[base64]"
    except Exception:
        pass
    return None, None


def extract_card_from_exif(
    path: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Extract TavernCard JSON from a JPEG or WebP file via EXIF UserComment.

    Strategy (in order):
      1. Pillow getexif() API — works for both JPEG and WebP with modern Pillow
      2. Raw WebP RIFF scanner — mirrors KoboldAI Lite reference implementation
      3. Raw JPEG APP1/TIFF parser — standalone EXIF byte-level parser

    Returns (card_dict, key_label) or (None, None) if no card is found.
    Raises ValueError if the file cannot be opened.
    """
    img_type = detect_image_type(path)
    if img_type not in ("JPEG", "WEBP"):
        raise ValueError(
            f"extract_card_from_exif expects JPEG or WebP, got '{img_type}' for '{path}'."
        )

    text: Optional[str] = None

    # ── Method 1: Pillow EXIF API ─────────────────────────────────────────────
    try:
        img = Image.open(path)
        text = _read_exif_usercomment_pillow(img)
    except Exception:
        pass

    # ── Method 2 / 3: Raw binary fallbacks ───────────────────────────────────
    if not text:
        try:
            with open(path, "rb") as fh:
                raw_data = fh.read()
            if img_type == "WEBP":
                text = _extract_webp_usercomment_raw(raw_data)
            else:  # JPEG
                text = _extract_jpeg_usercomment_raw(raw_data)
        except OSError as e:
            raise ValueError(f"Cannot read '{path}': {e}") from e
        except Exception:
            pass

    if not text:
        return None, None

    return _parse_card_text(text)


def extract_card_from_image(
    path: str, keys: Optional[List[str]] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str], Optional[str]]:
    """Auto-detect image format by magic bytes and extract TavernCard JSON.

    Works with PNG, JPEG, and WebP — regardless of the file extension.
    Returns (card_dict, metadata_dict, key_found).
    Raises ValueError for unrecognized formats or read errors.
    """
    img_type = detect_image_type(path)

    if img_type == "PNG":
        return extract_card_from_png(path, keys)

    if img_type in ("JPEG", "WEBP"):
        card, key = extract_card_from_exif(path)
        return card, {}, key

    raise ValueError(
        f"Unrecognized image format for '{path}'.\n"
        f"  Expected: PNG, JPEG, or WebP (checked by magic bytes, not filename).\n"
        f"  The file may be corrupt or use an unsupported format.\n"
        f"  Tip: run 'python3 taverncard_tool.py info \"{path}\"' to inspect."
    )


# ─── Commands ──────────────────────────────────────────────────────────────────

def cmd_info(args):
    try:
        img_type = detect_image_type(args.input)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if img_type == "PNG":
        try:
            card, chunks, key = extract_card_from_png(args.input)
        except Exception as e:
            print(f"[ERROR] Could not read PNG '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[INFO] File : {args.input}")
        print(f"  Detected type : PNG")
        print(f"  Text keys     : {list(chunks.keys())}")
        print(f"  Card key      : {key!r}" if key else "  Card key      : None")
        if card:
            kind = detect_card_obj(card)
            name = card.get("data", {}).get("name") if kind == "V2" else card.get("name")
            print(f"  Card kind     : {kind}")
            print(f"  Name          : {name}")
        else:
            print("  No TavernCard JSON detected in PNG text chunks.")

    elif img_type in ("JPEG", "WEBP"):
        try:
            card, key = extract_card_from_exif(args.input)
        except Exception as e:
            print(f"[ERROR] Could not read {img_type} EXIF data from '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[INFO] File : {args.input}")
        print(f"  Detected type : {img_type}  (by magic bytes — filename may differ)")
        print(f"  Card EXIF key : {key!r}" if key else "  Card EXIF key : None")
        if card:
            kind = detect_card_obj(card)
            name = card.get("data", {}).get("name") if kind == "V2" else card.get("name")
            print(f"  Card kind     : {kind}")
            print(f"  Name          : {name}")
        else:
            print("  No TavernCard JSON detected in EXIF UserComment.")

    else:
        # Attempt JSON
        try:
            obj = load_json(args.input)
        except ValueError as e:
            print(
                f"[ERROR] File is neither a recognized image (PNG/JPEG/WebP) nor valid JSON.\n  {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        kind = detect_card_obj(obj)
        name = obj.get("data", {}).get("name") if kind == "V2" else obj.get("name")
        print(f"[INFO] File : {args.input}")
        print(f"  Detected type : JSON")
        print(f"  Card kind     : {kind}")
        print(f"  Name          : {name}")


def cmd_extract(args):
    try:
        img_type = detect_image_type(args.input)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if img_type not in ("PNG", "JPEG", "WEBP"):
        print(
            f"[ERROR] 'extract' requires an image input (PNG, JPEG, or WebP).\n"
            f"  Got unrecognized format for '{args.input}'.\n"
            f"  Tip: use 'info' to check the actual file type.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        card, _, key = extract_card_from_image(args.input, keys=args.keys or None)
    except Exception as e:
        print(f"[ERROR] Could not read '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    if not card:
        print(
            f"[ERROR] No TavernCard JSON found in {img_type} file '{args.input}'.\n"
            f"  The file may not contain an embedded card.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.target == "v1" and detect_card_obj(card) == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.target == "v2" and detect_card_obj(card) == "V1":
        card = wrap_v1_to_v2(card)

    try:
        save_json(args.out, card)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Extracted card → {args.out}  (from {img_type} / EXIF key: {key})")


def cmd_embed(args):
    try:
        img_type = detect_image_type(args.input)
    except ValueError:
        img_type = "UNKNOWN"

    if img_type in ("PNG", "JPEG", "WEBP"):
        try:
            card, _, _ = extract_card_from_image(args.input)
        except Exception as e:
            print(f"[ERROR] Could not read image '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
        if not card:
            print(
                f"[ERROR] {img_type} input '{args.input}' has no embedded TavernCard JSON.\n"
                f"  Provide a JSON file as input, or use 'swap-image' to replace artwork.",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        try:
            card = load_json(args.input)
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    kind = detect_card_obj(card)
    if args.wrap == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)
    elif args.wrap == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)

    encoding = "base64" if args.base64 else "plain"
    try:
        build_png_with_card(
            out_path=args.out,
            json_obj=card,
            key=args.key,
            encoding=encoding,
            hints=args.hints,
            bg_path=args.bg,
            size=args.size,
            title=args.title,
        )
    except Exception as e:
        print(f"[ERROR] Failed to build output PNG '{args.out}': {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Embedded → {args.out}  ({detect_card_obj(card)} in tEXt[{args.key}] / {encoding})")


def cmd_swap_image(args):
    try:
        img_type = detect_image_type(args.card)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if img_type not in ("PNG", "JPEG", "WEBP"):
        print(
            f"[ERROR] --card must be a TavernCard image (PNG, JPEG, or WebP).\n"
            f"  Got unrecognized format for '{args.card}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        card, _, key_used = extract_card_from_image(args.card)
    except Exception as e:
        print(f"[ERROR] Could not read card image '{args.card}': {e}", file=sys.stderr)
        sys.exit(1)

    if not card:
        print(
            f"[ERROR] No TavernCard JSON found in '{args.card}'.\n"
            f"  The file may not contain an embedded card.",
            file=sys.stderr,
        )
        sys.exit(2)

    encoding = "base64" if args.base64 else "plain"
    try:
        build_png_with_card(
            out_path=args.out,
            json_obj=card,
            key=args.key or key_used or "chara",
            encoding=encoding,
            hints=args.hints,
            bg_path=args.image,
            size=args.size,
            title=args.title,
        )
    except Exception as e:
        print(f"[ERROR] Failed to build output PNG '{args.out}': {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Swapped image, preserved JSON → {args.out}")


def cmd_convert(args):
    try:
        img_type = detect_image_type(args.input)
    except ValueError:
        img_type = "UNKNOWN"

    if img_type in ("PNG", "JPEG", "WEBP"):
        try:
            card, _, _ = extract_card_from_image(args.input)
        except Exception as e:
            print(f"[ERROR] Could not read image '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
        if not card:
            print(
                f"[ERROR] {img_type} input '{args.input}' has no embedded TavernCard JSON.",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        try:
            card = load_json(args.input)
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    kind = detect_card_obj(card)
    if args.to == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.to == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)

    if args.format == "json":
        try:
            save_json(args.out, card)
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} JSON)")
    else:
        encoding = "base64" if args.base64 else "plain"
        try:
            build_png_with_card(
                out_path=args.out,
                json_obj=card,
                key=args.key,
                encoding=encoding,
                hints=args.hints,
                bg_path=args.bg,
                size=args.size,
                title=args.title,
            )
        except Exception as e:
            print(f"[ERROR] Failed to build output PNG '{args.out}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} in PNG)")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="taverncard_tool.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "TavernCard image toolkit (V1/V2, PNG / JPEG / WebP)\n"
            "Image format is detected by MAGIC BYTES — not file extension.\n"
            "A .png file that is actually JPEG or WebP is handled correctly.\n\n"
            "Supported input:  PNG (tEXt chunk), JPEG (EXIF UserComment), WebP (EXIF UserComment)\n"
            "Output images:    always PNG (standard TavernCard container)\n"
            "Output artwork:   --bg / --image accept PNG, JPEG, or WebP"
        ),
    )
    p.add_argument("-?", action="help", help="Show this help message and exit")

    sub = p.add_subparsers(dest="cmd", required=True)

    # ── info ─────────────────────────────────────────────────────────────────
    sp = sub.add_parser("info", help="Print format info and card details for any image or JSON")
    sp.add_argument("input", help="Path to PNG, JPEG, WebP, or JSON file")
    sp.set_defaults(func=cmd_info)

    # ── extract ───────────────────────────────────────────────────────────────
    sp = sub.add_parser("extract", help="Extract card JSON from a PNG, JPEG, or WebP image")
    sp.add_argument("input", help="Input image path (PNG, JPEG, or WebP)")
    sp.add_argument("-o", "--out", required=True, help="Output JSON path")
    sp.add_argument(
        "--keys",
        nargs="*",
        help="PNG text keys to search (default: chara, chara_card_v2, ai_chara). PNG only.",
    )
    sp.add_argument(
        "--target",
        choices=["v1", "v2"],
        default=None,
        help="Convert extracted card to V1 or V2 before saving",
    )
    sp.set_defaults(func=cmd_extract)

    # ── embed ─────────────────────────────────────────────────────────────────
    sp = sub.add_parser(
        "embed",
        help="Embed card JSON into a new PNG (artwork may be PNG, JPEG, or WebP)",
    )
    sp.add_argument("input", help="Input: JSON file, or an image file to re-embed")
    sp.add_argument("-o", "--out", required=True, help="Output PNG path")
    sp.add_argument("--bg", metavar="IMAGE", help="Artwork image: PNG, JPEG, or WebP")
    sp.add_argument("--size", default="512x512", help="Canvas size, e.g. 512x512 (default)")
    sp.add_argument("--title", help="Optional text overlay when no --bg is given")
    sp.add_argument("--key", default="chara", help="PNG tEXt key (default: chara)")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write chara_encoding / chara_spec hint keys")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Omit hint keys")
    sp.add_argument("--wrap", choices=["v1", "v2"], help="Force V1/V2 shape before embedding")
    sp.set_defaults(func=cmd_embed)

    # ── swap-image ────────────────────────────────────────────────────────────
    sp = sub.add_parser(
        "swap-image",
        help="Replace the artwork in a card while keeping its JSON data",
    )
    sp.add_argument(
        "--card-png", "--card",
        dest="card",
        required=True,
        metavar="IMAGE",
        help="Source card image (PNG, JPEG, or WebP — JSON is extracted from here)",
    )
    sp.add_argument(
        "--image-png", "--image",
        dest="image",
        required=True,
        metavar="IMAGE",
        help="New artwork image (PNG, JPEG, or WebP)",
    )
    sp.add_argument("-o", "--out", required=True, help="Output PNG path")
    sp.add_argument("--size", default="512x512", help="Canvas size, e.g. 512x512")
    sp.add_argument("--title", help="Optional overlay title text")
    sp.add_argument("--key", help="PNG tEXt key to use (default: keep source key or 'chara')")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write hint keys")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Omit hint keys")
    sp.set_defaults(func=cmd_swap_image)

    # ── convert ───────────────────────────────────────────────────────────────
    sp = sub.add_parser(
        "convert",
        help="Convert card between V1/V2 and output as JSON or PNG",
    )
    sp.add_argument("input", help="Input: JSON file, or image (PNG, JPEG, WebP)")
    sp.add_argument("-o", "--out", required=True, help="Output file path")
    sp.add_argument("--to", choices=["v1", "v2"], required=True, help="Target spec version")
    sp.add_argument("--format", choices=["json", "png"], default="json", help="Output format (default: json)")
    sp.add_argument("--bg", metavar="IMAGE", help="Artwork image (PNG, JPEG, or WebP) for PNG output")
    sp.add_argument("--size", default="512x512", help="Canvas size for PNG output")
    sp.add_argument("--title", help="Overlay title for PNG output when no --bg")
    sp.add_argument("--key", default="chara", help="PNG tEXt key (PNG output)")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write hint keys")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Omit hint keys")
    sp.set_defaults(func=cmd_convert)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
