---
name: taverncard
description: >
  Use when the user wants to work with TavernCard character cards in V1 or V2
  format. Triggers for: inspecting, validating, creating, editing, or converting
  TavernCard JSON or PNG files; extracting card data from PNG images; embedding
  JSON into PNGs; swapping card artwork; or any question about the TavernCard
  V1/V2 specification. Also triggers for lorebook / character_book work and
  identifying spec compliance issues in cards downloaded from sites like
  CharacterHub, Chub.ai, JanitorAI, or AI Character Editor.
---

# TavernCard Expert

You are an expert on the TavernCard V1 and V2 character card specification.
You can inspect, validate, create, edit, convert, and explain TavernCard JSON
and PNG files. The skill folder includes a bundled Python tool for PNG
operations — see §6 for bootstrap instructions.

---

## 1. Format Detection

**V2** — Has a `spec` / `data` envelope:
```json
{ "spec": "chara_card_v2", "spec_version": "2.0", "data": { … } }
```

**V1** — Flat structure, all fields at root level. No `spec` key. A `metadata`
block (e.g. from AI Character Editor) is NOT part of the spec and does not
indicate V2.

Detection logic:
- `obj.spec === "chara_card_v2"` AND `"data" in obj` → **V2**
- Has `name`, `description`, `personality`, `scenario`, `first_mes`,
  `mes_example` at root → **V1**
- Otherwise → **UNKNOWN / non-compliant**

---

## 2. Field Reference

### V1 Required Fields (all `string`, default `""`)
| Field | Purpose |
|---|---|
| `name` | Character identifier — replaces `{{char}}` / `<BOT>` in prompts |
| `description` | Full character description; injected in every prompt |
| `personality` | **Short** personality summary; injected separately from description |
| `scenario` | Current context / circumstances of the conversation |
| `first_mes` | Opening message (greeting); chatbot MUST send this first |
| `mes_example` | Example dialogues; use `<START>` delimiter between exchanges |

### V2 Additional Fields (all inside `data{}`)
| Field | Default | Purpose |
|---|---|---|
| `spec` | `"chara_card_v2"` | Version marker — MUST be this exact string |
| `spec_version` | `"2.0"` | MUST be `"2.0"` |
| `creator_notes` | `""` | Shown to users; NEVER used in prompts |
| `system_prompt` | `"{{original}}"` | Replaces frontend system prompt; `""` = use frontend default |
| `post_history_instructions` | `"{{original}}"` | Replaces frontend UJB/jailbreak; `""` = use frontend default |
| `alternate_greetings` | `[]` | Additional greeting swipes |
| `character_book` | optional | Embedded lorebook — see §5 |
| `tags` | `[]` | Metadata only; NOT used in prompts |
| `creator` | `""` | Attribution — NOT used in prompts |
| `character_version` | `"1.0.0"` | Version string — NOT used in prompts |
| `extensions` | `{}` | Arbitrary app data; MUST NOT be destroyed on import/export |

### Template Variables (case-insensitive; apply in all text fields)
- `{{char}}` or `<BOT>` → replaced with `name`
- `{{user}}` or `<USER>` → replaced with the app's display name for the user
- `{{original}}` → (system_prompt / post_history_instructions only) replaced
  with the frontend's own setting that would have been used without this card

---

## 3. Validation Checklist

Run through these when inspecting or editing a card:

**Structural (hard errors)**
- [ ] V2 has `spec: "chara_card_v2"` and `spec_version: "2.0"`
- [ ] V2 wraps all fields inside `data{}`
- [ ] All required string fields present and not null/undefined
- [ ] `extensions` is `{}` not absent

**Common quality issues**
- [ ] `personality` is empty → fill with a short trait summary (not a copy of `description`)
- [ ] `system_prompt` is `""` → change to `"{{original}}"` unless intentionally overriding
- [ ] `post_history_instructions` is `""` → change to `"{{original}}"` unless intentional
- [ ] `mes_example` uses `---` separators instead of `<START>` → most frontends accept
  both, but `<START>` is the spec-correct delimiter
- [ ] `mes_example` contains a system prompt (Alpaca-style `### Instruction:`) → misuse;
  move to `system_prompt` or `description`
- [ ] `character_version` is `"1.0"` instead of `"1.0.0"` → cosmetic, safe to update

**Non-spec-compliant sources** (CharacterHub, JanitorAI, AI Character Editor, etc.)
Cards from these sites frequently have: empty `personality`, empty `scenario`,
`metadata` blocks with `version: 1` (not a spec indicator), misused
`mes_example`, and missing `extensions`. Validate carefully.

---

## 4. The `{{original}}` Convention

**Critical rule for `system_prompt` and `post_history_instructions`:**

