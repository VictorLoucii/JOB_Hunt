# JobHunt — HITL LinkedIn Email Drafter

A cost-effective, semi-automated agentic workflow that drafts highly personalized internship/job application emails from LinkedIn posts.

![JobHunt Demo](assets/JOB_Hunt_Demo.gif)

## How It Works

```
LinkedIn Post → Select Text → Cmd+Shift+X → Local Server → Eligibility Screening 
                                                   │
                                                   ├── [Eligible]   → DeepSeek LLM → Auto-Draft → Gmail Draft Review (HITL)
                                                   └── [Ineligible] → Skip & Log to Terminal
```

1. **Browse LinkedIn normally** — find a relevant internship or job post.
2. **Select the post text** with your mouse (select the whole post for better context).
3. **Press `Cmd+Shift+X`** — Tampermonkey sends it to your local server.
4. **Smart Screening** — The system screens the post text against your strict profile constraints (location, graduation year, experience limits). If you don't match, it skips drafting and prints the reason in the terminal.
5. **DeepSeek drafts a personalized email** based on your profile.
6. **No Terminal Blocking** — If an email is found, it drafts directly. If no email is found, it drafts the message leaving the recipient field blank.
7. **Verify in Gmail Drafts (HITL)** — Open your Gmail Drafts folder to review, verify or add the recipient email, and hit send.


## Features

- **Automated Eligibility Screening:** Pre-evaluates job posts against candidate constraints (locations, maximum experience limits, graduation date, and degree) before drafting. If you are ineligible, it skips drafting and logs the reason directly to the terminal, avoiding wasted API calls and draft clutter.
- **Zero-Risk Extraction:** Uses native `window.getSelection()` and a keyboard shortcut instead of DOM injection, ensuring zero ban risk on LinkedIn.
- **Robust Email Extraction:** Two-stage pipeline uses regex for standard emails and LLM fallback for obfuscated emails (e.g., `user [at] company [dot] com`).
- **Seamless Asynchronous Flow:** Bypasses terminal confirmation prompts, immediately drafting to Gmail for a faster, less disruptive workflow.
- **Resilient API & Client Connections:** Dynamically recreates Gmail API services to prevent stale `httplib2` "Broken pipe" issues and utilizes a 3-attempt retry loop to handle intermittent truncated OpenRouter responses.
- **Smart Deduplication:** Local SQLite database tracks processed posts and emailed authors to prevent duplicate outreach.
- **Automated Resume Attachment:** Automatically finds and attaches the latest PDF resume from your configured directory.
- **Automatic LLM Fallback:** Configures a fallback chain (e.g. DeepSeek with Gemini 2.5 Flash fallback) to automatically recover from rate limits (429 errors) or model downtime.


## Setup

### Prerequisites
- Python 3.11+
- A Google Cloud project with Gmail API enabled ([setup guide below](#gmail-oauth-setup))
- An OpenRouter API key ([get one here](https://openrouter.ai/keys))
- Tampermonkey browser extension

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/JobHunt.git
cd JobHunt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies (editable mode with dev tools)
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your actual API keys
```

### Configuration

1. **Edit `config.yaml`** with your profile (name, university, skills, etc.) and under `user.constraints` define your strict hard requirements:
   ```yaml
   user:
     # ... profile data ...
     constraints:
       allowed_locations: ["Delhi", "Delhi NCR", "Gurgaon", "Noida", "Bangalore", "Remote"]
       excluded_locations: ["Kolkata"]
       max_experience_required_years: 1
       grad_date: "June 2026"
       degree: "BSc(H) Computer Science"
   ```
2. **Place `credentials.json`** in `credentials/` (from Google Cloud Console)
3. **Set your resume directory** in `config.yaml` under `user.resume_dir` (e.g., `~/Documents/resumes/`)
4. **Configure your LLM settings** in `config.yaml` with fallback models to handle 429 rate limits dynamically:
   ```yaml
   llm:
     model: "deepseek/deepseek-chat"
     fallback_models:
       - "google/gemini-2.5-flash"
     temperature: 0.7
     max_tokens: 1024
   ```


### Gmail OAuth Setup

If you haven't completed the OAuth flow yet:

```bash
# This will open a browser window for Google sign-in
python -m server.services.gmail_client --auth
```

After signing in and granting permissions, `token.json` will be saved to `credentials/`.

### Install Tampermonkey Script

1. Open Tampermonkey in your browser
2. Create a new script
3. Paste the contents of `tampermonkey/linkedin_extractor.user.js`
4. Save and enable

## Usage

```bash
# Start the local server
python -m server.main

# Or use the CLI shortcut (after pip install -e .)
jobhunt
```

Then browse LinkedIn, select post text, and press `Cmd+Shift+X` (or `Ctrl+Shift+X` on Windows).

## Project Structure

```
JobHunt/
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
├── config.yaml           # User profile & preferences
├── pyproject.toml        # Python packaging & tool config
├── server/               # FastAPI backend
│   ├── main.py           # App entry point
│   ├── config.py         # Settings loader
│   ├── models.py         # Pydantic schemas
│   ├── routers/          # API endpoints
│   └── services/         # Business logic
├── prompts/              # LLM prompt templates
├── tampermonkey/         # Browser userscript
├── data/                 # SQLite database (runtime)
├── credentials/          # Gmail OAuth (gitignored)
├── scratch/              # API experiments (gitignored)
└── tests/                # Formal test suite
```

## Cost

| Component | Cost |
|---|---|
| Everything except LLM | Free |
| DeepSeek via OpenRouter | ~$0.001/email |
| **100 emails** | **~$0.10** |

## License

MIT
