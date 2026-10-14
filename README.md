# AethraOS

A local Windows desktop assistant. It opens apps, types while you watch, reads the screen, drafts mail, and runs saved workflows. It does not send mail unless you confirm.

## What you need

- Windows 10 or 11
- Python 3.11+
- [LM Studio](https://lmstudio.ai/) with a tool-capable model (Qwen3 8B Q4 is a good fit for a 12 GB GPU)
- Optional: Tesseract for OCR, Outlook for inbox reading, a Google OAuth desktop client for Gmail

## Run

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Or double-click `run_aethra.bat` after the venv exists.

In LM Studio, load the model, turn on tool use, set context to 16384, and start the local server on port 1234. Aethra uses `http://localhost:1234/v1` and model `auto`.

## Safety

- Low-risk actions run. Medium and high-risk actions ask first.
- Mail is drafted, not sent, until you approve the exact text.
- Self-check tools can read the project and propose a patch. They do not edit source files.
- Do not commit `data/`, `.env`, or token files. `.gitignore` already excludes them.

## Limits

This is a personal agent for one Windows PC. It is not an operating system, and it is not a general intelligence. Plans are only as reliable as the local model.
