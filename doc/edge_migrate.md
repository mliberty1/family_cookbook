# Migrating from Render to edge (Caddy)

Status as of 2026-10-26: **edge is live.** `cookbook.libertyfamily.us`
resolves to the home address, Caddy fronts `cookbook.service` on edge, and
the first push-to-main deploy went through the webhook path and was
confirmed by `/healthz`. Remaining: backups (step 9) and retiring Render
(step 11). This document records the setup so it can be rebuilt.

## Target architecture

```
Internet
  |  80/443
  v
Ubiquiti firewall --port-forward--> edge (192.168.42.40)
                                      Caddy 2.x (TLS, Let's Encrypt)
                                        cookbook.libertyfamily.us -> 127.0.0.1:8880
                                      systemd cookbook.service (Restart=always)
                                        ExecStart = deploy/cookbook-start.sh
                                          git reset --hard origin/main
                                          pip install -r requirements.txt (if changed)
                                          python migrate.py
                                          exec gunicorn app:app
                                        /var/cookbook/app    git clone
                                        /var/cookbook/venv   Python venv
                                        /var/cookbook/data   cookbook.db
                                        /var/cookbook/backups
                                             ^                      ^
             POST /webhook/update            |                      | git fetch (https)
             Authorization: Bearer <token>   |                      |
GitHub Actions (this repo, push to main) ----+   github.com/mliberty1/family_cookbook
             then poll /healthz until git_sha == pushed commit
```

**Restart is deploy.** Every start of `cookbook.service` runs
`deploy/cookbook-start.sh`, which fast-forwards the clone to `origin/main`,
syncs the venv, applies schema migrations, and then `exec`s gunicorn. The
GitHub Action only has to make the service restart: it POSTs to the app's
own `/webhook/update` with a bearer token, the app sends SIGTERM to its
gunicorn master, and systemd (`Restart=always`) starts it again. The Action
then polls `/healthz` until the reported `git_sha` matches the pushed commit,
so a failed deploy shows up as a red run.

The repo is public, so edge fetches from GitHub anonymously; the Action never
ships code. Nothing in this path runs as root, and nothing outside this repo
needs changing (an earlier plan routed through `api.jetperch.com` plus a
sudoers rule; that is gone).

The prep steps in the start script **fail open**: if GitHub or PyPI is
unreachable, or a migration fails, the script logs a warning and still starts
gunicorn on whatever code is on disk. A push that breaks the app badly enough
that it cannot serve the webhook is recovered by pushing a fix and running
`sudo systemctl restart cookbook` once over ssh.

This mirrors the Jetperch ERP deployment on the same host. See
`C:\repos\Jetperch\erp\doc\deployment.md` for the reference pattern and
troubleshooting notes (Caddy install from Cloudsmith, cert issues, etc.).

Access: `ssh edge` (alias in `~/.ssh/config`, user `edge`). Use Windows-native
ssh from PowerShell; the key does not load under Git Bash. Root actions need
`sudo` with the `edge` password.

## Already done (2025-06-25)

- **Caddy site block** in `/etc/caddy/Caddyfile`:

  ```
  cookbook.libertyfamily.us {
      reverse_proxy 127.0.0.1:8880
      encode gzip
  }
  ```

  (A sibling `bowl.libertyfamily.us -> 127.0.0.1:8881` block exists for the
  bowl pool app, also unfinished.)

- **System user** created:

  ```bash
  sudo useradd --system --create-home --home-dir /var/cookbook --shell /bin/bash cookbook
  ```

## In this repo (2026-10-26)

- `deploy/cookbook-start.sh`: the ExecStart script described above.
- `deploy/cookbook.service`: the systemd unit (copy to `/etc/systemd/system`).
- `migrate.py` and `migrations/`: numbered SQL migrations tracked by
  `PRAGMA user_version`. See `migrations/README.md`.
- `app.py`: `GET /healthz` (reports `GIT_SHA`) and `POST /webhook/update`
  (bearer token, 404 when `DEPLOY_TOKEN` is unset).
- `.github/workflows/deploy.yml`: push to `main` -> webhook -> poll healthz.
  Merged after the DNS cutover; a push before cutover would have failed
  the workflow against Render.

## Not done

- Backup timer (step 9).
- Render service still live; retire after a few quiet days (step 11).

## Remaining steps

### 1. Native dependencies

WeasyPrint (PDF export) needs pango, pangoft2, and harfbuzz-subset. edge runs
Ubuntu 26.04, where the gdk-pixbuf package from `render.yaml`
(`libgdk-pixbuf2.0-0`) was renamed to `libgdk-pixbuf-2.0-0`; WeasyPrint 67
no longer needs it anyway.

```bash
sudo apt install -y git python3-venv python3-pip sqlite3 \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 shared-mime-info
```

