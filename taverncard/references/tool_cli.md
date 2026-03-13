# taverncard_tool.py — Full CLI Reference

The bundled `taverncard_tool.py` (Python 3 + Pillow) implements all five commands.

**Prerequisite (Python):** `pip install Pillow`

---

## Commands

### `info` — Inspect without extracting

```
python taverncard_tool.py info <input>
```

- `<input>`: PNG or JSON file path
- Prints: file type, detected card version (V1/V2/UNKNOWN), character name,
  PNG text chunk keys present
- Does NOT write any output file

---

### `extract` — Pull JSON from a PNG

```
python taverncard_tool.py extract <input.png> -o <output.json> [options]
```

| Flag | Description |
|---|---|
| `-o / --out` | Output JSON path (required) |
| `--target v1\|v2` | Convert extracted card to V1 or V2 before saving |
| `--keys KEY ...` | Override PNG chunk keys to search (default: `chara chara_card_v2 ai_chara`) |

Examples:
```bash
# Plain extract
python taverncard_tool.py extract card.png -o card.json

# Extract and upgrade to V2
python taverncard_tool.py extract card.png -o card_v2.json --target v2

# Extract and downgrade to V1
python taverncard_tool.py extract card.png -o card_v1.json --target v1

# Try a non-standard chunk key
python taverncard_tool.py extract card.png -o card.json --keys chara ccv3
```

---

### `embed` — Embed JSON into a PNG

```
python taverncard_tool.py embed <input> -o <output.png> [options]
```

`<input>` may be a JSON file or a TavernCard PNG (JSON is extracted from it).

| Flag | Description |
|---|---|
| `-o / --out` | Output PNG path (required) |
| `--bg <path>` | Background image (PNG or JPG) to use as card artwork |
| `--size WxH` | Canvas size, default `512x512` |
| `--title TEXT` | Text overlay on blank canvas (when no `--bg`) |
| `--key KEY` | PNG chunk key to write (default: `chara`) |
| `--base64` | Encode JSON as base64 in chunk (default) |
| `--plain` | Encode JSON as ASCII-escaped plain text |
| `--hints / --no-hints` | Write `chara_encoding` / `chara_spec` hint keys (default: on) |
| `--wrap v1\|v2` | Force wrap/unwrap of JSON to target version before embedding |

Examples:
```bash
# Embed with artwork
python taverncard_tool.py embed card.json -o card.png --bg artwork.png

# Embed V1 JSON, auto-upgrade to V2 in the PNG
python taverncard_tool.py embed card_v1.json -o card_v2.png --bg art.png --wrap v2

# Embed without artwork (generates placeholder image with character name)
python taverncard_tool.py embed card.json -o card.png
```

---

### `swap-image` — Replace artwork, keep card data

Preserves the embedded JSON exactly; only the image changes.

```
python taverncard_tool.py swap-image \
  --card-png <existing_card.png> \
  --image-png <new_artwork.png> \
  -o <output.png> [options]
```

| Flag | Description |
|---|---|
| `--card-png` | Source TavernCard PNG (provides the JSON) — required |
| `--image-png` | New artwork image (PNG or JPG) — required |
| `-o / --out` | Output PNG path — required |
| `--size WxH` | Canvas size, default `512x512` |
| `--key KEY` | Override output chunk key (default: keep source key or `chara`) |
| `--base64 / --plain` | Encoding for the output (default: base64) |
| `--hints / --no-hints` | Hint keys in output (default: on) |

Example:
```bash
python taverncard_tool.py swap-image \
  --card-png <existing-card>.png \
  --image-png <new-art>.png \
  -o <output>.png
```

---

### `convert` — Convert between V1 and V2

```
python taverncard_tool.py convert <input> -o <output> --to v1|v2 [options]
```

`<input>` may be a JSON file or a TavernCard PNG.

| Flag | Description |
|---|---|
| `-o / --out` | Output file path (required) |
| `--to v1\|v2` | Target spec version (required) |
| `--format json\|png` | Output format (default: `json`) |
| `--bg <path>` | Background image for PNG output |
| `--size WxH` | Canvas size for PNG output (default `512x512`) |
| `--key KEY` | PNG chunk key for PNG output (default `chara`) |
| `--base64 / --plain` | Encoding for PNG output (default: base64) |
| `--hints / --no-hints` | Hint keys for PNG output (default: on) |

Examples:
```bash
# V1 JSON → V2 JSON
python taverncard_tool.py convert card_v1.json -o card_v2.json --to v2

# V2 JSON → V1 JSON
python taverncard_tool.py convert card_v2.json -o card_v1.json --to v1

# V1 PNG → V2 PNG (with new canvas from existing art)
python taverncard_tool.py convert card.png -o card_v2.png --to v2 --format png --bg art.png

# Any card PNG → V1 plain-encoded PNG
python taverncard_tool.py convert card.png -o card_v1.png --to v1 --format png --plain
```

---

## Detection Logic (for reference)

The tool detects card version from the parsed JSON object:
- `obj.spec == "chara_card_v2"` AND `"data" in obj` → **V2**
- `name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example`
  all present at root → **V1**
- Otherwise → **UNKNOWN**

PNG chunk keys searched by default: `chara`, `chara_card_v2`, `ai_chara`.
Both base64-encoded and plain JSON payloads are auto-detected.
