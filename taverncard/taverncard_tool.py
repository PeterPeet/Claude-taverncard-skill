#!/usr/bin/env python3
"""
taverncard_tool.py — PNG/JSON helper for TavernCards (V1 & V2)
Bundled with the taverncard Claude skill. Requires: pip install Pillow
Commands: info, extract, embed, swap-image, convert

Examples
--------
# 1) Inspect a file
python taverncard_tool.py info <character-card>.png

# 2) Extract JSON from a card PNG
python taverncard_tool.py extract <character-card>.png -o <character-card>.json

# 3) Embed JSON V2 into a PNG (with new background image)
python taverncard_tool.py embed card.json -o card_v2.png --bg cover.png --size 512x512 --wrap v2

# 4) Convert a V1 JSON to V2 JSON
python taverncard_tool.py convert card_v1.json -o card_v2.json --to v2 --format json

# 5) Swap the image in an existing card PNG (preserve JSON)
python taverncard_tool.py swap-image --card-png <existing-card>.png --image-png <new-art>.png -o <output>.png

# 6) Convert a card PNG to a V1 PNG (rewrap JSON and re-embed)
python taverncard_tool.py convert card.png -o card_v1.png --to v1 --format png --plain

Use -? or --help for full help.
"""
import argparse, sys, os, platform, json, base64, re
from typing import Optional, Tuple, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

PNG_SIG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])  # \x89PNG\r\n\x1a\n

# --------------- Utilities ---------------

def _find_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """Return a TrueType font at *size* pt, searching common paths across OSes."""
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
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",        # Ubuntu/Debian
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",                    # Arch
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",      # Fedora
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",                 # Fedora (alt)
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Ubuntu alt
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def is_png(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            sig = f.read(8)
        return sig == PNG_SIG
    except Exception:
        return False

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ascii_escape_json(obj: Dict[str, Any]) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return re.sub(r"[\\u0080-\\uFFFF]", lambda m: "\\\\u%04x" % ord(m.group(0)), s)

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
    v1_keys = {"name","description","personality","scenario","first_mes","mes_example"}
    if isinstance(obj, dict) and v1_keys.issubset(set(obj.keys())):
        return "V1"
    return "UNKNOWN"

# --------------- PNG metadata I/O ---------------

def extract_text_chunks(img: Image.Image) -> Dict[str, str]:
    chunks = {}
    if hasattr(img, "text") and isinstance(img.text, dict):
        for k, v in img.text.items():
            if isinstance(v, str):
                chunks[k] = v
    for k, v in img.info.items():
        if isinstance(v, str) and k not in chunks:
            chunks[k] = v
    return chunks

def extract_card_from_png(path: str, keys: Optional[List[str]] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, str], Optional[str]]:
    if keys is None:
        keys = ["chara", "chara_card_v2", "ai_chara"]
    try:
        img = Image.open(path)
    except Exception as e:
        raise ValueError(f"Cannot open PNG '{path}': {e}") from e
    texts = extract_text_chunks(img)
    for key in keys:
        if key in texts:
            raw = texts[key]
            candidate = raw.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                try:
                    return json.loads(candidate), texts, key
                except Exception:
                    pass
            try:
                decoded = base64.b64decode(candidate, validate=True).decode("utf-8")
                return json.loads(decoded), texts, key
            except Exception:
                pass
    return None, texts, None

