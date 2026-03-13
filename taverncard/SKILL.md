---
name: taverncard
description: >
  Use when the user wants to work with TavernCard character cards in V1 or V2
  format. Triggers for: inspecting, validating, creating, editing, or converting
  TavernCard JSON, PNG, JPEG, or WebP files; extracting card data from images;
  embedding JSON into PNGs; swapping card artwork; handling misnamed image files
  (e.g. a .png that is actually JPEG or WebP); or any question about the
  TavernCard V1/V2 specification. Also triggers for lorebook / character_book
  work and identifying spec compliance issues in cards downloaded from sites like
  CharacterHub, Chub.ai, JanitorAI, or AI Character Editor.
---

# TavernCard Expert

> ⚠️ **LOCAL USE ONLY — Python image tool does not work on Claude.ai (web)**
>
> The bundled `taverncard_tool.py` (§6 / §7) reads raw image bytes directly
> from disk. **Claude.ai strips image metadata (EXIF, PNG tEXt chunks) before
> the tool can access the file**, so card data embedded in uploaded images is
> lost before extraction can occur.
>
> **Use this skill's Python tool only with local Claude Code (CLI).**
> On Claude.ai you can still work with TavernCard **JSON files** (validation,
> editing, conversion, spec questions) — just not image extraction/embedding.
> Always inform the user of this limitation when they upload an image on
> Claude.ai and expect card data to be extracted.

You are an expert on the TavernCard V1 and V2 character card specification.
You can inspect, validate, create, edit, convert, and explain TavernCard JSON,
PNG, JPEG, and WebP files. The skill folder includes a bundled Python tool for
image operations — see §6 for setup instructions.

**Image format detection:** The tool identifies image files by their **magic
bytes** (binary header), not by file extension. A file named `.png` that is
actually a JPEG or WebP is handled correctly. Always use `info` first when
unsure about a file's actual format.

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

## 6. Card Image Tool — Usage

The tool `taverncard_tool.py` is bundled with this skill and already present at:

```
~/.claude/skills/taverncard/taverncard_tool.py
```

It requires only **Python 3** and **Pillow** (`pip install Pillow`). Works on macOS, Linux, and Windows.

> **Claude.ai workaround:** Claude.ai strips metadata from image files on upload,
> removing the embedded card data. **Rename the card from `.png` to `.txt` before
> uploading** (e.g. `my_char.png → my_char.txt`). The tool detects format by
> magic bytes, not file extension, so the renamed file is processed correctly.

**Supported image input formats** (detected by magic bytes, not filename):

| Format | Card data location |
|---|---|
| PNG  | `tEXt` chunk — key `chara` / `chara_card_v2` / `ai_chara` |
| JPEG | EXIF `UserComment` tag (0x9286) |
| WebP | EXIF `UserComment` tag (0x9286) |

Any file extension is accepted. **Output images are always PNG.**

### Commands

```bash
TOOL=~/.claude/skills/taverncard/taverncard_tool.py

# Inspect any image or JSON — reports actual detected format and card version
python3 $TOOL info <card>
python3 $TOOL info <card>.txt          # .txt rename workaround for Claude.ai

# Extract card JSON from any image
python3 $TOOL extract <card.png> -o card.json
python3 $TOOL extract <card>.txt -o card.json   # .txt rename workaround

# Extract and convert in one step
python3 $TOOL extract <card.png> -o card.json --target v2
python3 $TOOL extract <card.png> -o card.json --target v1

# Embed JSON into a new PNG (artwork: PNG, JPEG, or WebP)
python3 $TOOL embed card.json -o out.png --bg art.jpg
python3 $TOOL embed card.json -o out.png           # placeholder art

# Force V2 wrapper when embedding V1 JSON
python3 $TOOL embed card.json -o out.png --bg art.png --wrap v2

# Swap artwork, preserve card JSON (card may be PNG, JPEG, or WebP)
python3 $TOOL swap-image --card card.png --image new_art.jpg -o out.png

# Convert between V1 / V2 — input may be image or JSON
python3 $TOOL convert card.json -o card_v2.json --to v2
python3 $TOOL convert card.png  -o card_v1.json --to v1
python3 $TOOL convert card.json -o card_v2.png  --to v2 --format png --bg art.jpg
```

Full flag reference: `references/tool_cli.md`

---

## 7. New V2 Card Template

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

## 8. Manual V1 → V2 Upgrade
1. → V2 Upgrade

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

## 9. Specification Coverage

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