| Value | Frontend behavior |
|---|---|
| `""` (empty string) | Frontend REPLACES its setting with nothing (silent suppression) |
| `"{{original}}"` | Frontend PASSES THROUGH its own setting unchanged |
| Any other string | Frontend REPLACES its setting with this character's custom text |

**When editing a card** that has `""` for these fields and the creator has NOT
provided custom content: correct to `"{{original}}"`.

Only write custom content into these fields when the user explicitly wants to
override the frontend's behavior for this specific character.

---

## 5. Character Book (Lorebook)

```json
{
  "name": "optional name",
  "description": "optional",
  "scan_depth": 100,
  "token_budget": 2048,
  "recursive_scanning": false,
  "extensions": {},
  "entries": [
    {
      "keys": ["trigger word", "alias"],
      "content": "Text injected into prompt when triggered",
      "extensions": {},
      "enabled": true,
      "insertion_order": 100,
      "case_sensitive": false,
      "name": "Label (not used in prompt)",
      "priority": 10,
      "id": 1,
      "comment": "",
      "selective": false,
      "secondary_keys": [],
      "constant": false,
      "position": "before_char"
    }
  ]
}
```

- `insertion_order`: lower = injected higher in context
- `priority`: lower = discarded first when token budget exceeded
- `position`: `"before_char"` | `"after_char"`
- `constant: true` = always inject (within budget)
- `selective: true` = requires a key from BOTH `keys` AND `secondary_keys`

---

## 6. PNG Tool — Bootstrap & Usage

The skill bundles a Python tool for PNG operations. It is self-contained and
requires only Python 3 + Pillow.

### Step 1 — Locate or bootstrap the tool

The tool should be at: `~/.claude/skills/taverncard/taverncard_tool.py`

Before any PNG operation, verify it exists:
```bash
ls ~/.claude/skills/taverncard/taverncard_tool.py
```

If the file is **missing**, write it from the source in §7, then install Pillow:
```bash
pip install Pillow -q
```

### Step 2 — Run commands

Always use the full path to the skill tool:
```bash
TOOL=~/.claude/skills/taverncard/taverncard_tool.py

# Inspect a PNG or JSON (no extraction)
python3 $TOOL info <input.png|input.json>

# Extract card JSON from PNG
python3 $TOOL extract <input.png> -o <output.json>

# Extract and convert to V2
python3 $TOOL extract <input.png> -o <output.json> --target v2

# Extract and convert to V1
python3 $TOOL extract <input.png> -o <output.json> --target v1

# Embed JSON into PNG (with artwork)
python3 $TOOL embed <card.json> -o <output.png> --bg <artwork.png>

# Embed JSON into PNG (placeholder image)
python3 $TOOL embed <card.json> -o <output.png>

# Force V2 wrapper when embedding V1 JSON
python3 $TOOL embed <card.json> -o <output.png> --bg <art.png> --wrap v2

# Swap artwork, preserve card data
python3 $TOOL swap-image --card-png <card.png> --image-png <new_art.png> -o <output.png>

# Convert V1 JSON → V2 JSON
python3 $TOOL convert <input.json> -o <output.json> --to v2

# Convert V2 PNG → V1 JSON
python3 $TOOL convert <input.png> -o <output.json> --to v1

# Convert V1 JSON → V2 PNG
python3 $TOOL convert <input.json> -o <output.png> --to v2 --format png --bg <art.png>
```

Full flag reference: `references/tool_cli.md`

---

## 7. Tool Source (Bootstrap)

If `~/.claude/skills/taverncard/taverncard_tool.py` is missing, write this
source to that path verbatim, then run `pip install Pillow -q`.

