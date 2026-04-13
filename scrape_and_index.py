"""
FSTM Scraper Complet — Scrape TOUTES les pages + PDFs + Indexation Qdrant
==========================================================================
Ce script :
1. Scrape toutes les pages HTML du site fstm.ac.ma
2. Télécharge et extrait le texte de tous les PDFs
3. Indexe tout dans Qdrant avec Jina v3

Usage:
    pip install requests beautifulsoup4 pymupdf qdrant-client
    python scrape_and_index.py
"""

import os, re, time, json, hashlib, requests, glob
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("⚠️  pymupdf non installé — les PDFs seront ignorés")
    print("   Installe-le : pip install pymupdf")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# ══════════════════════════════════════════
# CONFIG — Tout via variables d'environnement
# ══════════════════════════════════════════
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
QDRANT_URL   = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION   = "fstm_docs"
VECTOR_DIM   = 768
BASE_URL     = "https://www.fstm.ac.ma"
OUTPUT_DIR   = "./fstm_scraped"
PDF_DIR      = "./fstm_pdfs"

# ══════════════════════════════════════════
# PAGES À SCRAPER
# ══════════════════════════════════════════
PAGES_TO_SCRAPE = [
    # Institution
    "/", "/presentation.php", "/mot_doyenne.php", "/missions_et_valeurs.php",
    "/contact.php", "/mobilite.php", "/e_services.php", "/divers.php",
    "/organisation_generale/organigramme_fonctionnel.php",
    "/organisation_generale/conseil_etablissement.php",
    "/organisation_generale/commissions.php",
    "/organisation_generale/charges_de_missions.php",

    # Départements
    "/departements/presentation.php",
    "/departements/biologie.php", "/departements/chimie.php",
    "/departements/gpe.php", "/departements/ge.php",
    "/departements/informatique.php", "/departements/mathematiques.php",
    "/departements/physique.php", "/departements/tec.php",

    # Formation initiale
    "/formation_initiale/presentation.php",
    "/formation_initiale/architecture_pedagogique.php",
    "/formation_initiale/textes_et_lois.php",
    "/formation_initiale/tronc_commun.php",
    "/formation_initiale/lst.php",
    "/formation_initiale/mst.php",
    "/formation_initiale/ci.php",
    "/formation_initiale/cd.php",

    # Formation continue
    "/formation_continue/presentation.php",
    "/formation_continue/lu.php",
    "/formation_continue/mu.php",
    "/formation_continue/frais.php",
    "/formation_continue/dossier_preinscription.php",

    # Centres de certification
    "/centres_de_certification/presentation.php",

    # Recherche
    "/recherche/presentation.php",
    "/recherche/laboratoires.php",
    "/recherche/evenements_scientifiques.php",
    "/recherche/cedoc.php",
    "/recherche/cooperation.php",
    "/recherche/appelaprojets.php",

    # Affaires pédagogiques
    "/affaires_pedagogiques/affaires_pedagogiques.php",
    "/affaires_pedagogiques/porte_documents.php",

    # Vie estudiantine
    "/vie_estudiantine/activites.php",
    "/vie_estudiantine/projets.php",
    "/vie_estudiantine/journee_accueil.php",
    "/vie_estudiantine/journee_laureats.php",
    "/vie_estudiantine/association_des_etudiants.php",
    "/vie_estudiantine/association_des_laureats.php",

    # Entreprise et carrière
    "/entreprise_et_carriere/forum_fstm_entreprises.php",

    # Recrutement
    "/recrutement/concours.php",
    "/recrutement/resultats.php",

    # Actualités
    "/actualites/actualites.php",
    "/actualites/bulletin_d_information.php",
    "/actualites/presse.php",

    # Marchés publics
    "/marches_publics.php",
]

# ══════════════════════════════════════════
# FONCTIONS
# ══════════════════════════════════════════
session = requests.Session()
session.headers.update({
    "User-Agent": "FSTM-Chatbot-Scraper/1.0 (educational project)"
})

visited_urls = set()
all_pdf_urls = set()
all_documents = []


