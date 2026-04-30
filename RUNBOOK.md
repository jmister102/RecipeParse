# RecipeParse — Operations Runbook

## Connect to the droplet

```bash
ssh -i ~/.ssh/key josh@162.243.70.152
cd ~/recipeparse
source venv/bin/activate
```

Add this to `~/.ssh/config` on your local machine to shortcut it:
```
Host recipeparse
    HostName 162.243.70.152
    User josh
    IdentityFile ~/.ssh/key
```
Then just: `ssh recipeparse`

---

## Service management

```bash
sudo systemctl status recipeparse      # is it running?
sudo systemctl restart recipeparse     # restart after code changes
sudo systemctl stop recipeparse        # stop
sudo systemctl start recipeparse       # start
journalctl -u recipeparse -f           # live logs (Ctrl+C to exit)
journalctl -u recipeparse -n 100       # last 100 log lines
```

---

## Deploy an update

```bash
# On the droplet:
cd ~/recipeparse
git pull
sudo systemctl restart recipeparse
```

That's it. No build step needed.

---

## Admin scripts

Run from `~/recipeparse` with the venv active:

```bash
# List all users and their recipe counts
python3 scripts/list_users.py

# Change a user's password
RECIPES_SECRET_KEY=$(grep RECIPES_SECRET_KEY /etc/systemd/system/recipeparse.service | cut -d= -f3) \
  venv/bin/python3 scripts/change_password.py --username <username>

# Create a new admin account (first-time setup on a fresh server)
venv/bin/python3 scripts/setup_user.py
```

---

## Key file locations

| What | Where |
|------|-------|
| App code | `~/recipeparse/` |
| Database | `~/recipeparse/data/recipes.db` |
| Secret key | `/etc/systemd/system/recipeparse.service` |
| Nginx config | `/etc/nginx/sites-available/recipeparse` |
| SSL certs | `/etc/letsencrypt/live/recipeparse.com/` |

---

## Backup the database

```bash
# Copy DB to your local machine (run locally):
scp -i ~/.ssh/key josh@<droplet-ip>:~/recipeparse/data/recipes.db ~/Desktop/recipes-backup-$(date +%Y%m%d).db
```

---

## SSL certificate

Let's Encrypt auto-renews. To manually force a renewal:
```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

---

## Architecture at a glance

```
Browser → nginx (443/80) → uvicorn :8001 → FastAPI → SQLite
```

- **Backend:** FastAPI + uvicorn, port 8001 (localhost only)
- **Frontend:** Vanilla JS SPA served by FastAPI
- **Database:** SQLite at `data/recipes.db`
- **Auth:** JWT tokens (30-day expiry), bcrypt passwords
- **Rate limits:** 5 registrations/hour, 10 logins/15 min per IP

---

## GitHub

```bash
# On your local machine:
cd /home/josh/claude/myrecipes
git status
git add -A
git commit -m "description"
git push
```

Repo: https://github.com/jmister102/RecipeParse