Checked 2026-10-25: all of these are already installed on edge (pango 1.57,
harfbuzz 12.3, Python 3.14). Note Python 3.14 is newer than the 3.13 Render
uses, so watch the `pip install` in step 3 for any wheel that lacks 3.14
support.

### 2. Directory layout

As `edge`, with sudo. `app/` is created by `git clone` in step 3, not here:

```bash
sudo -iu cookbook
mkdir -p /var/cookbook/data /var/cookbook/backups /var/cookbook/log
chmod 0750 /var/cookbook /var/cookbook/data /var/cookbook/backups /var/cookbook/log
exit
```

| Path                               | Purpose                                              |
|------------------------------------|------------------------------------------------------|
| `/var/cookbook/app/`               | `git clone` of github.com/mliberty1/family_cookbook  |
| `/var/cookbook/venv/`              | Python venv                                          |
| `/var/cookbook/data/`              | `cookbook.db` (never inside `app/`)                  |
| `/var/cookbook/backups/`           | SQLite snapshots                                     |
| `/var/cookbook/log/`               | `deploy.log`, written by the start script            |
| `/var/cookbook/env`                | Environment file, `root:cookbook` 0640               |
| `/var/cookbook/.requirements-hash` | Stamp so pip only runs when requirements.txt changes |

### 3. Clone the repo and build the venv

One-time bootstrap. After step 6 the start script keeps the clone at
`origin/main` on every (re)start.

On edge:

```bash
sudo -iu cookbook
git clone https://github.com/mliberty1/family_cookbook.git /var/cookbook/app
python3 -m venv /var/cookbook/venv
/var/cookbook/venv/bin/pip install -r /var/cookbook/app/requirements.txt
exit
```

Anonymous https clone; no GitHub credentials live on edge. Every start does
`git reset --hard origin/main`, so never edit tracked files in
`/var/cookbook/app` by hand; they will be discarded. Untracked files survive
but do not put anything there either; `data/` is the place.

`cookbook.jsonld` and `schema.sql` come along with the clone and are only
needed if you fall back to a fresh database in step 5.

### 4. Environment file

`/var/cookbook/env`, owner `root:cookbook`, mode `0640`:

```
DATABASE_URL=sqlite:////var/cookbook/data/cookbook.db
SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
DEPLOY_TOKEN=<generate the same way; also goes into the GitHub secret in step 10>
MAILGUN_API_KEY=<copy from Render env vars>
MAILGUN_DOMAIN=<copy from Render env vars>
EMAIL_FROM=<copy from Render env vars>
REPLY_TO=<copy from Render env vars, optional>
```

Four slashes in `DATABASE_URL` means an absolute path. Three slashes is
relative to the working directory and silently creates a stray db.

```bash
sudo chown root:cookbook /var/cookbook/env
sudo chmod 0640 /var/cookbook/env
```

### 5. Migrate the database from Render

The production data lives on Render's persistent disk at
`/var/data/cookbook.db`. Pull a consistent copy using the Render Shell:

1. Render dashboard -> `family-cookbook` service -> **Shell**.
2. Snapshot the db (safe while gunicorn is running):

   ```bash
   sqlite3 /var/data/cookbook.db ".backup /tmp/cookbook-backup.db"
   ```

3. Get it off Render. Options:
   - Admin Panel **Database backup** download in the running app
     (see `doc/admin-panel.md`), or
   - `base64 /tmp/cookbook-backup.db` in the Render shell and paste into a
     local file, then `base64 -d`, or
   - temporarily `scp`/`curl` it to a reachable host.

4. Place it on edge:

   ```bash
   sudo cp cookbook-backup.db /var/cookbook/data/cookbook.db
   sudo chown cookbook:cookbook /var/cookbook/data/cookbook.db
   sudo chmod 0640 /var/cookbook/data/cookbook.db
   ```

5. Verify:

   ```bash
   sudo -u cookbook sqlite3 /var/cookbook/data/cookbook.db \
       "SELECT count(*) FROM recipes; SELECT name, email, is_admin FROM users; PRAGMA user_version;"
   ```

   `user_version` is `0` on the Render database; `migrate.py` will apply
   anything in `migrations/` on the first start.

Fallback if the Render db cannot be retrieved: initialize fresh with
`init_database.py` and `import_recipes.py` (see `deployment.md`). You will
lose users, edits, and version history that are not in `cookbook.jsonld`.

Do the final db copy **just before** the DNS switch so no edits are lost;
do a trial copy earlier to test the service.

### 6. systemd unit

The unit is in the repo. Install it and start the service:

```bash
sudo cp /var/cookbook/app/deploy/cookbook.service /etc/systemd/system/cookbook.service
sudo systemctl daemon-reload
sudo systemctl enable --now cookbook.service
systemctl status cookbook.service
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8880/
curl -s http://127.0.0.1:8880/healthz
tail /var/cookbook/log/deploy.log
```

Expect `200` (or `302` to login), a JSON body whose `git_sha` matches
`git -C /var/cookbook/app rev-parse HEAD`, and a `starting gunicorn at ...`
line in the log.

