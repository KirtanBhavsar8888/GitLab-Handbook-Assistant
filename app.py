import os
import time
import streamlit as st
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHROMA_PATH = str(Path(__file__).parent / "chroma_db")
COLLECTION_NAME = "gitlab_docs"
OUT_OF_SCOPE_PHRASE = "I don't have information about this in the GitLab Handbook."

SUGGESTED_QUESTIONS = [
    "What are GitLab's core values?",
    "How does GitLab handle code reviews?",
    "What is GitLab's remote work policy?",
    "How does GitLab prioritize product features?",
    "What is GitLab's vision for the future?",
    "How does GitLab handle time off and vacation?",
]

if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found in .env file.")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="GitLab Handbook Assistant", page_icon="🦊", layout="centered")
st.title("🦊 GitLab Handbook Assistant")
st.caption("Ask anything about GitLab's Handbook or Product Direction.")


@st.cache_resource
def load_collection():
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)


try:
    collection = load_collection()
except Exception as e:
    st.error(f"Failed to load ChromaDB: {e}\nMake sure you have run scrape.py and ingest.py first.")
    st.stop()


def call_llm(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content


def get_answer(query: str, chat_history: list) -> tuple[str, list[str], list[str]]:
    results = collection.query(query_texts=[query], n_results=3)
    chunks = results["documents"][0]
    sources = [m["url"] for m in results["metadatas"][0]]

    if not chunks:
        return OUT_OF_SCOPE_PHRASE, [], []

    context = "\n\n---\n\n".join(chunks)

    history_text = ""
    for msg in chat_history[-4:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""You are a helpful assistant for GitLab employees and candidates.
Answer the question using ONLY the context provided below.
If the answer is not found in the context, clearly say: "{OUT_OF_SCOPE_PHRASE}"
Do not make up information.

Context from GitLab Handbook/Direction:
{context}

Previous conversation:
{history_text}

Current question: {query}

Answer:"""

    answer = call_llm(prompt)

    # Deduplicate sources while preserving order
    seen = {}
    for url, chunk in zip(sources, chunks):
        if url not in seen:
            seen[url] = chunk
    unique_sources = list(seen.keys())
    unique_previews = [seen[url] for url in unique_sources]

    return answer, unique_sources, unique_previews


def is_out_of_scope(answer: str) -> bool:
    return OUT_OF_SCOPE_PHRASE.lower() in answer.lower()


def show_assistant_message(msg: dict, idx: int):
    answer = msg["content"]
    sources = msg.get("sources", [])
    previews = msg.get("previews", [])

    # Guardrail badge
    if is_out_of_scope(answer):
        st.warning("🚫 **Out of Scope** — This question is outside the GitLab Handbook content.", icon="🚫")

    st.markdown(answer)

    # Source page previews
    if sources:
        with st.expander("📄 Sources & Previews"):
            for i, url in enumerate(sources):
                st.markdown(f"**[{url}]({url})**")
                if i < len(previews) and previews[i]:
                    preview_text = previews[i][:200].strip().replace("\n", " ")
                    st.caption(f"_{preview_text}..._")
                st.divider()

    # Thumbs feedback
    feedback = st.session_state.feedback.get(idx)
    if feedback is None:
        col1, col2, col3 = st.columns([1, 1, 10])
        with col1:
            if st.button("👍", key=f"up_{idx}", help="Helpful"):
                st.session_state.feedback[idx] = "up"
                st.rerun()
        with col2:
            if st.button("👎", key=f"down_{idx}", help="Not helpful"):
                st.session_state.feedback[idx] = "down"
                st.rerun()
    elif feedback == "up":
        st.success("✅ Thanks for the feedback!", icon="✅")
    elif feedback == "down":
        st.error("❌ Thanks! We'll work on improving this.", icon="❌")


def handle_query(query: str):
    """Central function to process a query and update session state."""
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.pending_query = query


# ── Session state init ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback" not in st.session_state:
    st.session_state.feedback = {}
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# ── Sidebar — Suggested Questions ─────────────────────────────────────────────
with st.sidebar:
    st.header("💡 Suggested Questions")
    st.caption("Click any question to ask it directly.")
    for q in SUGGESTED_QUESTIONS:
        if st.button(q, use_container_width=True):
            handle_query(q)
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.feedback = {}
        st.session_state.pending_query = None
        st.rerun()

# ── Render existing messages ──────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            show_assistant_message(msg, i)
        else:
            st.markdown(msg["content"])

# ── Show suggested questions inline if chat is empty ─────────────────────────
if not st.session_state.messages:
    st.markdown("#### 👋 Not sure where to start? Try one of these:")
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTED_QUESTIONS):
        with cols[i % 2]:
            if st.button(q, key=f"inline_{i}", use_container_width=True):
                handle_query(q)
                st.rerun()

# ── Process pending query (from sidebar or inline buttons) ────────────────────
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=True) as status:
            st.write("🔍 Searching the GitLab Handbook...")
            time.sleep(1.5)
            st.write("📚 Reading relevant sections...")
            time.sleep(1.5)
            st.write("✍️ Composing answer...")
            time.sleep(1)
            try:
                answer, sources, previews = get_answer(query, st.session_state.messages)
            except Exception as e:
                answer = f"Sorry, something went wrong: {e}"
                sources = []
                previews = []
            status.update(label="Done!", state="complete", expanded=False)

        new_idx = len(st.session_state.messages)
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "previews": previews,
        })
        show_assistant_message(st.session_state.messages[-1], new_idx)

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about GitLab's handbook or product direction..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=True) as status:
            st.write("🔍 Searching the GitLab Handbook...")
            time.sleep(1.5)
            st.write("📚 Reading relevant sections...")
            time.sleep(1.5)
            st.write("✍️ Composing answer...")
            time.sleep(1)
            try:
                answer, sources, previews = get_answer(prompt, st.session_state.messages)
            except Exception as e:
                answer = f"Sorry, something went wrong: {e}"
                sources = []
                previews = []
            status.update(label="Done!", state="complete", expanded=False)

        new_idx = len(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "previews": previews,
        })
        show_assistant_message(st.session_state.messages[-1], new_idx)