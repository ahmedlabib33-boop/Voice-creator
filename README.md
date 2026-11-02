# Egyptian Voice Sender

A Streamlit app that turns Egyptian Arabic text into an MP3 voice note and sends it
through the **official WhatsApp Cloud API**. Every generated file is labelled
"Generated AI voice audio."

## AI text engine: Groq (default) or Claude

The sidebar has an **AI text engine** switch. It controls who writes and refines the
message text:

| Engine | Default model | Needs |
|--------|---------------|-------|
| Groq (default) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` (same key as Groq voice) |
| Claude | `claude-opus-5-5` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `llama3.1` | a running Ollama server; refine only |

* **Write with …**: type a short brief in any language and the engine drafts a natural
  Egyptian Arabic voice-note script.
* **Refine with …**: rewrite existing text into Egyptian dialect without changing the
  meaning.

Change the default with `TEXT_ENGINE=claude` and the models with `GROQ_TEXT_MODEL`,
`CLAUDE_MODEL` / `CLAUDE_EFFORT`. Claude runs with adaptive thinking and server-side
refusal fallback. Neither engine produces audio; the voice comes from the TTS
providers below.

## Voice providers (in order of preference)

| # | Provider | Default model / voice | Notes |
|---|----------|-----------------------|-------|
| 1 | Groq Orpheus Arabic TTS | `canopylabs/orpheus-arabic-saudi` / `noura` | WAV only, 200 chars per request. The app splits long text and merges chunks with ffmpeg. Voices: noura, lulwa, aisha, abdullah, fahad, sultan. |
| 2 | OpenAI TTS | `gpt-4o-mini-tts` / `alloy` | MP3 output. |
| 3 | Azure Arabic Egypt Neural TTS | `ar-EG-SalmaNeural` | Uses the Azure Speech REST endpoint for your region. |
| 4 | Windows TTS fallback | SAPI5 via `pyttsx3` | Offline, robotic, Windows only. Shown with a warning. |

The first provider whose credentials are present is selected by default. You can
pick any provider in the UI; missing keys produce a clear setup message that never
shows secret values.

## Setup

Requirements: Python 3.10+, `ffmpeg` on PATH (`winget install Gyan.FFmpeg` on Windows).

```bash
python -m pip install -r requirements.txt
```

### Where to paste your keys

Easiest: open `keys.txt` in Notepad (the launcher creates it from `keys.example.txt`
on first run and opens it for you) and paste the keys after the `=` signs:

```text
ANTHROPIC_API_KEY=
GROQ_API_KEY=
```

A file named `API keys.txt` (or `keys.txt`) in the **parent** folder works too, so you
can keep one keys file outside the project. Lines may be `NAME=value`, `name: value`
(for example `claude: sk-ant-...`, `groq: gsk_...`) or a bare key, which is matched by
its prefix. Set `KEYS_FILE` to use any other path. `keys.txt` is ignored by git. The
same names also work in `.env` (copy `.env.example` to `.env`); non-blank values in
the keys file win over `.env`.
`.env` is ignored by git. Never paste keys into chat, screenshots, or commits. If a key
was ever displayed anywhere, revoke it and create a new one.

```env
ANTHROPIC_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
WHATSAPP_ACCESS_TOKEN=
```

Optional values stay blank unless you want to override the defaults:
`TEXT_ENGINE`, `GROQ_TEXT_MODEL`, `CLAUDE_MODEL`, `CLAUDE_EFFORT`, `GROQ_TTS_MODEL`, `GROQ_TTS_VOICE`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`,
`AZURE_SPEECH_VOICE`, `WHATSAPP_API_VERSION`, `LOCKED_RECIPIENT_NUMBER`,
`OLLAMA_BASE_URL`, `OLLAMA_MODEL`.

Streamlit secrets work too: put the same names in `.streamlit/secrets.toml`
(also ignored by git). A value in `.env` overrides the process environment, and a
UTF-8 BOM written by Windows editors is handled.

Save the key without echoing it in PowerShell:

```powershell
cd path\to\Voice-creator
$secure = Read-Host "Paste Anthropic key" -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
if (!(Test-Path .env)) { Copy-Item .env.example .env }
$lines = Get-Content .env | Where-Object { $_ -notmatch "^ANTHROPIC_API_KEY=" }
@("ANTHROPIC_API_KEY=$key") + $lines | Set-Content .env -Encoding UTF8
$key = $null; $secure = $null
```

## Run

Windows:

```powershell
.\run_app_6543.bat
```

macOS / Linux:

```bash
./run_app_6543.sh
```

Then open http://127.0.0.1:6543. Generated MP3 files land in `generated_audio/`
and the SQLite database in `data/` (both ignored by git).

## Phone numbers

Egyptian local numbers are normalized to E.164 automatically:

| Input | Stored `normalized_e164` |
|-------|--------------------------|
| `01123040202` | `+201123040202` |
| `00201123040202` | `+201123040202` |
| `201123040202` | `+201123040202` |
| `+201123040202` | `+201123040202` |

Contacts and authorized senders store both `original_input` and `normalized_e164`.
Databases created by older versions are migrated on startup. The normalized value
is what the UI displays and what the WhatsApp API receives as the recipient.

## WhatsApp sending rules

* Messages are sent only through an authorized Meta `phone_number_id` saved in the
  **Authorized Sender Manager** tab, using `WHATSAPP_ACCESS_TOKEN`.
* The business phone number is stored for display and validation only. A plain
  number, including an SMS-registered one that can receive OTP codes, is never used as
  a sender.
* The app never automates WhatsApp Web or Desktop. If the Cloud API is not configured,
  the **Manual send** button opens the recipient chat via `wa.me` and shows the MP3
  path so you can attach it yourself.
* "Validate with Meta" checks the token and `phone_number_id` without sending.
  "Send test text" confirms delivery before uploading audio.

## Design system

The UI follows a documented design system: tokens, components, states and
accessibility rules are in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). Styling lives in
`src/ui_theme.py` (CSS custom properties + helpers such as `hero`, `step`, `chips`,
`kpis`) and the base theme in `.streamlit/config.toml`. The Studio tab is a
three-step flow: write, generate voice, send.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers number normalization, database migration, text chunking, a mocked
Claude call (model, fallback header, refusal handling, Ollama fallback) and a mocked Groq run that merges chunks into an MP3 through ffmpeg.
