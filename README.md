# JobHunt — HITL LinkedIn Email Drafter

A cost-effective, semi-automated agentic workflow that drafts highly personalized internship/job application emails from LinkedIn posts.

## How It Works

```
LinkedIn Post → Select Text → Cmd+Shift+X → Local Server → DeepSeek LLM → HITL Review → Gmail Draft
```

1. **Browse LinkedIn normally** — find a relevant internship post with an email
2. **Select the post text** with your mouse
3. **Press `Cmd+Shift+X`** — Tampermonkey sends it to your local server
4. **DeepSeek drafts a personalized email** based on your profile
5. **Review in terminal** — approve, edit, regenerate, or skip
6. **Gmail draft created** with your resume attached — just hit send

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

1. **Edit `config.yaml`** with your profile (name, university, skills, etc.)
2. **Place `credentials.json`** in `credentials/` (from Google Cloud Console)
3. **Set your resume directory** in `.env` (`RESUME_DIR=~/Documents/resumes/`)

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

Then browse LinkedIn, select post text, and press `Cmd+Shift+X`.

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
