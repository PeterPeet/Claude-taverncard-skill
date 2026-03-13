# TavernCard Claude Skill

A Claude skill for working with **TavernCard V1 and V2** character cards — inspect, validate, create, edit, convert, and manage character card JSON and PNG files directly inside Claude.

---

## What Is This?

[TavernCards](https://github.com/malfoyslastname/character-card-spec-v2) are character definition files used by AI chat frontends like SillyTavern, KoboldAI, and others. They store a character's name, description, personality, scenario, example dialogues, and more — either as a standalone JSON file or embedded invisibly inside a PNG image.

This skill teaches Claude the TavernCard V1 and V2 specifications so it can:

- **Inspect & validate** cards against the spec and flag issues
- **Create** new V2 cards from scratch
- **Edit & fix** existing cards (fill empty fields, fix spec violations, etc.)
- **Compare** two versions of the same card
- **Convert** between V1 and V2 formats
- **Extract** card JSON from PNG images
- **Embed** card JSON into PNG images (with optional artwork)
- **Swap artwork** on a PNG card while keeping the card data intact
- Handle **PNG, JPEG, and WebP** card images — detected by file content, not extension

---

## Installation

1. Copy the `taverncard/` folder to your Claude skills directory:
   ```
   ~/.claude/skills/taverncard/
   ```
2. The skill will be available automatically in Claude.

The bundled `taverncard_tool.py` handles all PNG operations locally. It requires Python 3 and [Pillow](https://pillow.readthedocs.io/):
```bash
pip install Pillow
```

---

## Using the Skill

Just describe what you want to do with your TavernCard, and Claude will handle it.

**Examples:**
- *"Validate this card JSON and tell me every spec issue you find"*
- *"Convert this V1 card to V2 format"*
- *"Extract the card JSON from this PNG and fix the empty personality field"*
- *"Create a new V2 card for a wise elven librarian named Sylara"*
- *"Compare these two versions of the same card and tell me what changed"*

---

## Uploading TavernCard PNGs to Claude.ai

> **⚠️ Important:** Claude.ai (the web version) strips metadata from image files on upload. This means the card data embedded in a TavernCard `.png` file will be lost before Claude can read it.

### The `.txt` Rename Workaround

**Rename your card file from `.png` to `.txt` before uploading.** Claude's `taverncard_tool.py` detects file format by reading the file's binary content (magic bytes), not the filename — so a `.txt` file that is actually a PNG is processed correctly.

**Step-by-step:**

1. Locate your TavernCard PNG, e.g. `my_character.png`
2. Rename it to `my_character.txt`
3. Upload `my_character.txt` to Claude.ai
4. Tell Claude: *"Extract and inspect this TavernCard"*

Claude will detect that the file is a PNG from its content, extract the embedded card JSON, and work with it normally.

**To get the card back as a PNG**, Claude can embed the (possibly edited) JSON back into a new PNG file for you to download.

---

## Supported Formats

| Format | Read card data | Use as artwork |
|--------|---------------|----------------|
| PNG | ✅ tEXt chunk (`chara` key) | ✅ |
| JPEG | ✅ EXIF UserComment | ✅ |
| WebP | ✅ EXIF UserComment | ✅ |

All formats are detected by **magic bytes** (file content), not file extension. A card renamed to `.txt`, `.dat`, or any other extension is handled correctly.

---

## `taverncard_tool.py` — Command Reference

```bash
TOOL=~/.claude/skills/taverncard/taverncard_tool.py

# Inspect a card (PNG, JPEG, WebP, or JSON — any extension)
python3 $TOOL info <card>

# Extract card JSON from an image
python3 $TOOL extract <card.png> -o card.json

# Extract and convert to V2 in one step
python3 $TOOL extract <card.png> -o card.json --target v2

# Embed JSON into a PNG (with artwork)
python3 $TOOL embed card.json -o output.png --bg artwork.jpg

# Swap artwork, preserve card data
python3 $TOOL swap-image --card <card.png> --image <new_art.jpg> -o output.png

# Convert V1 JSON → V2 JSON
python3 $TOOL convert card_v1.json -o card_v2.json --to v2

# Convert V1 JSON → V2 PNG with artwork
python3 $TOOL convert card_v1.json -o card_v2.png --to v2 --format png --bg art.png
```

---

## TavernCard Specification

This skill implements the **TavernCard V1 and V2** specifications:

- **V1** — flat JSON with fields: `name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example`
- **V2** — V1 fields wrapped inside a `data{}` envelope, plus: `system_prompt`, `post_history_instructions`, `alternate_greetings`, `character_book` (lorebook), `creator_notes`, `tags`, `extensions`

A V3 specification also exists; the skill can answer questions about it but the tool does not yet support V3 operations.

---

## License

[GNU General Public License v3.0](LICENSE.txt)
