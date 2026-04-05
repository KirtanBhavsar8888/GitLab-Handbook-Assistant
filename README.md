# 🦊 GitLab Handbook Assistant

An AI-powered chatbot that lets employees and candidates instantly query GitLab's [Handbook](https://handbook.gitlab.com/) and [Direction](https://about.gitlab.com/direction/) pages using natural language — no more manual searching through thousands of pages.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE                        │
│                      (Run once offline)                     │
│                                                             │
│   GitLab Handbook   GitLab Direction                        │
│   (300+ pages)      (1 page)                                │
│        │                 │                                  │
│        └────────┬────────┘                                  │
│                 │                                           │
│            scrape.py                                        │
│         (BeautifulSoup)                                     │
│                 │                                           │
│         scraped_data.json                                   │
│                 │                                           │
│            ingest.py                                        │
│         (Chunk → Embed)                                     │
│                 │                                           │
│     SentenceTransformer (all-MiniLM-L6-v2)                  │
│         [runs 100% locally]                                 │
│                 │                                           │
│           ChromaDB (local vector store)                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      QUERY PIPELINE                         │
│                    (Every user question)                    │
│                                                             │
│   User Question                                             │
│        │                                                    │
│        ▼                                                    │
│   Embed Query                                               │
│   (SentenceTransformer)                                     │
│        │                                                    │
│        ▼                                                    │
│   ChromaDB Similarity Search                                │
│   (Top 3 relevant chunks)                                   │
│        │                                                    │
│        ▼                                                    │
│   Build Prompt                                              │
│   (chunks + history + question)                             │
│        │                                                    │
│        ▼                                                    │
│   Groq LLM (llama-3.1-8b-instant)                           │
│        │                                                    │
│        ▼                                                    │
│   Answer + Sources + Guardrail Check                        │
│        │                                                    │
│        ▼                                                    │
│   Streamlit Chat UI                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- 💬 **Conversational chat** with follow-up question support
- 🔍 **Semantic search** across 300+ GitLab Handbook pages
- 📄 **Source previews** — see exactly which page and excerpt was used to answer
- 🚫 **Guardrails** — clearly flags when a question is out of scope
- 👍👎 **Feedback buttons** — thumbs up/down on every response
- 💡 **Suggested questions** — sidebar + inline prompts for new users
- 🗑️ **Clear chat** — reset the conversation anytime

---

## 🛠️ Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Scraping | `requests` + `BeautifulSoup` | Simple, reliable HTML parsing |
| Chunking | Custom word-overlap chunker | 500 words, 50 word overlap |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) | Local, free, no API limits |
| Vector Store | `ChromaDB` (persistent) | Zero setup, runs locally |
| LLM | Groq (llama-3.1-8b-instant) | 14,400 free requests/day, very fast |
| Frontend | `Streamlit` | Rapid chat UI with minimal code |
| Deployment | Streamlit Community Cloud | Free, 1-click from GitHub |

---

## 📁 Project Structure

```
gitlab-chatbot/
│
├── scrape.py            # Crawls GitLab Handbook sections + Direction page
├── ingest.py            # Chunks text, embeds, stores in ChromaDB
├── app.py               # Streamlit chat UI with RAG logic
│
├── chroma_db/           # Persisted vector store (auto-created by ingest.py)
├── scraped_data.json    # Raw scraped text (auto-created by scrape.py)
│
├── .env                 # Your API keys (never commit this)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/gitlab-chatbot.git
cd gitlab-chatbot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your API key

Create a `.env` file in the root folder:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq key at [console.groq.com](https://console.groq.com) — no credit card needed.

### 4. Scrape GitLab pages

```bash
python scrape.py
```

Scrapes 10 key handbook sections (up to 30 pages each) + the Direction page.
Creates `scraped_data.json`. Takes ~10-15 minutes.

### 5. Embed and store

```bash
python ingest.py
```

Chunks the scraped text, embeds using a local model, stores in ChromaDB.
Creates `chroma_db/`. Takes ~5-10 minutes. Downloads ~90MB model on first run.

### 6. Run the chatbot

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`

> ⚠️ Steps 4 and 5 only need to be run **once**. After that, just run step 6.

---

## 🚀 Deployment

Deployed on **Streamlit Community Cloud** at:
```
https://YOUR-APP-URL.streamlit.app
```

To deploy your own:
1. Push this repo to GitHub (make sure `chroma_db/` is committed)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select your repo and `app.py` as the main file
4. In **Advanced settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your_groq_key_here"
   ```
5. Click Deploy

---

## 📊 Data Coverage

| Handbook Section | Pages Scraped |
|---|---|
| Values | up to 30 |
| Company | up to 30 |
| Engineering | up to 30 |
| Product | up to 30 |
| People / HR | up to 30 |
| Finance | up to 30 |
| Marketing | up to 30 |
| Sales | up to 30 |
| Security | up to 30 |
| Legal | up to 30 |
| Direction page | 1 |
| **Total** | **~300 pages** |

> The GitLab Handbook has 4,500+ pages total. This project covers the most employee-relevant sections. Coverage can be expanded by increasing `MAX_PAGES_PER_SECTION` in `scrape.py`.

---

## ⚠️ Limitations

- Covers ~300 of 4,500+ handbook pages — some niche topics may not be found
- Knowledge is static — re-run `scrape.py` + `ingest.py` to refresh content
- Embedding model (`all-MiniLM-L6-v2`) is English-only
- LLM answers are grounded in retrieved chunks — it will not hallucinate but may miss context from unscraped pages

---

## 🔮 Possible Improvements

- Scheduled re-scraping to keep content fresh
- Expand to all 4,500+ handbook pages using Supabase pgvector
- Add query rewriting for better retrieval on vague questions
- Stream LLM responses token by token for faster perceived response