def clean_text(html_text):
    """Nettoyer le HTML pour extraire le texte propre."""
    soup = BeautifulSoup(html_text, "html.parser")

    # Supprimer nav, footer, header, scripts, styles
    for tag in soup.find_all(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Nettoyer les lignes vides multiples
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)

    return text


def extract_pdf_links(html_text, page_url):
    """Extraire tous les liens PDF d'une page HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    pdfs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            full_url = urljoin(page_url, href)
            if "fstm.ac.ma" in full_url:
                pdfs.add(full_url)
    return pdfs


def scrape_page(path):
    """Scraper une page et extraire texte + liens PDF."""
    url = BASE_URL + path if not path.startswith("http") else path

    if url in visited_urls:
        return None
    visited_urls.add(url)

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
    except Exception as e:
        print(f"  ⚠️  Erreur {path}: {e}")
        return None

    # Extraire texte
    text = clean_text(html)

    # Extraire liens PDF
    pdfs = extract_pdf_links(html, url)
    all_pdf_urls.update(pdfs)

    # Extraire titre
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else path

    return {
        "title": title,
        "url": url,
        "path": path,
        "text": text,
        "pdf_count": len(pdfs),
    }


def download_and_extract_pdf(url):
    """Télécharger un PDF et extraire son texte."""
    if not HAS_PYMUPDF:
        return None

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()

        # Sauvegarder le PDF
        filename = hashlib.md5(url.encode()).hexdigest()[:12] + ".pdf"
        filepath = os.path.join(PDF_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(resp.content)

        # Extraire le texte avec PyMuPDF
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()

        text = text.strip()
        if len(text) < 50:
            return None

        # Deviner le titre depuis l'URL
        url_path = urlparse(url).path
        title = os.path.basename(url_path).replace(".pdf", "").replace("_", " ").replace("%20", " ")

        return {
            "title": f"PDF: {title}",
            "url": url,
            "path": url_path,
            "text": text,
            "pdf_count": 0,
        }

    except Exception as e:
        print(f"  ⚠️  Erreur PDF {url[:80]}: {e}")
        return None


def chunk_text(text, max_chars=1200):
    """Découper le texte en chunks."""
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) < max_chars:
            current += p + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_chars]]


def jina_embed(texts):
    """Embed avec Jina v3 — retry automatique sur 429."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {JINA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "jina-embeddings-v3",
                    "task": "text-matching",
                    "dimensions": VECTOR_DIM,
                    "input": texts,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  ⏱️  Rate limit (429), pause {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return [d["embedding"] for d in resp.json()["data"]]
        except requests.exceptions.HTTPError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  ⚠️  Erreur réseau, retry... ({e})")
                time.sleep(5)
            else:
                raise
    raise Exception("Rate limit persistant après 3 tentatives")


# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════
def main():
    if not JINA_API_KEY:
        print("❌ Erreur : JINA_API_KEY manquante.")
        print("   Définissez-la : export JINA_API_KEY=votre_clé")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)

    # ── ÉTAPE 1 : Scraper les pages HTML ──
    print("=" * 60)
    print("  ÉTAPE 1 : Scraping des pages HTML")
    print("=" * 60)

    for i, path in enumerate(PAGES_TO_SCRAPE):
        print(f"  [{i+1}/{len(PAGES_TO_SCRAPE)}] {path}")
        doc = scrape_page(path)
        if doc and len(doc["text"]) > 50:
            all_documents.append(doc)
            # Sauvegarder en fichier texte
            safe_name = path.strip("/").replace("/", "_").replace(".php", "") or "accueil"
            with open(os.path.join(OUTPUT_DIR, f"{safe_name}.txt"), "w", encoding="utf-8") as f:
                f.write(f"[TITLE] {doc['title']}\n[URL] {doc['url']}\n[CONTENT]\n{doc['text']}")
        time.sleep(0.3)

    print(f"\n✅ {len(all_documents)} pages scrapées")
    print(f"📎 {len(all_pdf_urls)} liens PDF trouvés")

    # ── ÉTAPE 2 : Télécharger et extraire les PDFs ──
    print("\n" + "=" * 60)
    print("  ÉTAPE 2 : Téléchargement et extraction des PDFs")
    print("=" * 60)

    pdf_docs = []
    pdf_list = sorted(all_pdf_urls)
    for i, url in enumerate(pdf_list):
        print(f"  [{i+1}/{len(pdf_list)}] {os.path.basename(urlparse(url).path)[:60]}")
        doc = download_and_extract_pdf(url)
        if doc:
            pdf_docs.append(doc)
            all_documents.append(doc)
        time.sleep(0.3)

    print(f"\n✅ {len(pdf_docs)} PDFs extraits avec succès")

    # Sauvegarder aussi les anciens fichiers fstm_data s'ils existent
    if os.path.isdir("./fstm_data"):
        print("\n📂 Ajout des fichiers existants dans fstm_data/...")
        for path in glob.glob("./fstm_data/**/*.txt", recursive=True):
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            if len(text) > 50:
                title = os.path.basename(path).replace(".txt", "")
                all_documents.append({
                    "title": title,
                    "url": "",
                    "path": path,
                    "text": text,
                    "pdf_count": 0,
                })
        print(f"  ✅ Total documents : {len(all_documents)}")

    # ── ÉTAPE 3 : Indexer dans Qdrant ──
    print("\n" + "=" * 60)
    print("  ÉTAPE 3 : Indexation dans Qdrant avec Jina v3")
    print("=" * 60)

    qdrant = QdrantClient(url=QDRANT_URL)

    # Reset collection
    try:
        qdrant.delete_collection(COLLECTION)
    except Exception:
        pass
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"✅ Collection '{COLLECTION}' créée\n")

    # Build chunks
    all_chunks = []
    for doc in all_documents:
        text = doc["text"]
        # Extraire le contenu après [CONTENT] si présent
        if "[CONTENT]" in text:
            text = text.split("[CONTENT]", 1)[1].strip()

        for i, chunk in enumerate(chunk_text(text)):
            if len(chunk) < 40:
                continue
            all_chunks.append({
                "text": chunk,
                "title": doc["title"],
                "url": doc.get("url", ""),
                "source": doc.get("path", ""),
                "chunk_idx": i,
            })

    print(f"📝 {len(all_chunks)} chunks à indexer\n")

    # Embed + insert (batching par 20)
    BATCH = 20
    point_id = 0
    total_batches = (len(all_chunks) - 1) // BATCH + 1

    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i:i + BATCH]
        texts = [c["text"][:2000] for c in batch]

        try:
            embeddings = jina_embed(texts)
        except Exception as e:
            print(f"  ❌ Skip batch {i//BATCH+1}: {e}")
            continue

        points = []
        for c, emb in zip(batch, embeddings):
            points.append(PointStruct(
                id=point_id,
                vector=emb,
                payload={
                    "title": c["title"],
                    "content": c["text"],
                    "url": c.get("url", ""),
                    "source": c.get("source", ""),
                    "chunk": c["chunk_idx"],
                },
            ))
            point_id += 1

        qdrant.upsert(collection_name=COLLECTION, points=points)
        print(f"  ✅ Batch {i//BATCH+1}/{total_batches} — {len(points)} chunks")
        time.sleep(0.4)

    # ── RÉSUMÉ ──
    print("\n" + "=" * 60)
    print("  🎉 SCRAPING + INDEXATION TERMINÉS !")
    print("=" * 60)
    print(f"  📄 Pages HTML scrapées : {len(all_documents) - len(pdf_docs)}")
    print(f"  📎 PDFs extraits       : {len(pdf_docs)}")
    print(f"  📝 Chunks indexés      : {point_id}")
    print(f"  💾 Fichiers sauvegardés: {OUTPUT_DIR}/ et {PDF_DIR}/")
    print(f"\n  🚀 Teste sur http://localhost:3001")
    print("=" * 60)


if __name__ == "__main__":
    main()
