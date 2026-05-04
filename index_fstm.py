"""
FSTM Indexation — Indexe les fichiers texte locaux dans Qdrant via Jina v3
===========================================================================
Usage:
    pip install qdrant-client requests
    python index_fstm.py
"""

import os
import requests
import json
import uuid
import glob
import time
from qdrant_client import QdrantClient
from qdrant_client.http import models

# ── Config (via variables d'environnement) ──
JINA_API_KEY   = os.environ.get("JINA_API_KEY", "")
QDRANT_URL     = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION     = "fstm_docs"
JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
VECTOR_DIM     = 768

# Liste des dossiers à indexer (TOUTES les sources)
DATA_SOURCES = [
    "./fstm_data",
    "./fstm_scraped",
    "./fstm_data/pdf_texts"
]


def get_embeddings(texts: list) -> list:
    """Obtient les embeddings pour une liste de textes via Jina AI."""
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "jina-embeddings-v3",
        "task": "text-matching",
        "dimensions": VECTOR_DIM,
        "input": texts
    }
    try:
        resp = requests.post(JINA_EMBED_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429:
            print(f"  ⏱️  Rate limit (429) — pause...")
            return None
        if resp.status_code != 200:
            print(f"❌ Erreur Jina ({resp.status_code}): {resp.text}")
            return None
        return [item["embedding"] for item in resp.json()["data"]]
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return None


def chunk_text(text: str, max_chars=1200) -> list[str]:
    """Découpage intelligent par paragraphes."""
    paragraphs = text.split("\n\n")
    if len(paragraphs) <= 1:
        paragraphs = text.split("\n")

    chunks = []
    current = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i : i + max_chars])
            continue
        if len(current) + len(p) < max_chars:
            current += p + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]


def parse_file(path: str) -> dict:
    """Lit un fichier et prépare le contenu."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Titre propre basé sur le nom du fichier
        title = os.path.basename(path).replace(".txt", "").replace("_", " ").title()

        # Si c'est un fichier scrapé, on cherche le tag [TITLE]
        if "[TITLE]" in content:
            title_part = content.split("\n", 1)[0]
            title = title_part.replace("[TITLE]", "").strip()
            if "[CONTENT]" in content:
                content = content.split("[CONTENT]", 1)[1].strip()

        return {"title": title, "content": content, "source": path}
    except Exception as e:
        print(f"  ⚠️ Ignoré {path}: {e}")
        return None


def main():
    if not JINA_API_KEY:
        print("❌ Erreur : JINA_API_KEY manquante.")
        print("   Définissez-la : export JINA_API_KEY=votre_clé")
        return

    client = QdrantClient(url=QDRANT_URL)
    print(f"🔧 Super-Indexation : Recréation collection ({COLLECTION}) {VECTOR_DIM} dims...")
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=VECTOR_DIM, distance=models.Distance.COSINE),
    )

    # 1. Collecter TOUS les chunks de TOUTES les sources
    total_chunks = []
    for source_dir in DATA_SOURCES:
        if not os.path.exists(source_dir):
            continue
        files = glob.glob(os.path.join(source_dir, "**/*.txt"), recursive=True)
        print(f"📂 {len(files)} fichiers dans {source_dir}")

        for f in files:
            data = parse_file(f)
            if not data or len(data["content"]) < 30:
                continue

            chunks = chunk_text(data["content"])
            for chunk in chunks:
                total_chunks.append({
                    "content": chunk,
                    "title": data["title"],
                    "source": data["source"]
                })

    print(f"📝 {len(total_chunks)} segments totaux identifiés.")

    # 2. Indexation par lots (Batching par 100 pour la vitesse)
    batch_size = 100
    for i in range(0, len(total_chunks), batch_size):
        batch = total_chunks[i : i + batch_size]
        texts = [item["content"][:2500] for item in batch]

        print(f" ↗️  Traitement lot {i//batch_size + 1}... ", end="", flush=True)

        # Système de Retry pour le Rate Limit (429)
        max_retries = 3
        embeddings = None
        for attempt in range(max_retries):
            embeddings = get_embeddings(texts)
            if embeddings:
                break
            print(f" (⏱️ Tentative {attempt+1} échouée, pause...) ", end="", flush=True)
            time.sleep(10)  # Grosse pause en cas d'erreur

        if embeddings:
            points = []
            for j, emb in enumerate(embeddings):
                points.append(models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload={
                        "title": batch[j]["title"],
                        "content": batch[j]["content"],
                        "source": batch[j]["source"]
                    }
                ))
            client.upsert(collection_name=COLLECTION, points=points)
            print("✅")
        else:
            print("❌ Échec définitif du lot.")

        # Pause de précaution (Éviter 429) mais réduite pour la vitesse
        time.sleep(1.0)

    print(f"\n🎉 INDEXATION TERMINÉE ! {len(total_chunks)} segments indexés.")


if __name__ == "__main__":
    main()