def build_png_with_card(out_path: str,
                        json_obj: Dict[str, Any],
                        key: str = "chara",
                        encoding: str = "base64",
                        hints: bool = True,
                        bg_path: Optional[str] = None,
                        size: str = "512x512",
                        title: Optional[str] = None) -> None:
    if bg_path:
        try:
            base = Image.open(bg_path).convert("RGBA")
        except Exception as e:
            raise ValueError(f"Cannot open background image '{bg_path}': {e}") from e
        m = re.match(r"(\\d+)x(\\d+)", size)
        if m:
            W, H = int(m.group(1)), int(m.group(2))
        else:
            W, H = base.size
        img = Image.new("RGBA", (W, H), (26,26,32,255))
        base = base.resize((W, H), Image.LANCZOS)
        img.paste(base, (0,0))
    else:
        m = re.match(r"(\\d+)x(\\d+)", size)
        if m:
            W, H = int(m.group(1)), int(m.group(2))
        else:
            W, H = 512, 512
        img = Image.new("RGBA", (W, H), (26,26,32,255))
        draw = ImageDraw.Draw(img)
        font = _find_font(24)
        text = title or json_obj.get("data", {}).get("name") or json_obj.get("name", "Character")
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, (H - th) // 2), text, fill=(235, 235, 235, 255), font=font)

    if encoding == "base64":
        payload = base64.b64encode(json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")
    elif encoding == "plain":
        payload = ascii_escape_json(json_obj)
    else:
        raise ValueError("encoding must be 'base64' or 'plain'")

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text(key, payload)
    if hints and encoding == "base64":
        spec = "chara_card_v2" if json_obj.get("spec") == "chara_card_v2" else ""
        pnginfo.add_text("chara_encoding", "base64")
        if spec:
            pnginfo.add_text("chara_spec", spec)

    img.save(out_path, "PNG", pnginfo=pnginfo, optimize=False)

# --------------- Commands ---------------

def cmd_info(args):
    if is_png(args.input):
        try:
            card, chunks, key = extract_card_from_png(args.input)
        except Exception as e:
            print(f"[ERROR] Could not read PNG: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[INFO] File: {args.input}")
        print(f"  Type: PNG")
        print(f"  Text keys: {list(chunks.keys())}")
        print(f"  Card detected under: {key!r}" if key else "  Card detected under: None")
        if card:
            kind = detect_card_obj(card)
            print(f"  Card kind: {kind}")
            name = card.get("data", {}).get("name") if kind=='V2' else card.get("name")
            print(f"  Name: {name}")
        else:
            print("  No Tavern card JSON detected.")
    else:
        try:
            obj = load_json(args.input)
            kind = detect_card_obj(obj)
            print(f"[INFO] File: {args.input}")
            print(f"  Type: JSON")
            print(f"  Detected kind: {kind}")
            name = obj.get("data", {}).get("name") if kind=='V2' else obj.get("name")
            print(f"  Name: {name}")
        except Exception as e:
            print(f"[ERROR] Could not read file: {e}", file=sys.stderr)
            sys.exit(1)

def cmd_extract(args):
    if not is_png(args.input):
        print("[ERROR] extract expects a PNG input.", file=sys.stderr)
        sys.exit(1)
    card, chunks, key = extract_card_from_png(args.input, keys=args.keys or None)
    if not card:
        print("[ERROR] No Tavern card JSON found in PNG.", file=sys.stderr)
        sys.exit(2)
    if args.target == "v1" and detect_card_obj(card) == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.target == "v2" and detect_card_obj(card) == "V1":
        card = wrap_v1_to_v2(card)
    save_json(args.out, card)
    print(f"[OK] Extracted card → {args.out} (from key {key})")

def cmd_embed(args):
    if is_png(args.input):
        card, _, _ = extract_card_from_png(args.input)
        if not card:
            print("[ERROR] PNG input has no Tavern card JSON; provide a JSON file or use 'swap-image'.", file=sys.stderr)
            sys.exit(2)
    else:
        try:
            card = load_json(args.input)
        except Exception as e:
            print(f"[ERROR] Cannot read JSON '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)

    kind = detect_card_obj(card)
    if args.wrap == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)
    elif args.wrap == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)

    encoding = "base64" if args.base64 else "plain"
    build_png_with_card(out_path=args.out, json_obj=card, key=args.key, encoding=encoding,
                        hints=args.hints, bg_path=args.bg, size=args.size, title=args.title)
    print(f"[OK] Embedded → {args.out}  ({detect_card_obj(card)} in tEXt[{args.key}] / {encoding})")

def cmd_swap_image(args):
    if not is_png(args.card_png):
        print("[ERROR] --card-png must be a TavernCard PNG", file=sys.stderr)
        sys.exit(1)
    card, _, key_used = extract_card_from_png(args.card_png)
    if not card:
        print("[ERROR] No card JSON found in --card-png", file=sys.stderr)
        sys.exit(2)

    encoding = "base64" if args.base64 else "plain"
    build_png_with_card(out_path=args.out, json_obj=card, key=args.key or key_used or "chara",
                        encoding=encoding, hints=args.hints, bg_path=args.image_png, size=args.size, title=args.title)
    print(f"[OK] Swapped image, preserved JSON → {args.out}")