```python
#!/usr/bin/env python3
"""
taverncard_tool.py — PNG/JSON helper for TavernCards (V1 & V2)
Bundled with the taverncard Claude skill. Requires: pip install Pillow
Commands: info, extract, embed, swap-image, convert
"""
import argparse, sys, json, base64, re
from typing import Optional, Tuple, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

PNG_SIG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])  # \x89PNG\r\n\x1a\n

# --------------- Utilities ---------------

def is_png(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(8) == PNG_SIG
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
    return re.sub(r"[\u0080-\uFFFF]", lambda m: "\\u%04x" % ord(m.group(0)), s)

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
    img = Image.open(path)
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

def build_png_with_card(out_path: str, json_obj: Dict[str, Any], key: str = "chara",
                        encoding: str = "base64", hints: bool = True,
                        bg_path: Optional[str] = None, size: str = "512x512",
                        title: Optional[str] = None) -> None:
    m = re.match(r"(\d+)x(\d+)", size)
    W, H = (int(m.group(1)), int(m.group(2))) if m else (512, 512)
    if bg_path:
        base_img = Image.open(bg_path).convert("RGBA")
        img = Image.new("RGBA", (W, H), (26, 26, 32, 255))
        img.paste(base_img.resize((W, H), Image.LANCZOS), (0, 0))
    else:
        img = Image.new("RGBA", (W, H), (26, 26, 32, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except Exception:
            font = ImageFont.load_default()
        text = title or json_obj.get("data", {}).get("name") or json_obj.get("name", "Character")
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, (H - th) // 2), text, fill=(235, 235, 235, 255), font=font)
    if encoding == "base64":
        payload = base64.b64encode(json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")
    else:
        payload = ascii_escape_json(json_obj)
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text(key, payload)
    if hints and encoding == "base64":
        pnginfo.add_text("chara_encoding", "base64")
        if json_obj.get("spec") == "chara_card_v2":
            pnginfo.add_text("chara_spec", "chara_card_v2")
    img.save(out_path, "PNG", pnginfo=pnginfo, optimize=False)

# --------------- Commands ---------------

def cmd_info(args):
    if is_png(args.input):
        card, chunks, key = extract_card_from_png(args.input)
        print(f"[INFO] File: {args.input}\n  Type: PNG\n  Text keys: {list(chunks.keys())}")
        print(f"  Card detected under: {key!r}" if key else "  Card detected under: None")
        if card:
            kind = detect_card_obj(card)
            name = card.get("data", {}).get("name") if kind == "V2" else card.get("name")
            print(f"  Card kind: {kind}\n  Name: {name}")
        else:
            print("  No Tavern card JSON detected.")
    else:
        try:
            obj = load_json(args.input)
            kind = detect_card_obj(obj)
            name = obj.get("data", {}).get("name") if kind == "V2" else obj.get("name")
            print(f"[INFO] File: {args.input}\n  Type: JSON\n  Detected kind: {kind}\n  Name: {name}")
        except Exception as e:
            print(f"[ERROR] Could not read file: {e}", file=sys.stderr); sys.exit(1)

def cmd_extract(args):
    if not is_png(args.input):
        print("[ERROR] extract expects a PNG input.", file=sys.stderr); sys.exit(1)
    card, _, key = extract_card_from_png(args.input, keys=args.keys or None)
    if not card:
        print("[ERROR] No Tavern card JSON found in PNG.", file=sys.stderr); sys.exit(2)
    if args.target == "v1" and detect_card_obj(card) == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.target == "v2" and detect_card_obj(card) == "V1":
        card = wrap_v1_to_v2(card)
    save_json(args.out, card)
    print(f"[OK] Extracted card → {args.out} (from key {key})")

def cmd_embed(args):
    card = extract_card_from_png(args.input)[0] if is_png(args.input) else load_json(args.input)
    if card is None:
        print("[ERROR] PNG input has no Tavern card JSON.", file=sys.stderr); sys.exit(2)
    kind = detect_card_obj(card)
    if args.wrap == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)
    elif args.wrap == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)
    build_png_with_card(args.out, card, args.key, "base64" if args.base64 else "plain",
                        args.hints, args.bg, args.size, args.title)
    print(f"[OK] Embedded → {args.out} ({detect_card_obj(card)} / {'base64' if args.base64 else 'plain'})")

def cmd_swap_image(args):
    if not is_png(args.card_png):
        print("[ERROR] --card-png must be a TavernCard PNG", file=sys.stderr); sys.exit(1)
    card, _, key_used = extract_card_from_png(args.card_png)
    if not card:
        print("[ERROR] No card JSON found in --card-png", file=sys.stderr); sys.exit(2)
    build_png_with_card(args.out, card, args.key or key_used or "chara",
                        "base64" if args.base64 else "plain", args.hints,
                        args.image_png, args.size, args.title)
    print(f"[OK] Swapped image, preserved JSON → {args.out}")

def cmd_convert(args):
    card = extract_card_from_png(args.input)[0] if is_png(args.input) else load_json(args.input)
    if card is None:
        print("[ERROR] PNG input has no Tavern card JSON.", file=sys.stderr); sys.exit(2)
    kind = detect_card_obj(card)
    if args.to == "v1" and kind == "V2":
        card = unwrap_v2_to_v1(card)
    elif args.to == "v2" and kind == "V1":
        card = wrap_v1_to_v2(card)
    if args.format == "json":
        save_json(args.out, card)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} JSON)")
    else:
        build_png_with_card(args.out, card, args.key, "base64" if args.base64 else "plain",
                            args.hints, args.bg, args.size, args.title)
        print(f"[OK] Converted → {args.out} ({args.to.upper()} in PNG)")

# --------------- CLI ---------------

def build_parser():
    p = argparse.ArgumentParser(prog="taverncard_tool.py",
        description="TavernCard PNG/JSON toolkit (V1 & V2). Requires: pip install Pillow")
    p.add_argument("-?", action="help")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("info"); sp.add_argument("input"); sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("extract")
    sp.add_argument("input"); sp.add_argument("-o","--out", required=True)
    sp.add_argument("--keys", nargs="*"); sp.add_argument("--target", choices=["v1","v2"])
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser("embed")
    sp.add_argument("input"); sp.add_argument("-o","--out", required=True)
    sp.add_argument("--bg"); sp.add_argument("--size", default="512x512")
    sp.add_argument("--title"); sp.add_argument("--key", default="chara")
    sp.add_argument("--base64", action="store_true", default=True)
    sp.add_argument("--plain", dest="base64", action="store_false")
    sp.add_argument("--hints", action="store_true", default=True)
    sp.add_argument("--no-hints", dest="hints", action="store_false")
    sp.add_argument("--wrap", choices=["v1","v2"])
    sp.set_defaults(func=cmd_embed)

    sp = sub.add_parser("swap-image")
    sp.add_argument("--card-png", required=True); sp.add_argument("--image-png", required=True)
    sp.add_argument("-o","--out", required=True); sp.add_argument("--size", default="512x512")
    sp.add_argument("--title"); sp.add_argument("--key")
    sp.add_argument("--base64", action="store_true", default=True)
    sp.add_argument("--plain", dest="base64", action="store_false")
    sp.add_argument("--hints", action="store_true", default=True)
    sp.add_argument("--no-hints", dest="hints", action="store_false")
    sp.set_defaults(func=cmd_swap_image)

    sp = sub.add_parser("convert")
    sp.add_argument("input"); sp.add_argument("-o","--out", required=True)
    sp.add_argument("--to", choices=["v1","v2"], required=True)
    sp.add_argument("--format", choices=["json","png"], default="json")
    sp.add_argument("--bg"); sp.add_argument("--size", default="512x512")
    sp.add_argument("--title"); sp.add_argument("--key", default="chara")
    sp.add_argument("--base64", action="store_true", default=True)
    sp.add_argument("--plain", dest="base64", action="store_false")
    sp.add_argument("--hints", action="store_true", default=True)
    sp.add_argument("--no-hints", dest="hints", action="store_false")
    sp.set_defaults(func=cmd_convert)

    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 8. New V2 Card Template

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "description": "Full character description. Use {{char}} for the name, {{user}} for the user.",
    "personality": "Short trait summary — 1–3 sentences or keyword list. Must stand alone if description is pruned.",
    "scenario": "The context or setting for conversations.",
    "first_mes": "The character's opening message. Use {{char}} and {{user}}.",
    "mes_example": "<START>\n{{user}}: example input\n{{char}}: example response\n<START>\n{{user}}: another example\n{{char}}: another response",
    "creator_notes": "Notes for users of this card (never injected into prompts).",
    "system_prompt": "{{original}}",
    "post_history_instructions": "{{original}}",
    "alternate_greetings": [],
    "character_book": null,
    "tags": [],
    "creator": "",
    "character_version": "1.0.0",
    "extensions": {}
  }
}
```