Things to know about the unit (comments in the file say the same):

- `Restart=always`, because the webhook stops gunicorn with SIGTERM and exit
  code 0, which `on-failure` would not restart.
- `StartLimitIntervalSec=0`, so a crash loop keeps retrying every 5 s. Each
  retry pulls `origin/main`, so pushing a fix is enough to recover.
- `ExecStart` points into the clone. The script updates itself on each
  start; the new version applies on the following start.
- `User=cookbook`, bind to `127.0.0.1` only; Caddy is the only client.

Test the deploy loop locally before DNS moves:

```bash
sudo systemctl restart cookbook            # restart = pull + redeploy
TOKEN=$(sudo grep ^DEPLOY_TOKEN /var/cookbook/env | cut -d= -f2)
curl -s -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8880/webhook/update
# expect 202 {"status":"restarting",...}, then the unit restarts
journalctl -u cookbook -n 30
```

### 7. Caddy

The site block is already present. Confirm and reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy cannot obtain the certificate until DNS points here (step 8). Until
then the log will show ACME failures for `cookbook.libertyfamily.us`; this is
expected.

Pre-flight test before switching DNS, from a LAN machine:

```powershell
curl.exe -k --resolve cookbook.libertyfamily.us:443:192.168.42.40 https://cookbook.libertyfamily.us/
```

### 8. DNS cutover

Done 2026-10-26. Previously: `cookbook.libertyfamily.us CNAME family-cookbook-rh6v.onrender.com`.

1. Do the final database copy (step 5).
2. Change the CNAME to the DDNS hostname that `erp.jetperch.com` uses (same
   target as `ssh.jetperch.com`). Low TTL first if possible.
3. Confirm the firewall port-forward for 80/443 already reaches edge (it does
   for erp, so nothing to change).
4. Watch Caddy acquire the cert:

   ```bash
   journalctl -u caddy -f
   ```

5. Browse to <https://cookbook.libertyfamily.us> and log in.

### 9. Backups

Copy the erp pattern (`erp-backup.service` + `erp-backup.timer` on edge),
pointing at `/var/cookbook/data/cookbook.db` and writing to
`/var/cookbook/backups/`. Keep a rolling 14 days.

### 10. Deploy from GitHub Actions

Everything on edge is already in place after step 6. What remains:

1. Add the GitHub repo secret `COOKBOOK_DEPLOY_TOKEN` with the same value as
   `DEPLOY_TOKEN` in `/var/cookbook/env`.
2. Merge `.github/workflows/deploy.yml` to `main`. It has two steps:
   `curl -X POST .../webhook/update` with the bearer token, then poll
   `/healthz` every 5 s for up to 3 minutes until `git_sha` equals
   `GITHUB_SHA`. The `concurrency` group serializes runs so two quick pushes
   do not restart over each other.
3. Watch the first run, then `tail /var/cookbook/log/deploy.log` on edge.

Expect 5 to 15 seconds of 502 from Caddy during each deploy while gunicorn
restarts, longer when `requirements.txt` changed.

**Schema changes** go in `migrations/NNN_description.sql` and are applied by
`migrate.py` before gunicorn starts. See `migrations/README.md`. A failing
migration is rolled back and logged; the app still starts on the old schema.

**Rollback:** `git revert` and push (the Action redeploys), or on edge:

```bash
sudo -u cookbook git -C /var/cookbook/app reset --hard <old-sha>
sudo systemctl restart cookbook
```

Note the restart will pull `origin/main` again, so a manual rollback only
holds until the next restart; push the revert as well.

**Manual deploy** (Action down, or app too broken to serve the webhook):

```bash
sudo systemctl restart cookbook
```

**Alternative considered:** a systemd timer on edge polling `origin/main`
every few minutes needs no GitHub secret at all. Rejected only because the
push path deploys immediately and reports failure back into the GitHub run.

### 11. Retire Render

After a few days of edge serving traffic without issues:

1. Take one last backup from Render.
2. Suspend, then delete the `family-cookbook` service and its disk.
3. Remove `render.yaml` from the repo and rewrite `doc/deployment.md` for
   edge. Update `README.md` deployment references.

## Checklist

- [x] 1. Native deps installed
- [x] 2. Directories created
- [x] 3. Repo cloned, venv built
- [x] 4. `/var/cookbook/env` written (including `DEPLOY_TOKEN`)
- [x] 5. Trial db copy, service tested locally on 8880
- [x] 6. `cookbook.service` installed and enabled; restart and webhook tested on LAN
- [x] 7. Caddy validated and reloaded
- [x] 5. Final db copy
- [x] 8. CNAME switched, cert issued, site verified
- [ ] 9. Backup timer
- [x] 10. `COOKBOOK_DEPLOY_TOKEN` secret set, workflow merged, first push-to-main deploy green
- [ ] 11. Render retired, docs updated
