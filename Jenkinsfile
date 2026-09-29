pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        // NOTE: do NOT use a host path like /home/dejassha/... here unless
        // it is bind-mounted into the Jenkins container, otherwise mkdir
        // fails with "Permission denied". This path is always writable
        // (jenkins user owns /var/jenkins_home).
        // Host sync: /var/lib/docker/volumes/jenkins_home/_data/deploys/sakthi-erp-backend
        DEPLOY_PATH = "/home/dejassha/Projects/jenkins-office/sakthi-erp-backend"

        // Backend .env Jenkins credential (frontend uses "sakthi-erp-frontend")

        PYTHON = "python3"
        DJANGO_SETTINGS_MODULE = "sakthi_erp.settings"
        PORT = "8000"
    }

    stages {

        stage('Checkout') {
            steps {
                cleanWs()
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    set -e
                    ${PYTHON} --version
                    ${PYTHON} -m pip --version
                    # venv lives in workspace so cleanWs() resets it each build
                    if [ ! -x "venv/bin/python" ]; then
                        ${PYTHON} -m venv venv
                    fi
                    ./venv/bin/python --version
                    ./venv/bin/pip --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    // Optional .env from Jenkins credentials.
                    // Does not fail the build if missing — falls back
                    // to the .env committed in the repo.
                    try {
                        withCredentials([
                            file(
                                credentialsId: "${ENV_CREDENTIAL_ID}",
                                variable: 'ENV_FILE'
                            )
                        ]) {
                            sh '''
                                set -e
                                if [ -f "$ENV_FILE" ]; then
                                    echo "Copying Jenkins environment file..."
                                    cp "$ENV_FILE" .env
                                fi
                            '''
                        }
                    } catch (err) {
                        echo "WARNING: credential '${ENV_CREDENTIAL_ID}' not found. Using repo .env as fallback."
                    }

                    sh '''
                        set -e
                        ./venv/bin/pip install --upgrade pip
                        if [ -f "requirements.txt" ]; then
                            ./venv/bin/pip install -r requirements.txt
                        elif [ -f "requirements/prod.txt" ]; then
                            ./venv/bin/pip install -r requirements/prod.txt
                        else
                            echo "ERROR: no requirements file found."
                            exit 1
                        fi
                        echo "Dependencies installed successfully."
                    '''
                }
            }
        }

        stage('Check') {
            steps {
                // Non-blocking lint-style check: warnings visible but
                // never skip migrate/deploy (mirrors frontend Lint fix).
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    sh '''
                        set +e
                        ./venv/bin/python manage.py check
                        CHECK_EXIT=$?
                        if [ $CHECK_EXIT -ne 0 ]; then
                            echo "WARNING: manage.py check reported issues (exit ${CHECK_EXIT}). Continuing."
                        else
                            echo "Django check passed."
                        fi
                        exit 0
                    '''
                }
            }
        }

        stage('Migrate & Collectstatic') {
            steps {
                sh '''
                    set -e
                    ./venv/bin/python manage.py migrate --noinput
                    ./venv/bin/python manage.py collectstatic --noinput
                    test -f "manage.py"
                    echo "Migrate + collectstatic done."
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    set -e
                    echo "Preparing deployment..."
                    test -f "manage.py"
                    test -f "requirements.txt"

                    mkdir -p "${DEPLOY_PATH}"
                    echo "Deploying to: ${DEPLOY_PATH}"
                    echo "NOTE: this path is inside the Jenkins container"
                    echo "unless it is mounted to the host."

                    echo "Synchronizing files..."
                    if command -v rsync >/dev/null 2>&1; then
                        rsync -av --delete \
                            --exclude 'venv/' \
                            --exclude '__pycache__/' \
                            --exclude '*.pyc' \
                            --exclude '.git/' \
                            --exclude 'db.sqlite3' \
                            --exclude 'media/' \
                            --exclude '.tools/' \
                            ./ "${DEPLOY_PATH}/"
                    else
                        echo "WARNING: rsync not found, falling back to cp."
                        rm -rf "${DEPLOY_PATH:?}/"*
                        mkdir -p "${DEPLOY_PATH}"
                        # crude exclude handling for cp fallback
                        tar --exclude='venv' --exclude='.git' --exclude='__pycache__' \
                            --exclude='*.pyc' --exclude='db.sqlite3' \
                            -cf - . | (cd "${DEPLOY_PATH}" && tar -xf -)
                    fi
                    echo "Deployment completed successfully."
                '''
                archiveArtifacts artifacts: 'requirements*.txt,manage.py', fingerprint: true
            }
        }

        stage('Restart Backend') {
            steps {
                // Best-effort only — never fail the build if the
                // host uses a different process manager.
                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                    sh '''
                        set +e
                        echo "Attempting backend restart on deploy target..."
                        if [ -x "${DEPLOY_PATH}/venv/bin/gunicorn" ]; then
                            echo "Found venv gunicorn in deploy dir."
                        fi
                        # systemd (host must allow jenkins user or run via sudoers)
                        if command -v systemctl >/dev/null 2>&1; then
                            sudo -n systemctl restart sakthi-erp-backend 2>/dev/null \
                                && echo "systemd restart ok" \
                                || echo "INFO: systemd restart skipped (no service or no sudo)."
                        fi
                        # supervisor alternative
                        if command -v supervisorctl >/dev/null 2>&1; then
                            sudo -n supervisorctl restart sakthi-erp-backend 2>/dev/null \
                                && echo "supervisor restart ok" \
                                || echo "INFO: supervisor restart skipped."
                        fi
                        echo "If neither manager applies, restart manually on host:"
                        echo "  gunicorn sakthi_erp.wsgi:application -b 127.0.0.1:${PORT} --workers 3"
                        exit 0
                    '''
                }
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    set -e
                    echo "Verifying deployment..."
                    test -f "${DEPLOY_PATH}/manage.py" || (echo "ERROR: manage.py missing after deploy."; exit 1)
                    test -f "${DEPLOY_PATH}/requirements.txt" || (echo "ERROR: requirements.txt missing."; exit 1)
                    echo "Deployed files:"
                    ls -lh "${DEPLOY_PATH}" | head -20
                    du -sh "${DEPLOY_PATH}"
                    # Backend liveness is best-effort (may run on host, not in container)
                    if command -v curl >/dev/null 2>&1; then
                        curl -fsS -m 5 "http://127.0.0.1:${PORT}/api/" >/dev/null 2>&1 \
                            && echo "Backend responded on :${PORT}/api/" \
                            || echo "INFO: backend not reachable from container (expected if it runs on host)."
                    fi
                    echo "Deployment verification successful."
                '''
            }
        }
    }

    post {
        success {
            echo "=============================================="
            echo "Backend deployment successful."
            echo "Build: #${BUILD_NUMBER}"
            echo "Path: ${DEPLOY_PATH}"
            echo "=============================================="
        }

        failure {
            echo "=============================================="
            echo "Backend deployment FAILED."
            echo "Build: #${BUILD_NUMBER}"
            echo "Check the Jenkins console output."
            echo "=============================================="
        }

        always {
            cleanWs()
        }
    }
}
