# SubLens

Reads game subtitles and dialogue from the screen and translates them live. The translation is shown over the game in an **overlay** that sits where the original subtitle is.

## Quick start

1. **Subtitle area > Select (F2):** draw a box around where the subtitles appear. For two-line subtitles cover **both lines** and leave a little margin.
2. **Language and translator:** e.g. English → Turkish with Google Translate (no setup).
3. **Start (F4)** and switch to the game.

If reading is poor, press **Auto-tune** while a subtitle is on screen. It tries every reading setting and keeps the one that gives the cleanest text.

## Text style

| Style | When |
|---|---|
| **Auto** | Most games. Reads the raw frame and the bright-subtitle filter, keeps the text that looks more like language. |
| **Bright subtitle** | White, outlined or shadowed subtitles (RDR2, Spider-Man 2, GTA…). Best over busy, bright scenes. |
| **Dialog box** | Dialogue in flat-coloured boxes and menus. |

**Filtered view** shows what the OCR actually sees.

## Translators

| Engine | Setup | Note |
|---|---|---|
| **Google Translate** | None | Fast and free. Unofficial endpoint, may be rate-limited under heavy use. |
| **DeepL** | API key (free plan: 500k characters/month) | Best machine translation. Uses previous lines as context. |
| **AI (OpenAI-compatible)** | LM Studio / Ollama (local, offline) or an OpenAI, OpenRouter, Groq key | Understands game context, glossary and previous lines. |
| **Claude** | Anthropic API key | Opus is the best quality; Haiku is faster and cheaper for quick dialogue. |
| **Gemini** | Google AI Studio key | Has a free tier. |
| **No translation** | None | Shows the text as read, without translating. Works offline. To read small or blurry text in a language you know, raise the font size under Settings > Overlay. |

Every engine has a **Test** button under Settings > Translation.

**Game context** (e.g. *"Red Dead Redemption 2, Wild West 1899, gang slang"*) helps AI engines get the tone right.

**Glossary:** one rule per line. `Dutch` keeps a word untranslated, `Spider-Man=Örümcek Adam` forces a rendering.

## Game profiles

**Game profile > Manage > Save current settings as a game profile** stores the area, language, reading settings, context and glossary per game. Bind it to the game's exe and it loads by itself when you start scanning in that game.

## Shortcuts

| Key | Global alternative | Action |
|---|---|---|
| F2 | Ctrl+Alt+R | Select area |
| F3 | Ctrl+Alt+T | Translate once |
| F4 | Ctrl+Alt+G | Start / stop |
| Esc | Ctrl+Alt+H | Hide overlay |

Global shortcuts work in fullscreen games too. If the game runs as administrator, run SubLens as administrator as well. If your keyboard has no F keys, use the Ctrl+Alt shortcuts or the buttons in the window.

## Overlay

- Its width follows the subtitle text, so a two-line subtitle comes out as a two-line translation.
- Drag it to move it (it stays where you drop it). Right-click hides it. Pressing Stop closes it.
- It can't be dragged while clicks pass through to the game.
- Settings > Overlay: font size, background opacity, position, showing the original text, passing clicks through to the game, and how long it stays after the subtitle ends.
- The overlay is invisible to screen capture, so it never reads its own translation back, even on top of the area.

## How reading works

- Text is read with **Windows OCR** (built into Windows 10/11, ~10-30 ms per frame). Nothing else to install; the source language's Windows OCR pack must be present.
- The area is only read when its pixels change, so a short interval (0.25 s) is cheap.
- A line is translated once it stays the same for two reads, so fading-in and typewriter text isn't translated half-finished.
- Text misread while half-faded is held for up to 1.2 seconds until it reads cleanly. If it was already translated, a clean read within 3 seconds replaces it. Reads that degrade as a subtitle fades out are not translated again.
- Speaker labels are repaired: a name seen twice with a colon is learned, then damaged forms like "eter:", ".Harry•." or "Peter." become "Peter:".
- Lines that wrap onto the next line are translated as one sentence. A speaker tag like `ARTHUR:` starts a new paragraph.
- **Scrolling captions** (YouTube, streams, some games) are detected automatically: lines already seen are not translated again, new words are sent a sentence at a time, and if the translator is slow the waiting pieces are merged instead of dropped.
- **Conversation context:** AI engines get the previous lines together with their translations, so short replies are translated from what came before ("You should try this." then "Neyi?" becomes "Try what?"). Lines older than 90 seconds count as another scene and are left out. Google cannot use context; pick an AI engine for this.
- Controller/key icons, symbols and small UI hints ("Hold E to skip") are filtered out.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Windows OCR has no '…' language pack" | Windows Settings > Time & language > Language > add the language (tick "Optical character recognition"). |
| "The text doesn't look like …" | Wrong source language. A Turkish video needs source language **Turkish**. |
| Garbled text | **Auto-tune** with a subtitle on screen. Otherwise try **Bright subtitle** and make the area hug the subtitle. |
| No text | Check with **Filtered view**. Is the area in the right place? |
| Speaker names lose their first letters | The area cuts the name off. Widen it a little to the left. |
| Translations lag | Google or DeepL are faster than local models. For Claude choose Haiku. |
| Google errors | Switch to DeepL or another engine for a while. |
| Shortcuts don't work in game | Run SubLens as administrator. |

Switch the interface language with **EN / TR** at the top right (or Settings > General). Windows notifications can be turned off under Settings > General too.

At startup SubLens asks GitHub whether a newer version exists. If one does, it shows the release notes and a Download button for the new exe. Turn this off under Settings > General, or check by hand with **Check for updates** in the Help window.

Settings live in `%APPDATA%\SubLens\config.json`. Delete it if it ever gets corrupted.
