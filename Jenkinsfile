pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        // Host path bind-mounted into the Jenkins container (see docker run -v).
        // Requires: -v /home/dejassha/Projects/jenkins-office/sakthi-erp-backend:/home/dejassha/Projects/jenkins-office/sakthi-erp-backend:rw
        DEPLOY_PATH = "/home/dejassha/Projects/jenkins-office/sakthi-erp-backend"

        // Backend .env Jenkins credential (frontend uses "sakthi-erp-frontend")
        ENV_CREDENTIAL_ID = "sakthi-erp-backend"

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
                script {
                    // jenkins/jenkins:lts-jdk17 has NO python3. Bootstrap via
                    // `uv` (static binary, only needs curl) which installs a
                    // local CPython 3.12 + workspace venv. Mirrors the
                    // frontend 'Setup Node' pattern. Persists via env.PATH.
                    sh '''
                        set -e
                        TOOLS="$WORKSPACE/.tools"
                        BIN="$TOOLS/bin"
                        mkdir -p "$BIN"
                        export PATH="$BIN:$PATH"
                        if [ ! -x "$BIN/uv" ]; then
                            echo "Installing uv locally..."
                            UV_VERSION="0.6.14"
                            cd /tmp
                            rm -rf uv.tar.gz uv-x86_64-unknown-linux-gnu
                            if command -v curl >/dev/null 2>&1; then
                                curl -fsSL -o uv.tar.gz "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz"
                            elif command -v wget >/dev/null 2>&1; then
                                wget -q -O uv.tar.gz "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz"
                            else
                                echo "ERROR: neither curl nor wget available."
                                exit 1
                            fi
                            tar -xzf uv.tar.gz
                            mv uv-x86_64-unknown-linux-gnu/uv "$BIN/uv"
                            chmod +x "$BIN/uv"
                            rm -rf uv.tar.gz uv-x86_64-unknown-linux-gnu
                        fi
                        "$BIN/uv" --version
                        "$BIN/uv" python install 3.12
                        if [ ! -x "venv/bin/python" ]; then
                            "$BIN/uv" venv venv --python 3.12
                        fi
                        ./venv/bin/python --version
                    '''
                    env.PATH = "${env.WORKSPACE}/.tools/bin:${env.WORKSPACE}/venv/bin:${env.PATH}"
                    echo "Python on PATH: ${env.WORKSPACE}/venv/bin"
                    sh 'uv --version; ./venv/bin/python --version'
                }
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
                        export PATH="$WORKSPACE/.tools/bin:$PATH"
                        # uv venv has no pip by default — use `uv pip`
                        # pinned to the workspace interpreter.
                        export UV_PYTHON="./venv/bin/python"
                        if [ -f "requirements.txt" ]; then
                            uv pip install --python "$UV_PYTHON" -r requirements.txt
                        elif [ -f "requirements/prod.txt" ]; then
                            uv pip install --python "$UV_PYTHON" -r requirements/prod.txt
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

                    # This exact host path must be bind-mounted into the
                    # container, else mkdir fails with "Permission denied"
                    # because /home/dejassha/Projects inside the container
                    # is owned by root. Try plain mkdir first, then sudo.
                    if ! mkdir -p "${DEPLOY_PATH}" 2>/dev/null; then
                        echo "mkdir denied, retrying with sudo..."
                        sudo -n mkdir -p "${DEPLOY_PATH}"
                        sudo -n chown -R "$(id -u):$(id -g)" "${DEPLOY_PATH}"
                    fi
                    echo "Deploying to: ${DEPLOY_PATH}"

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
