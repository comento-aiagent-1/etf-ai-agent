#!/usr/bin/env bash
# Executed over SSH; uses the existing production Compose and VM secrets.
set -Eeuo pipefail
image=${1:?Expected a GHCR image tagged with a full commit SHA}
[[ "$image" =~ ^ghcr\.io/[a-z0-9._/-]+:[a-f0-9]{40}$ ]] || { echo 'Invalid image reference'; exit 1; }
cd "${DEPLOY_DIR:-/opt/etf-ai-agent}"
test -f .env && test -f compose.prod.yaml
umask 077
exec 9>.deploy.lock
flock -w 300 9
compose=(docker compose -f compose.prod.yaml)
"${compose[@]}" config --quiet
container=$("${compose[@]}" ps -q app)
[[ -n "$container" ]] || { echo 'Initial deployment must be completed first'; exit 1; }
previous=$(docker inspect --format '{{.Image}}' "$container")
changed=false
rollback() {
    status=$?
    trap - ERR INT TERM
    if "$changed"; then
        echo 'Deployment failed; restoring the previous local image.' >&2
        if ! APP_IMAGE="$previous" "${compose[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 120 app; then
            echo 'Rollback failed; manual recovery is required.' >&2
        fi
    fi
    exit "${status:-1}"
}
trap rollback ERR
trap 'false' INT TERM
APP_IMAGE="$image" "${compose[@]}" pull app
changed=true
APP_IMAGE="$image" "${compose[@]}" up -d --no-deps --no-build --wait --wait-timeout 120 app
# Only persist the new reference after the container is healthy. Preserve all secrets.
python3 - "$image" <<'PY'
import os, re, sys, tempfile
from pathlib import Path
path = Path('.env')
text = path.read_text()
line = 'APP_IMAGE=' + sys.argv[1]
pattern = r'(?m)^[ \t]*(?:export[ \t]+)?APP_IMAGE[ \t]*=.*$'
text = re.sub(pattern, lambda _: line, text) if re.search(pattern, text) else text.rstrip('\n') + '\n' + line + '\n'
fd, temporary = tempfile.mkstemp(prefix='.env.deploy-', dir='.')
try:
    with os.fdopen(fd, 'w') as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
trap - ERR INT TERM
echo "Healthy deployment completed: $image"
