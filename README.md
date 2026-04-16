# 🎓 FSTM Chatbot — Guide de Déploiement du Portail Étudiant Intelligent

> **Solution RAG (Retrieval-Augmented Generation) pour la Faculté des Sciences et Techniques de Mohammedia.**

Ce projet est un écosystème complet permettant de répondre aux questions des étudiants en se basant sur les documents officiels de la FSTM. Il combine scraping automatisé, recherche sémantique vectorielle et une interface web moderne.

---

## 🏗️ 1. Architecture & Services

Le projet est entièrement conteneurisé via Docker Compose :

| Service | Image | Rôle | Port |
|---------|-------|------|------|
| **Chatbot UI** | `nginx:alpine` | Interface Web (HTML/JS) | `3001` |
| **n8n** | `docker.n8n.io/n8nio/n8n` | Orchestration du pipeline RAG | `5678` |
| **Qdrant** | `qdrant/qdrant` | Base de données vectorielle | `6333` |

---

## 🚀 2. Installation Manuelle Détaillée

### 2.1. Prérequis
- **Docker & Docker Compose** installés sur votre machine (Windows via Docker Desktop).
- Clé API **Jina AI** (pour les embeddings 768 dim).
- Clé API **Groq** (pour le modèle LLaMA 3.1 8B).

### 2.2. Lancement de l'infrastructure
1.  **Clonage** :
    ```bash
    git clone https://github.com/iamsamahaziz/fstm-chatbot.git
    cd fstm-chatbot
    ```
2.  **Configuration des clés** :
    *   Créez un fichier `.env` à la racine (copiez `.env.example`).
    *   Ajoutez `JINA_API_KEY` et `GROQ_API_KEY`.
3.  **Démarrage** :
    ```bash
    docker compose up -d
    ```
    *Vérifiez les conteneurs avec `docker ps`. Tous doivent être sur "Up".*

---

## 🔍 3. Pilotage de la Base de Connaissances

### 3.1. Scraping & Indexation (Outils Python)
Si vous voulez mettre à jour les données (nouvel emploi du temps, nouvelles annales) :
1.  **Installation de l'outil** :
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install qdrant-client requests beautifulsoup4 pymupdf
    ```
2.  **Lancement du scraping** :
    ```bash
    python scrape_and_index.py
    ```
    *Le script va parcourir le site de la FSTM, télécharger les PDF et les indexer dans Qdrant.*

### 3.2. Configuration du Cerveau (n8n)
1.  Accédez à `http://localhost:5678`.
2.  Importez le fichier `FSTM_JINA.json`.
3.  Vérifiez que le **Webhook** est actif et que les nœuds Mistral/Qdrant utilisent bien votre clé Jina et l'URL `http://qdrant:6333`.

---

## 📂 4. Fonctionnalités Étudiantes
- 🤖 **Orientations** : L'agent IA peut conseiller parmi les 26 filières de la FSTM.
- 📁 **Annales** : Accès direct aux archives d'examens classées par semestre.
- 🏫 **Annuaire** : Recherche rapide de contacts enseignants par département.

---
**Auteur** : Samah AZIZ
**Institution** : FST Mohammedia - Université Hassan II de Casablanca - 2026
