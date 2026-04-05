import json
import os
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "gitlab_docs"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
BATCH_SIZE = 100


def chunk_text(text, url):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        chunks.append({"text": chunk, "url": url})
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def batch(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def main():
    print("Loading scraped_data.json...")
    with open("scraped_data.json", "r", encoding="utf-8") as f:
        pages = json.load(f)
    print(f"Loaded {len(pages)} pages.")

    print("Chunking text...")
    all_chunks = []
    for page in pages:
        all_chunks.extend(chunk_text(page["text"], page["url"]))
    print(f"Total chunks: {len(all_chunks)}")

    # Local embedding model — no API, no rate limits, no version issues
    print("Loading local embedding model (downloads ~90MB on first run)...")
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    print("Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
        print("Deleted existing collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    print(f"Embedding and storing in batches of {BATCH_SIZE}...")
    for i, b in enumerate(batch(all_chunks, BATCH_SIZE)):
        documents = [c["text"] for c in b]
        metadatas = [{"url": c["url"]} for c in b]
        ids = [f"chunk_{i * BATCH_SIZE + j}" for j in range(len(b))]

        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"  Batch {i+1}/{-(-len(all_chunks)//BATCH_SIZE)} done")

    print(f"\nDone! {len(all_chunks)} chunks stored in {CHROMA_PATH}")


if __name__ == "__main__":
    main()