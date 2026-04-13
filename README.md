# 🎓 FSTM Chatbot — Portail Étudiant Intelligent

Chatbot RAG (Retrieval-Augmented Generation) pour la **Faculté des Sciences et Techniques de Mohammedia**.  
Architecture complète avec scraping automatique, base vectorielle et interface web moderne.

## 📋 Architecture

```
Question utilisateur
    │
    ▼
[Interface Web] → [Webhook n8n] → [Jina v3 Embedding] → [Qdrant Search] → [Groq LLM] → Réponse
     :3001              :5678           768 dims               :6333
```

**Stack technique :**
| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Embeddings | **Jina v3** (768 dim) | Vectorisation des textes |
| Vector DB | **Qdrant** | Recherche sémantique |
| LLM | **Groq** (LLaMA 3.1 8B) | Génération de réponses |
| Orchestrateur | **n8n** | Workflow RAG complet |
| Frontend | **HTML/CSS/JS** | Interface chatbot responsive |
| Infra | **Docker Compose + Nginx** | Déploiement conteneurisé |

## 🚀 Installation

### 1. Cloner et configurer

```bash
git clone https://github.com/<votre-username>/fstm-chatbot.git
cd fstm-chatbot
cp .env.example .env
# Éditez .env avec vos clés API
```

### 2. Lancer les services

```bash
docker compose up -d
```

Services démarrés :
| Service | URL | Port |
|---------|-----|------|
| Qdrant | `http://localhost:6333` | 6333 |
| n8n | `http://localhost:5678` | 5678 |
| Chatbot UI | `http://localhost:3001` | 3001 |

### 3. Indexer les données

```bash
pip install qdrant-client requests beautifulsoup4 pymupdf
python scrape_and_index.py
```

Ce script :
- Scrape toutes les pages de fstm.ac.ma
- Télécharge et extrait le texte des PDFs
- Indexe le tout dans Qdrant via Jina v3 (chunks de 1200 chars, batches de 20)

### 4. Importer le workflow n8n

1. Ouvrir `http://localhost:5678`
2. Menu → **Import workflow** → `workflow_n8n.json`
3. Configurer les credentials (Jina, Groq, Qdrant)
4. **Activer** le workflow
5. Tester sur `http://localhost:3001` 🎉

## 📂 Structure du projet

```
fstm-chatbot/
├── docker-compose.yml      # 3 services : Qdrant + n8n + Nginx
├── nginx.conf              # Proxy + serveur statique
├── .env.example            # Variables d'environnement (template)
├── .gitignore              # Fichiers exclus du repo
├── index_fstm.py           # Indexation fichiers locaux → Qdrant
├── scrape_and_index.py     # Scraping complet + indexation
├── README.md               # Ce fichier
└── web/
    ├── index.html          # Interface chatbot (fichier unique)
    └── logo.png            # Logo FSTM
```

## 🔐 Variables d'environnement

| Variable | Description | Exemple |
|----------|------------|---------|
| `JINA_API_KEY` | Clé API Jina AI | `jina_xxx...` |
| `N8N_ENCRYPTION_KEY` | Clé de chiffrement n8n | `une_clé_secrète` |
| `QDRANT_URL` | URL Qdrant | `http://localhost:6333` |

> ⚠️ **Aucune clé API n'est stockée dans le code.** Tout passe par les variables d'environnement.

## 🔧 Scripts Python

### `index_fstm.py`
Indexe les fichiers `.txt` locaux (dossiers `fstm_data/`, `fstm_scraped/`) dans Qdrant.
- Chunking intelligent : 1200 caractères max
- Batching : 20 segments par requête
- Retry automatique sur erreur 429 (rate limit)

### `scrape_and_index.py`
Pipeline complet : scraping du site FSTM + extraction PDF + indexation.
- 60+ pages scrapées
- Extraction automatique des PDFs
- Sauvegarde locale + indexation Qdrant

## 📊 Fonctionnalités du portail

- 🤖 **Chatbot IA** — Questions/réponses sur la FSTM
- 📄 **Annales d'examens** — Téléchargement direct PDF
- 👨‍🏫 **Annuaire enseignants** — Par département
- 📅 **Emplois du temps** — Par filière et semestre
- 🧠 **Agent IA d'orientation** — Recommandation de filières

## 🛠️ Webhook n8n

Le chatbot communique avec n8n via :
```
POST /webhook/fstm-chat
Content-Type: application/json

{"question": "Quelles sont les filières LST ?"}
```

## 📄 Licence

Projet éducatif — Faculté des Sciences et Techniques de Mohammedia  
Université Hassan II de Casablanca
