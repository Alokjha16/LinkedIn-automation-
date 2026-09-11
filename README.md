# 🔗 LinkedIn Job Post Email Automation using Gmail API

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gmail API](https://img.shields.io/badge/Gmail-API-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](https://developers.google.com/gmail/api)
[![Selenium](https://img.shields.io/badge/Selenium-4.x-43B02A?style=for-the-badge&logo=selenium&logoColor=white)](https://selenium.dev)
[![License](https://img.shields.io/badge/License-Educational-blue?style=for-the-badge)]()

> **Automated tool to search LinkedIn posts for job requirements, extract recruiter emails, and send professional candidate submission emails through Gmail API with resume attachment.**

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Gmail API Setup](#gmail-api-setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Workflow](#workflow)
- [Screenshots](#screenshots)
- [Safety & Compliance](#safety--compliance)
- [Troubleshooting](#troubleshooting)
- [Author](#author)

---

## 🎯 Overview

This project automates the process of:
1. **Searching** LinkedIn for recent job requirement posts
2. **Extracting** recruiter email addresses from post content
3. **Sending** professional candidate submission emails via Gmail API

Built for **educational and demo purposes** as part of an internship assignment.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **LinkedIn Scraping** | Searches posts with configurable keywords and date filters |
| 📧 **Email Extraction** | Regex-based extraction with obfuscation support |
| 📨 **Gmail Integration** | Full OAuth 2.0 authentication with send/draft support |
| 📎 **Resume Attachment** | Automatically attaches candidate resume (PDF) |
| 📊 **CSV Export** | Saves leads and sent logs to organized CSV files |
| 🔄 **Duplicate Removal** | Prevents sending duplicate emails |
| 👀 **Preview Mode** | Shows leads before sending for user confirmation |
| 📝 **Dry-Run Mode** | Creates Gmail drafts instead of sending (default) |
| 🛡️ **Rate Limiting** | Built-in delays between actions to avoid detection |
| 📷 **Screenshots** | Captures search results for documentation |
| 🔒 **Manual Login** | LinkedIn login is manual — no automated login/bypass |

---

## 📁 Project Structure

```
linkedin-gmail-automation/
│
├── main.py                    # Main entry point — orchestrates the workflow
├── config.py                  # Configuration and environment variables
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── .gitignore                 # Git ignore rules
├── candidate_data.json        # Candidate details (JSON)
├── README.md                  # This file
│
├── src/                       # Source modules
│   ├── __init__.py
│   ├── linkedin_scraper.py    # LinkedIn browser automation & scraping
│   ├── email_extractor.py     # Email regex extraction & validation
│   ├── gmail_service.py       # Gmail API auth, compose, send/draft
│   ├── csv_manager.py         # CSV read/write, dedup, logging
│   └── email_template.py      # Email subject/body generators
│
├── credentials/               # Gmail API credentials (NOT committed)
│   └── README.md              # Setup instructions for credentials
│
├── resumes/                   # Candidate resumes
│   └── Sunny_Patel_Resume.pdf # Resume file (placeholder)
│
├── outputs/                   # Generated output files
│   ├── leads.csv              # Extracted leads with emails
│   └── sent_log.csv           # Email send/draft log
│
└── screenshots/               # Auto-captured search screenshots
    └── README.md
```

---

## 🔧 Prerequisites

- **Python 3.10+** installed ([Download](https://www.python.org/downloads/))
- **Google Chrome** browser installed
- **LinkedIn account** (personal — for manual login)
- **Google Cloud account** (for Gmail API credentials)
- **ChromeDriver** (auto-managed by `webdriver-manager`)

---

## 🚀 Installation

### 1. Clone or Download the Project

```bash
cd linkedin-gmail-automation
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

```bash
copy .env.example .env
```

Edit `.env` with your details:
```env
SENDER_EMAIL=your_email@gmail.com
SENDER_NAME=Alok Jha
DRY_RUN=true
```

---

## 🔐 Gmail API Setup

Follow these steps to enable Gmail API and download credentials:

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Name it (e.g., "LinkedIn Email Automation")
4. Click **Create**

### Step 2: Enable Gmail API

1. In the Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for **"Gmail API"**
3. Click on it and press **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** → Click **Create**
3. Fill in:
   - App name: "LinkedIn Email Automation"
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. On **Scopes** page, click **Add or Remove Scopes**
6. Add: `https://www.googleapis.com/auth/gmail.compose`
7. Click **Save and Continue**
8. On **Test users** page, click **Add Users**
9. Add your Gmail address
10. Click **Save and Continue**

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: "LinkedIn Automation Desktop"
5. Click **Create**
6. Click **Download JSON**
7. Rename the file to `credentials.json`
8. Move it to the `credentials/` folder in this project

### Step 5: First-Time Authentication

When you run the tool for the first time:
1. A browser window will open asking you to sign in to Google
2. Select your Gmail account
3. Click **"Allow"** to grant permissions
4. The token will be saved automatically for future use

---

## ⚙️ Configuration

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `SENDER_EMAIL` | Your Gmail address | `your_email@gmail.com` |
| `SENDER_NAME` | Your name for email signature | `Alok Jha` |
| `DRY_RUN` | `true` = drafts only, `false` = send | `true` |
| `CHROME_PROFILE_DIR` | Chrome profile path for persistent login | (empty) |

### Candidate Details (`candidate_data.json`)

Edit this file to change the candidate being submitted:

```json
{
    "name": "Sunny Patel",
    "role": "Project Manager / C2C Contractor",
    "experience": "9+ Years",
    "email": "sunnypatel@gmail.com",
    "phone": "+1-609-555-2022",
    "location": "Princeton, NJ",
    "work_authorization": "H1B / GC EAD",
    "availability": "Immediate",
    "relocation": "Open",
    "linkedin": "linkedin.com/in/sunnypatel",
    "salary": "Open / As per market rate"
}
```

### Search Keywords (`config.py`)

Default keywords can be modified in `config.py` or overridden via CLI:

```python
DEFAULT_SEARCH_KEYWORDS = [
    "Java Developer C2C",
    "Java Developer W2",
    "Java Developer Contract",
    "Java Developer email",
]
```

---

## 📖 Usage

### Basic Usage (Dry-Run / Draft Mode)

```bash
python main.py
```

This will:
1. Open Chrome for LinkedIn manual login
2. Search with default keywords
3. Extract emails from posts
4. Save leads to `outputs/leads.csv`
5. Show preview and ask for confirmation
6. Create Gmail **drafts** (not send)

### Send Emails Directly

```bash
python main.py --send
```

### Skip Scraping (Use Existing Leads)

```bash
python main.py --skip-scrape
```

### Custom Keywords

```bash
python main.py --keywords "Python Developer C2C" "React Developer W2"
```

### Custom Resume Path

```bash
python main.py --resume "path/to/resume.pdf"
```

### Limit Emails Per Session

```bash
python main.py --max-emails 5
```

### Combined Example

```bash
python main.py --skip-scrape --send --max-emails 10
```

---

## 🔄 Workflow

```
┌─────────────────┐
│  Start main.py  │
└────────┬────────┘
         │
┌────────▼────────┐     ┌──────────────────────┐
│  Open Chrome    │────►│ User logs in to       │
│  (LinkedIn)     │     │ LinkedIn manually     │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
┌────────▼─────────────────────────▼──┐
│  Search posts with keywords         │
│  (Java Developer C2C, W2, etc.)     │
└────────┬────────────────────────────┘
         │
┌────────▼────────┐
│  Extract emails │
│  from post text │
└────────┬────────┘
         │
┌────────▼────────┐
│  Save leads to  │
│  leads.csv      │
│  (dedup emails) │
└────────┬────────┘
         │
┌────────▼────────┐     ┌──────────────────┐
│  Preview leads  │────►│ User confirms    │
│  in console     │     │ (yes/no)         │
└────────┬────────┘     └──────────┬───────┘
         │                         │
┌────────▼─────────────────────────▼──┐
│  Authenticate Gmail (OAuth 2.0)     │
└────────┬────────────────────────────┘
         │
┌────────▼────────────────────────────┐
│  For each lead:                     │
│  • Generate email from template     │
│  • Attach resume PDF                │
│  • Send OR save as draft            │
│  • Log to sent_log.csv              │
│  • Wait (rate limit delay)          │
└────────┬────────────────────────────┘
         │
┌────────▼────────┐
│  Done! Summary  │
└─────────────────┘
```

---

## 📸 Screenshots

> Add screenshots of the tool in action here:

| Step | Screenshot |
|------|------------|
| LinkedIn Search | `screenshots/search_Java_Developer_C2C.png` |
| Leads Preview | *(add console screenshot)* |
| Email Draft | *(add Gmail draft screenshot)* |
| Sent Log | *(add sent_log.csv screenshot)* |

---

## 🛡️ Safety & Compliance

> **⚠️ IMPORTANT DISCLAIMER**

This tool is built for **educational and demonstration purposes only**.

### Compliance Measures

| Measure | Implementation |
|---------|----------------|
| **Manual Login** | LinkedIn login is performed manually by the user — no credentials are stored or automated |
| **Rate Limiting** | Random delays (2-5 seconds) between all browser actions |
| **No Bypass** | No CAPTCHA bypass, no security circumvention, no headless scraping |
| **User Confirmation** | Emails are previewed and require explicit user approval before sending |
| **Dry-Run Default** | Emails default to draft mode — not sent unless `--send` flag is used |
| **Session Limits** | Maximum emails per session is capped (default: 20) |
| **Transparent** | All actions are logged to `automation.log` |
| **No Fake Accounts** | Uses the user's real LinkedIn and Gmail accounts |

### LinkedIn Terms

- This tool does NOT use LinkedIn's API (which requires partnership)
- Only publicly visible post text is read
- The tool is equivalent to manually reading and copying from posts
- For production use, consider LinkedIn's official API partner program

### Gmail API

- Uses official Google Gmail API with proper OAuth 2.0
- Only the `gmail.compose` scope is requested (minimal permissions)
- Token can be revoked at any time from Google Account settings

---

## 🔧 Troubleshooting

### ChromeDriver Version Mismatch

```bash
pip install --upgrade webdriver-manager
```

The tool uses `webdriver-manager` to auto-download the correct ChromeDriver.

### Gmail Authentication Error

1. Delete `credentials/token.json`
2. Run the tool again — it will re-authenticate
3. Make sure your email is added as a test user in Google Cloud Console

### No Emails Found

- Not all LinkedIn posts contain email addresses
- Try different keywords or broader searches
- Check if posts are visible (you must be logged in)

### LinkedIn Security Challenge

- If LinkedIn shows a security check, complete it manually
- Use a Chrome profile (`CHROME_PROFILE_DIR` in `.env`) for persistent sessions

---

## 👤 Author

**Alok Jha**

Internship Assignment — LinkedIn Job Post Email Automation using Gmail API

---

## 📄 License

This project is for **educational/demo purposes only**. Not intended for commercial use or mass email campaigns.

---

*Built with Python, Selenium, and Gmail API* 🐍