---

## 9. Manual V1 → V2 Upgrade

1. Wrap all existing fields inside `data: {}`
2. Add at root: `"spec": "chara_card_v2"`, `"spec_version": "2.0"`
3. Add inside `data` with spec-correct defaults:
   - `"creator_notes": ""`
   - `"system_prompt": "{{original}}"`
   - `"post_history_instructions": "{{original}}"`
   - `"alternate_greetings": []`
   - `"tags": []`, `"creator": ""`, `"character_version": "1.0.0"`
   - `"extensions": {}`
4. Omit `character_book` unless lorebook data exists

---

## 10. Specification Coverage

This skill implements **TavernCard V1 and V2**. A V3 specification also exists
but is not yet implemented in the bundled tool.

All specifications used to develop this skill are included for reference:

- `references/taverncard_specifications/spec_v1.md` — V1 field definitions
- `references/taverncard_specifications/spec_v2.md` — V2 additions and field rules
- `references/taverncard_specifications/keyword_definitions_spec_v1-v2.md` — MUST/SHOULD/MAY definitions
- `references/taverncard_specifications/SPEC_V3.md` — V3 specification (not yet implemented)
- `references/taverncard_specifications/concepts_V3.md` — V3 design concepts

If asked about V3, read `SPEC_V3.md` and `concepts_V3.md` to answer accurately,
but make clear that `taverncard_tool.py` does not support V3 operations yet.
