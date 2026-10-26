#!/usr/bin/env bash
# ExecStart for cookbook.service on edge. Every (re)start is a deploy:
# fast-forward to origin/main, sync the venv, apply schema migrations, then
# exec gunicorn. The prep steps fail open: a GitHub or PyPI outage, or a bad
# push, logs a warning and the last code on disk still serves. Recovery from
# a broken deploy is therefore "push a fix, then systemctl restart cookbook".
#
# This file lives in the repo and is replaced by the git reset below while it
# is running. That is safe: git unlinks and recreates the file, and bash keeps
# reading the old inode. The new version takes effect on the next start.

APP=/var/cookbook/app
VENV=/var/cookbook/venv
LOG=/var/cookbook/log/deploy.log
STAMP=/var/cookbook/.requirements-hash

log() { echo "$(date -Is) $*" | tee -a "$LOG" >&2; }

cd "$APP" || exit 1

if git fetch --quiet origin && git reset --quiet --hard origin/main; then
    log "checked out $(git rev-parse HEAD)"
else
    log "WARNING: git update failed; starting with $(git rev-parse HEAD)"
fi

NEW=$(sha256sum requirements.txt | cut -d' ' -f1)
if [[ "$NEW" != "$(cat "$STAMP" 2>/dev/null)" ]]; then
    if "$VENV/bin/pip" install -q -r requirements.txt; then
        echo "$NEW" > "$STAMP"
        log "requirements installed"
    else
        log "WARNING: pip install failed; continuing with existing venv"
    fi
fi

"$VENV/bin/python" migrate.py || log "WARNING: migrate.py failed; see above"

GIT_SHA=$(git rev-parse HEAD)
export GIT_SHA
log "starting gunicorn at $GIT_SHA"
exec "$VENV/bin/gunicorn" app:app --bind 127.0.0.1:8880 --workers 2
