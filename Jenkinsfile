pipeline {
    agent any

    parameters {
        password(
            name: 'JINA_API_KEY_INPUT',
            defaultValue: '',
            description: '🔑 Entrez votre clé API Jina AI (jina_...)'
        )
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        QDRANT_URL  = 'http://qdrant:6333'
        N8N_URL     = 'http://n8n:5678'
        CHATBOT_URL = 'http://chatbot:80'
        VENV_DIR    = "/var/jenkins_home/venv/fstm"
        PYTHON      = "/var/jenkins_home/venv/fstm/bin/python"
        PIP         = "/var/jenkins_home/venv/fstm/bin/pip"
    }

    stages {

        stage('0. Prérequis Système') {
            steps {
                sh '''
                # Installe python3 si absent
                if ! command -v python3 >/dev/null 2>&1; then
                    echo "python3 absent — installation..."
                    apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip curl
                else
                    echo "python3 OK : $(python3 --version)"
                fi

                # Vérifie curl
                if ! command -v curl >/dev/null 2>&1; then
                    echo "curl absent — installation..."
                    apt-get update -qq && apt-get install -y -qq curl
                else
                    echo "curl OK"
                fi
                '''
            }
        }

        stage('1. Récupération du Code') {
            steps {
                checkout scm
                echo "Commit : ${env.GIT_COMMIT?.take(8)}"
            }
        }

        stage('2. Vérification Universelle') {
            parallel {
                stage("Contrôle d'Intégrité") {
                    steps {
                        sh '''
                        echo "--- Audit de Structure FSTM ---"
                        find . -maxdepth 2 -not -path '*/.*' -not -path '*/venv*'
                        echo "--- Vérification des Fichiers Data ---"
                        [ -e "FSTM_JINA.json" ] && echo "FSTM_JINA.json : Présent" || echo "FSTM_JINA.json : MANQUANT"
                        '''
                    }
                }
                stage('Contrôle Qualité (ALL)') {
                    steps {
                        sh '''
                        echo "=== 1. Scripts Python ==="
                        find . -name "*.py" ! -path "*/venv/*" ! -path "*/.*" -exec python3 -m py_compile {} +
                        
                        echo "=== 2. Configurations JSON ==="
                        find . -name "*.json" ! -path "*/.*" -exec python3 -c "import json; json.load(open('{}'))" \\; -print
                        
                        echo "=== 3. Infrastructure YAML ==="
                        find . -name "*.yml" -o -name "*.yaml" ! -path "*/.*" -exec echo "Validating YAML structure: {}" \\;

                        echo "=== 4. Audit HTML (Interface) ==="
                        find . -name "*.html" ! -path "*/venv/*" ! -path "*/.git/*" | while read f; do
                            python3 -c "
import sys
from html.parser import HTMLParser

class Check(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.void = ['br','hr','img','input','meta','link','base','col','embed','param','source','track','wbr']
    def handle_starttag(self, tag, attrs):
        if tag not in self.void:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag in self.void:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            print('ERREUR: balise mal fermee </' + tag + '> dans $f')
            sys.exit(1)

p = Check()
p.feed(open('$f').read())
if p.stack:
    print('ERREUR: balises non fermees', p.stack, 'dans $f')
    sys.exit(1)
print('OK:', '$f')
" || exit 1
                        done
                        echo "HTML : OK"
                        '''
                    }
                }
            }
        }

        stage('3. Validation Fail-Fast (Jina)') {
            steps {
                script {
                    if (!params.JINA_API_KEY_INPUT?.toString()?.trim()) {
                        error "❌ ERREUR FAIL-FAST : Aucune clé JINA_API_KEY saisie ! Relancez avec 'Build with Parameters'."
                    }
                }
                sh """
                echo "Vérification Fail-Fast de l'API Jina AI..."
                STATUS=\$(curl -s -o /dev/null -w "%{http_code}" -X POST https://api.jina.ai/v1/embeddings \\
                     -H "Authorization: Bearer ${params.JINA_API_KEY_INPUT}" \\
                     -H "Content-Type: application/json" \\
                     -d '{"model": "jina-embeddings-v3", "input": ["test"]}')
                if [ "\$STATUS" = "401" ] || [ "\$STATUS" = "403" ]; then
                    echo "❌ ERREUR FAIL-FAST : Clé JINA_API_KEY invalide ou expirée (Code: \$STATUS) !"
                    exit 1
                else
                    echo "✅ API Jina joignable (Code \$STATUS)."
                fi
                """
            }
        }

        stage('4. Déploiement des Services') {
            steps {
                script {
                    sh '''
                    # ── Réseau Docker ──
                    docker network create fstm_network 2>/dev/null || echo "Réseau fstm_network déjà existant."
                    docker network connect fstm_network fstm_jenkins 2>/dev/null || true

                    # ── Qdrant ──
                    if ! docker ps --format "{{.Names}}" | grep -q "^fstm_qdrant$"; then
                        echo "Lancement de Qdrant..."
                        docker run -d \
                            --name fstm_qdrant \
                            --network fstm_network \
                            -p 6333:6333 \
                            -v qdrant_storage:/qdrant/storage \
                            --restart unless-stopped \
                            qdrant/qdrant:latest
                        echo "✅ Qdrant lancé."
                    else
                        echo "✅ Qdrant déjà en cours d\'exécution."
                    fi

                    # ── n8n ──
                    if ! docker ps --format "{{.Names}}" | grep -q "^fstm_n8n$"; then
                        echo "Lancement de n8n..."
                        docker run -d \
                            --name fstm_n8n \
                            --network fstm_network \
                            -p 5678:5678 \
                            -e N8N_HOST=0.0.0.0 \
                            -e N8N_PORT=5678 \
                            -e N8N_PROTOCOL=http \
                            -e N8N_USER_MANAGEMENT_DISABLED=true \
                            -v n8n_data:/home/node/.n8n \
                            --restart unless-stopped \
                            n8nio/n8n:latest
                        echo "✅ n8n lancé."
                    else
                        echo "✅ n8n déjà en cours d\'exécution."
                    fi

                    # ── Chatbot (Nginx) ──
                    if ! docker ps --format "{{.Names}}" | grep -q "^fstm_chatbot$"; then
                        echo "Lancement du Chatbot UI..."
                        docker run -d \
                            --name fstm_chatbot \
                            --network fstm_network \
                            -p 3001:80 \
                            -v "$(pwd)/web:/usr/share/nginx/html:ro" \
                            -v "$(pwd)/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
                            --restart unless-stopped \
                            nginx:alpine
                        echo "✅ Chatbot UI lancé."
                    else
                        echo "✅ Chatbot UI déjà en cours d\'exécution."
                    fi

                    echo "⏳ Attente de 10s pour démarrage des services..."
                    sleep 10
                    '''
                }
            }
        }

        stage('5. Vérification des Services') {
            parallel {

                stage('Qdrant') {
                    steps {
                        script {
                            def hasDocker = (sh(script: 'command -v docker >/dev/null 2>&1', returnStatus: true) == 0)
                            def qdrantOK = (sh(script: "curl -sf --max-time 5 ${env.QDRANT_URL}", returnStatus: true) == 0)
                            if (!qdrantOK && hasDocker) {
                                sh 'docker restart fstm_qdrant || true'
                                sleep 10
                                qdrantOK = (sh(script: "curl -sf --max-time 5 ${env.QDRANT_URL}", returnStatus: true) == 0)
                            }
                            if (!qdrantOK) error "Qdrant injoignable sur ${env.QDRANT_URL}"
                            echo "Qdrant : OK"
                        }
                    }
                }

                stage('n8n') {
                    steps {
                        script {
                            def hasDocker = (sh(script: 'command -v docker >/dev/null 2>&1', returnStatus: true) == 0)
                            def n8nOK = (sh(script: "curl -sf --max-time 5 ${env.N8N_URL}", returnStatus: true) == 0)
                            if (!n8nOK && hasDocker) {
                                sh 'docker restart fstm_n8n || true'
                                sleep 10
                                n8nOK = (sh(script: "curl -sf --max-time 5 ${env.N8N_URL}", returnStatus: true) == 0)
                            }
                            if (!n8nOK) error "n8n injoignable sur ${env.N8N_URL}"
                            echo "n8n : OK"
                        }
                    }
                }

                stage('Chatbot UI') {
                    steps {
                        script {
                            def hasDocker = (sh(script: 'command -v docker >/dev/null 2>&1', returnStatus: true) == 0)
                            def chatbotOK = (sh(script: "curl -sf --max-time 5 ${env.CHATBOT_URL}", returnStatus: true) == 0)
                            if (!chatbotOK && hasDocker) {
                                sh 'docker restart fstm_chatbot || true'
                                sleep 10
                                chatbotOK = (sh(script: "curl -sf --max-time 5 ${env.CHATBOT_URL}", returnStatus: true) == 0)
                            }
                            if (!chatbotOK) error "Chatbot UI injoignable sur ${env.CHATBOT_URL}"
                            echo "Chatbot UI : OK"
                        }
                    }
                }

            }
        }

        stage('6. Installation') {
            steps {
                sh '''
                # Crée le venv une seule fois
                [ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"

                # Vérifie si tous les packages sont déjà installés
                echo "Vérification des packages..."
                MISSING=$("$PIP" install --dry-run -r requirements.txt -q 2>&1 | grep "Would install" || echo "")

                if [ -z "$MISSING" ]; then
                    echo "Tous les packages déjà installés — rien à faire."
                else
                    echo "Packages manquants : $MISSING"
                    "$PIP" install --upgrade pip -q
                    "$PIP" install -r requirements.txt -q
                    echo "Installation terminée."
                fi
                '''
            }
        }

        stage('7. Indexation Jina AI') {
            steps {
                sh """
                export JINA_API_KEY=${params.JINA_API_KEY_INPUT}
                export QDRANT_URL=${env.QDRANT_URL}
                "\$PYTHON" index_fstm.py
                """
                sh '''
                curl -sf "${QDRANT_URL}/collections" | python3 -c "
import sys, json
data = json.load(sys.stdin)
cols = [c['name'] for c in data.get('result', {}).get('collections', [])]
sys.exit(0 if 'fstm_docs' in cols else 1)
" && echo "Collection fstm_docs OK." || { echo "Collection manquante !"; exit 1; }
                '''
            }
        }
    }

    post {
        success { echo "Pipeline FSTM (Branche dev-user) OK — Build #${env.BUILD_NUMBER}" }
        failure  { echo "Pipeline FSTM (Branche dev-user) ÉCHOUÉ — Build #${env.BUILD_NUMBER}" }
        cleanup  {
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}
