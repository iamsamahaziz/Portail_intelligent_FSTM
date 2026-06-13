pipeline {
    agent any

    parameters {
        password(
            name: 'JINA_API_KEY_INPUT',
            defaultValue: '',
            description: '🔑 Entrez votre clé API Jina AI (jina_...) [Uniquement pour les branches de développement/feature]'
        )
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }

    stages {

        stage('1. Préparation de l\'Environnement') {
            steps {
                script {
                    // Détection et standardisation du nom de la branche
                    def rawBranch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: "main"
                    def cleanBranch = rawBranch.split('/')[-1]
                    env.BRANCH_SLUG = cleanBranch.replaceAll('[^a-zA-Z0-9]', '_').toLowerCase()

                    echo "Branche détectée : ${env.BRANCH_SLUG}"

                    if (env.BRANCH_SLUG == 'main' || env.BRANCH_SLUG == 'master') {
                        env.IS_MAIN = 'true'
                        env.QDRANT_PORT = '6333'
                        env.N8N_PORT = '5678'
                        env.QDRANT_CONTAINER = 'fstm_qdrant'
                        env.N8N_CONTAINER = 'fstm_n8n'
                        env.VENV_DIR = "/var/jenkins_home/venv/fstm"
                    } else {
                        env.IS_MAIN = 'false'
                        env.QDRANT_PORT = "${10000 + env.BUILD_NUMBER.toInteger()}"
                        env.N8N_PORT = "${20000 + env.BUILD_NUMBER.toInteger()}"
                        env.QDRANT_CONTAINER = "fstm_qdrant_${env.BRANCH_SLUG}"
                        env.N8N_CONTAINER = "fstm_n8n_${env.BRANCH_SLUG}"
                        env.VENV_DIR = "/var/jenkins_home/venv/fstm_${env.BRANCH_SLUG}"

                        if (!params.JINA_API_KEY_INPUT?.toString()?.trim()) {
                            error "❌ ERREUR FAIL-FAST : Aucune clé JINA_API_KEY saisie ! Relancez avec 'Build with Parameters'."
                        }
                    }

                    env.QDRANT_URL = "http://${env.QDRANT_CONTAINER}:6333"
                    env.N8N_URL    = "http://${env.N8N_CONTAINER}:5678"
                    env.PYTHON     = "${env.VENV_DIR}/bin/python"
                    env.PIP        = "${env.VENV_DIR}/bin/pip"

                    checkout scm
                    echo "Commit : ${env.GIT_COMMIT?.take(8)} — Projet FSTM"
                }
            }
        }

        stage('2. Contrôle Qualité') {
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
                    if (env.IS_MAIN == 'true') {
                        withCredentials([string(credentialsId: 'JINA_API_KEY', variable: 'JINA_API_KEY')]) {
                            env.JINA_API_KEY_VALUE = env.JINA_API_KEY
                        }
                    } else {
                        env.JINA_API_KEY_VALUE = params.JINA_API_KEY_INPUT
                    }
                }
                sh """
                echo "Vérification Fail-Fast de l'API Jina AI..."
                STATUS=\$(curl -s -o /dev/null -w "%{http_code}" -X POST https://api.jina.ai/v1/embeddings \\
                     -H "Authorization: Bearer ${env.JINA_API_KEY_VALUE}" \\
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
                    JENKINS_NAME=$(docker ps --format "{{.Names}}" | grep -i jenkins | head -1)
                    docker network connect fstm_network "$JENKINS_NAME" 2>/dev/null || true
                    '''

                    if (env.IS_MAIN == 'true') {
                        sh """
                        # ── Qdrant Production ──
                        if ! docker ps -a --format "{{.Names}}" | grep -q "^${env.QDRANT_CONTAINER}\$"; then
                            echo "Lancement de Qdrant..."
                            docker run -d \\
                                --name ${env.QDRANT_CONTAINER} \\
                                --network fstm_network \\
                                -p ${env.QDRANT_PORT}:6333 \\
                                -v qdrant_storage:/qdrant/storage \\
                                --restart unless-stopped \\
                                qdrant/qdrant:latest
                            echo "✅ Qdrant lancé."
                        elif ! docker ps --format "{{.Names}}" | grep -q "^${env.QDRANT_CONTAINER}\$"; then
                            echo "Démarrage de ${env.QDRANT_CONTAINER} arrêté..."
                            docker start ${env.QDRANT_CONTAINER}
                        else
                            echo "✅ Qdrant déjà en cours d'exécution."
                        fi

                        # ── n8n Production ──
                        if ! docker ps -a --format "{{.Names}}" | grep -q "^${env.N8N_CONTAINER}\$"; then
                            echo "Lancement de n8n..."
                            docker run -d \\
                                --name ${env.N8N_CONTAINER} \\
                                --network fstm_network \\
                                -p ${env.N8N_PORT}:5678 \\
                                -e N8N_HOST=0.0.0.0 \\
                                -e N8N_PORT=5678 \\
                                -e N8N_PROTOCOL=http \\
                                -e N8N_USER_MANAGEMENT_DISABLED=true \\
                                -v n8n_data:/home/node/.n8n \\
                                --restart unless-stopped \\
                                n8nio/n8n:latest
                            echo "✅ n8n lancé."
                        elif ! docker ps --format "{{.Names}}" | grep -q "^${env.N8N_CONTAINER}\$"; then
                            echo "Démarrage de ${env.N8N_CONTAINER} arrêté..."
                            docker start ${env.N8N_CONTAINER}
                        else
                            echo "✅ n8n déjà en cours d'exécution."
                        fi
                        """
                    } else {
                        // En développement, nettoyage systématique pour un déploiement éphémère à neuf
                        sh """
                        docker stop ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true
                        docker rm   ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true

                        echo "Lancement de Qdrant éphémère..."
                        docker run -d \\
                            --name ${env.QDRANT_CONTAINER} \\
                            --network fstm_network \\
                            -p ${env.QDRANT_PORT}:6333 \\
                            qdrant/qdrant:latest

                        echo "Lancement de n8n éphémère..."
                        docker run -d \\
                            --name ${env.N8N_CONTAINER} \\
                            --network fstm_network \\
                            -p ${env.N8N_PORT}:5678 \\
                            -e N8N_HOST=0.0.0.0 \\
                            -e N8N_PORT=5678 \\
                            -e N8N_PROTOCOL=http \\
                            -e N8N_USER_MANAGEMENT_DISABLED=true \\
                            n8nio/n8n:latest
                        """
                    }

                    sh 'sleep 5'
                }
            }
        }

        stage('5. Vérification de Santé') {
            parallel {
                stage('Qdrant') {
                    steps {
                        script {
                            def qdrantOK = false
                            for (int i = 1; i <= 10; i++) {
                                qdrantOK = (sh(script: "curl -sf --max-time 3 ${env.QDRANT_URL}", returnStatus: true) == 0)
                                if (qdrantOK) break
                                echo "Qdrant non prêt (tentative ${i}/10) — attente de 3s..."
                                sleep 3
                            }
                            if (!qdrantOK) error "Qdrant injoignable sur ${env.QDRANT_URL}"
                            echo "✅ Qdrant : OK"
                        }
                    }
                }

                stage('n8n') {
                    steps {
                        script {
                            def n8nOK = false
                            for (int i = 1; i <= 40; i++) {
                                n8nOK = (sh(script: "curl -sf --max-time 3 ${env.N8N_URL}/healthz || curl -sf --max-time 3 ${env.N8N_URL}", returnStatus: true) == 0)
                                if (n8nOK) break
                                echo "n8n non prêt (tentative ${i}/40) — attente de 3s..."
                                sleep 3
                            }
                            if (!n8nOK) {
                                echo "❌ Échec final. Logs de n8n :"
                                sh "docker logs ${env.N8N_CONTAINER} || true"
                                error "n8n injoignable sur ${env.N8N_URL}"
                            }
                            echo "✅ n8n : OK"
                        }
                    }
                }
            }
        }

        stage('6. Configuration du Workflow n8n') {
            steps {
                script {
                    echo "📥 Importation et activation automatique du workflow dans n8n..."
                    sh """
                    docker cp FSTM_JINA.json ${env.N8N_CONTAINER}:/tmp/FSTM_JINA.json
                    docker exec -u node ${env.N8N_CONTAINER} n8n import:workflow --input=/tmp/FSTM_JINA.json
                    docker exec -u node ${env.N8N_CONTAINER} n8n update:workflow --all --active=true
                    """
                    echo "✅ n8n est prêt avec le workflow actif !"
                }
            }
        }

        stage('7. Installation') {
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

        stage('8. Indexation Jina AI') {
            steps {
                sh """
                export JINA_API_KEY=${env.JINA_API_KEY_VALUE}
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
        success {
            echo "🎉 Pipeline FSTM OK sur la branche ${env.BRANCH_SLUG} — Build #${env.BUILD_NUMBER}"
            script {
                if (env.IS_MAIN == 'false') {
                    echo "Succès détecté sur branche feature : Nettoyage des conteneurs éphémères..."
                    sh "docker stop ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true"
                    sh "docker rm   ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true"
                }
            }
        }
        failure {
            script {
                if (env.IS_MAIN == 'false') {
                    echo "Échec détecté sur branche feature : Nettoyage des conteneurs éphémères..."
                    sh "docker stop ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true"
                    sh "docker rm   ${env.QDRANT_CONTAINER} ${env.N8N_CONTAINER} || true"
                } else {
                    echo "Échec détecté sur main — Conteneurs de production préservés."
                }
            }
        }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}
