pipeline {
    agent any

    options {
        timeout(time: 15, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        QDRANT_URL   = 'http://qdrant:6333'
        N8N_URL      = 'http://n8n:5678'
        BOTPRESS_URL = 'https://cdn.botpress.cloud'
        PYTHON       = "${WORKSPACE}/venv/bin/python"
        PIP          = "${WORKSPACE}/venv/bin/pip"
    }

    stages {

        // 1. Téléchargement du code fstm-chatbot
        stage('1. Récupération du Code') {
            steps {
                checkout scm
                echo "Commit : ${env.GIT_COMMIT?.take(8)} — Projet FSTM"
            }
        }

        // 2. Vérifications en parallèle
        stage('2. Vérification') {
            parallel {
                stage('Fichiers FSTM') {
                    steps {
                        sh '''
                        MISSING=0
                        for FILE in index_fstm.py requirements.txt FSTM_JINA.json docker-compose.yml; do
                            if [ -e "$FILE" ]; then
                                echo "OK : $FILE"
                            else
                                echo "MANQUANT : $FILE"
                                MISSING=1
                            fi
                        done
                        [ "$MISSING" -eq 1 ] && exit 1 || echo "Fichiers FSTM complets."
                        '''
                    }
                }

                stage('Syntaxe Python') {
                    steps {
                        sh 'python3 -m py_compile index_fstm.py && echo "Syntaxe FSTM OK"'
                    }
                }

                stage('Requirements') {
                    steps {
                        sh '''
                        python3 << 'PYEOF'
import sys
with open('requirements.txt') as f:
    lines = [l for l in f if l.strip() and not l.startswith('#')]
if not lines:
    print("requirements.txt est vide !")
    sys.exit(1)
print(f"requirements.txt OK — {len(lines)} dependances")
PYEOF
                        '''
                    }
                }
            }
        }

        // 3. Vérification des Services (Identique à Wathiqa pour la robustesse)
        stage('3. Vérification des Services') {
            options { timeout(time: 5, unit: 'MINUTES') }
            steps {
                script {
                    // --- Docker Detection ---
                    def hasDocker = (sh(script: 'command -v docker >/dev/null 2>&1', returnStatus: true) == 0)
                    if (!hasDocker) {
                        echo "AVERTISSEMENT : Commande 'docker' introuvable dans Jenkins. L'auto-réparation est désactivée."
                    } else {
                        echo "Docker détecté. Vérification de l'accès..."
                        def dockerOK = (sh(script: 'docker ps', returnStatus: true) == 0)
                        if (!dockerOK) {
                            echo "AVERTISSEMENT : Docker est installé mais inaccessible (problème de permissions/socket)."
                            hasDocker = false
                        }
                    }

                    // --- Qdrant ---
                    def qdrantOK = (sh(script: "curl -sf --max-time 10 ${QDRANT_URL}", returnStatus: true) == 0)
                    if (!qdrantOK) {
                        if (hasDocker) {
                            echo "Qdrant KO — tentative de redémarrage via Docker..."
                            sh 'docker restart fstm_qdrant || true'
                            sleep 10
                            qdrantOK = (sh(script: "curl -sf --max-time 10 ${QDRANT_URL}", returnStatus: true) == 0)
                        } else {
                            echo "ERREUR : Qdrant est hors ligne et Docker est absent pour le redémarrer."
                        }
                        
                        if (!qdrantOK)
                            error "Qdrant est injoignable sur ${QDRANT_URL} — arrêt du pipeline."
                    }

                    // --- n8n ---
                    def n8nOK = (sh(script: "curl -sf --max-time 10 ${N8N_URL}", returnStatus: true) == 0)
                    if (!n8nOK) {
                        if (hasDocker) {
                            echo "n8n KO — tentative de redémarrage via Docker..."
                            sh 'docker restart fstm_n8n || true'
                            sleep 10
                            n8nOK = (sh(script: "curl -sf --max-time 10 ${N8N_URL}", returnStatus: true) == 0)
                        } else {
                            echo "ERREUR : n8n est hors ligne et Docker est absent pour le redémarrer."
                        }

                        if (!n8nOK)
                            error "n8n est injoignable sur ${N8N_URL} — arrêt du pipeline."
                    }

                    // --- Botpress (Non-bloquant) ---
                    def botpressOK = false
                    for (int i = 1; i <= 3; i++) {
                        botpressOK = (sh(script: "curl -sf --max-time 10 ${BOTPRESS_URL}", returnStatus: true) == 0)
                        if (botpressOK) break
                        echo "Botpress KO (tentative ${i}/3)..."
                        sleep 5
                    }
                    if (!botpressOK)
                        echo "AVERTISSEMENT : Botpress injoignable (non bloquant)."

                    echo "Infrastructure FSTM vérifiée."
                }
            }
        }

        // 4. Installation de l'environnement FSTM
        stage('4. Installation') {
            options { timeout(time: 5, unit: 'MINUTES') }
            steps {
                sh '''
                [ ! -f "$PYTHON" ] && python3 -m venv venv
                "$PIP" install --upgrade pip --quiet
                "$PIP" install -r requirements.txt --quiet
                '''
            }
        }

        // 5. Indexation FSTM via Jina AI
        stage('5. Indexation Jina AI') {
            options { timeout(time: 10, unit: 'MINUTES') }
            steps {
                // Utilise la clé JINA_API_KEY stockée dans Jenkins
                withCredentials([string(credentialsId: 'JINA_API_KEY', variable: 'JINA_API_KEY')]) {
                    sh '''
                    export JINA_API_KEY=$JINA_API_KEY
                    export QDRANT_URL=$QDRANT_URL
                    "$PYTHON" index_fstm.py
                    '''
                }

                // Vérification post-indexation (collection: fstm_docs)
                sh '''
                COLLECTIONS=$(curl -sf "${QDRANT_URL}/collections" | python3 -c "
import sys, json
data = json.load(sys.stdin)
cols = [c['name'] for c in data.get('result', {}).get('collections', [])]
print(1 if 'fstm_docs' in cols else 0)
")
                [ "$COLLECTIONS" -eq 1 ] && echo "Collection 'fstm_docs' vérifiée." || { echo "Collection FSTM manquante après indexation !"; exit 1; }
                '''
            }
        }
    }

    post {
        success { echo "FSTM Pipeline terminé avec succès." }
        failure { echo "Échec du pipeline FSTM." }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true,
                    patterns: [[pattern: 'venv/**', type: 'EXCLUDE']])
        }
    }
}
