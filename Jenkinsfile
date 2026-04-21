pipeline {
    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        QDRANT_URL = 'http://qdrant:6333'
        N8N_URL    = 'http://n8n:5678'
        VENV_DIR   = "/var/jenkins_home/venv/fstm"
        PYTHON     = "/var/jenkins_home/venv/fstm/bin/python"
        PIP        = "/var/jenkins_home/venv/fstm/bin/pip"
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

        stage('2. Vérification') {
            steps {
                sh '''
                for FILE in index_fstm.py requirements.txt FSTM_JINA.json docker-compose.yml; do
                    [ -e "$FILE" ] && echo "OK : $FILE" || { echo "MANQUANT : $FILE"; exit 1; }
                done
                python3 -m py_compile index_fstm.py && echo "Syntaxe OK"
                '''
            }
        }

        stage('3. Vérification des Services') {
            steps {
                script {
                    [qdrant: QDRANT_URL, n8n: N8N_URL].each { name, url ->
                        def ok = (sh(script: "curl -sf --max-time 5 ${url}", returnStatus: true) == 0)
                        if (!ok) {
                            sh(script: "docker restart fstm_${name}", returnStatus: true)
                            sleep 8
                            if ((sh(script: "curl -sf --max-time 5 ${url}", returnStatus: true)) != 0)
                                error "${name} injoignable — arrêt."
                        }
                        echo "${name} OK."
                    }
                }
            }
        }

        stage('4. Installation') {
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

        stage('5. Indexation Jina AI') {
            steps {
                withCredentials([string(credentialsId: 'JINA_API_KEY', variable: 'JINA_API_KEY')]) {
                    sh '''
                    export JINA_API_KEY=$JINA_API_KEY
                    "$PYTHON" index_fstm.py
                    '''
                }
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
        success { echo "Pipeline FSTM OK — Build #${env.BUILD_NUMBER}" }
        failure  { echo "Pipeline FSTM ÉCHOUÉ — Build #${env.BUILD_NUMBER}" }
        cleanup  {
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}
