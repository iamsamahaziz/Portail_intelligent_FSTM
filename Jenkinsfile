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

        stage('1. Récupération du Code') {
            steps {
                checkout scm
                echo "Commit : ${env.GIT_COMMIT?.take(8)}"
            }
        }

        stage('2. Syntaxe Python') {
            steps {
                sh '''
                find . -name "*.py" ! -path "./.git/*" ! -path "./venv/*" | while read f; do
                    python3 -m py_compile "$f" && echo "OK : $f" || exit 1
                done
                echo "Syntaxe OK."
                '''
            }
        }

        stage('3. Vérification Fichiers') {
            steps {
                sh '''
                for f in index_fstm.py requirements.txt FSTM_JINA.json docker-compose.yml; do
                    [ -e "$f" ] && echo "OK : $f" || { echo "MANQUANT : $f"; exit 1; }
                done
                '''
            }
        }

        stage('4. Vérification Services') {
            steps {
                script {
                    [qdrant: QDRANT_URL, n8n: N8N_URL].each { name, url ->
                        def ok = (sh(script: "curl -sf --max-time 5 ${url}", returnStatus: true) == 0)
                        if (!ok) {
                            sh "docker restart fstm_${name} || true"
                            sleep 8
                            if (sh(script: "curl -sf --max-time 5 ${url}", returnStatus: true) != 0)
                                error "${name} injoignable — arrêt."
                        }
                        echo "${name} OK."
                    }
                }
            }
        }

        stage('5. Installation') {
            steps {
                sh '''
                [ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
                "$PIP" install -q --upgrade pip
                "$PIP" install -q -r requirements.txt
                echo "Installation OK."
                '''
            }
        }

        stage('6. Indexation') {
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
cols = [c['name'] for c in json.load(sys.stdin).get('result',{}).get('collections',[])]
sys.exit(0 if 'fstm_docs' in cols else 1)
" && echo "Collection fstm_docs OK." || { echo "Collection manquante !"; exit 1; }
                '''
            }
        }
    }

    post {
        success { echo "Pipeline OK — Build #${env.BUILD_NUMBER}" }
        failure  { echo "Pipeline ECHEC — Build #${env.BUILD_NUMBER}" }
        cleanup  { cleanWs(deleteDirs: true, notFailBuild: true) }
    }
}