def cmd_convert(args):
    if is_png(args.input):
        card, _, _ = extract_card_from_png(args.input)
        if not card:
            print("[ERROR] PNG input has no Tavern card JSON.", file=sys.stderr)
            sys.exit(2)
    else:
        try:
            card = load_json(args.input)
        except Exception as e:
            print(f"[ERROR] Cannot read JSON '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)

    kind = detect_card_obj(card)
    if args.to == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.to == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)

    if args.format == "json":
        save_json(args.out, card)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} JSON)")
    else:
        encoding = "base64" if args.base64 else "plain"
        build_png_with_card(out_path=args.out, json_obj=card, key=args.key, encoding=encoding,
                            hints=args.hints, bg_path=args.bg, size=args.size, title=args.title)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} in PNG)")

# --------------- CLI ---------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="taverncard_tool.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Tavern Card helper toolkit (PNG V1/V2 & JSON V1/V2)\\n"
            "- Read PNG cards, extract JSON\\n"
            "- Embed JSON into PNG (tEXt chunk)\\n"
            "- Swap/replace image in existing card PNG\\n"
            "- Convert V1<->V2, output JSON or PNG\\n\\n"
            "Default PNG embedding uses base64(JSON) in tEXt['chara'] to match lite.koboldai."
        )
    )
    p.add_argument("-?", action="help", help="Show this help message and exit")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("info", help="Print info about a PNG or JSON file")
    sp.add_argument("input", help="Path to PNG or JSON")
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("extract", help="Extract card JSON from a PNG")
    sp.add_argument("input", help="Input PNG path")
    sp.add_argument("-o","--out", required=True, help="Output JSON path")
    sp.add_argument("--keys", nargs="*", help="Keys to search (default: chara, chara_card_v2, ai_chara)")
    sp.add_argument("--target", choices=["v1","v2"], default=None, help="Convert extracted card to V1 or V2")
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser("embed", help="Embed JSON/PNG card data into a PNG (optionally with new background)")
    sp.add_argument("input", help="Input JSON or PNG (if PNG, JSON is extracted)")
    sp.add_argument("-o","--out", required=True, help="Output PNG path")
    sp.add_argument("--bg", help="Background image PNG/JPG to use (non-card image)")
    sp.add_argument("--size", default="512x512", help="Canvas size, e.g., 512x512 (default)")
    sp.add_argument("--title", help="Optional text overlay if no bg image")
    sp.add_argument("--key", default="chara", help="PNG text key (default: chara)")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write hint keys (chara_encoding/spec)")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Do not write hint keys")
    sp.add_argument("--wrap", choices=["v1","v2"], help="Wrap/unwrap: force output JSON shape before embedding")
    sp.set_defaults(func=cmd_embed)

    sp = sub.add_parser("swap-image", help="Replace image of a TavernCard PNG while preserving its JSON")
    sp.add_argument("--card-png", required=True, help="Input TavernCard PNG (source of JSON)")
    sp.add_argument("--image-png", required=True, help="Non-card PNG/JPG to use as new image")
    sp.add_argument("-o","--out", required=True, help="Output PNG path")
    sp.add_argument("--size", default="512x512", help="Canvas size, e.g., 512x512")
    sp.add_argument("--title", help="Optional overlay title text")
    sp.add_argument("--key", help="PNG text key to use (default: keep source key or 'chara')")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write hint keys")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Do not write hint keys")
    sp.set_defaults(func=cmd_swap_image)

    sp = sub.add_parser("convert", help="Convert between V1/V2 and output as JSON or PNG")
    sp.add_argument("input", help="Input JSON or PNG")
    sp.add_argument("-o","--out", required=True, help="Output file path")
    sp.add_argument("--to", choices=["v1","v2"], required=True, help="Target spec version for card data")
    sp.add_argument("--format", choices=["json","png"], default="json", help="Output format (default: json)")
    sp.add_argument("--bg", help="Background image if output is PNG")
    sp.add_argument("--size", default="512x512", help="Canvas size for PNG")
    sp.add_argument("--title", help="Overlay title for PNG if no bg")
    sp.add_argument("--key", default="chara", help="PNG text key (PNG output)")
    sp.add_argument("--base64", action="store_true", default=True, help="Embed JSON as base64 (default)")
    sp.add_argument("--plain", dest="base64", action="store_false", help="Embed JSON as plain ASCII-escaped")
    sp.add_argument("--hints", action="store_true", default=True, help="Write hint keys")
    sp.add_argument("--no-hints", dest="hints", action="store_false", help="Do not write hint keys")
    sp.set_defaults(func=cmd_convert)

    return p

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
