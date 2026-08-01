# Mumble Tags

[![test](https://github.com/KitchenSinkhole/allianceauth-mumble-tags/actions/workflows/test.yml/badge.svg)](https://github.com/KitchenSinkhole/allianceauth-mumble-tags/actions/workflows/test.yml)

Appends tags such as `[FC]` or `[LOGI]` to a user's Mumble display name based on
their Alliance Auth group membership.

Built for **Alliance Auth 5.x**. A replacement for the unmaintained
[`allianceauth-mumble-tagger`](https://github.com/Solar-Helix-Independent-Transport/allianceauth-mumble-tagger),
which is broken on AA 5 (see [Why this exists](#why-this-exists)).

---

## Contents

- [Requirements](#requirements)
- [Installation — Docker](#installation--docker)
- [Installation — bare metal](#installation--bare-metal)
- [Verifying the install](#verifying-the-install)
- [Configuration](#configuration)
- [Updating](#updating)
- [How it works](#how-it-works)
- [Why this exists](#why-this-exists)
- [Settings reference](#settings-reference)
- [Troubleshooting](#troubleshooting)
- [Uninstalling](#uninstalling)
- [Development](#development)
- [Contributing](#contributing)

---

## Requirements

- Alliance Auth `>=5.0.0,<6`
- Python 3.10 – 3.14 (CI covers 3.10 – 3.13)
- The Mumble service enabled (`allianceauth.services.modules.mumble`)

The package is installed from Git, not PyPI — the URLs below are the canonical
install source.

---

## Installation — Docker

For the official Alliance Auth Docker stack (the `aa-docker` directory produced
by the upstream `download.sh` script).

> **You are already running a custom image.** `zeroc-ice` is not included in the
> stock Alliance Auth container, so anyone running Mumble on Docker has already
> followed the
> [custom docker image](https://allianceauth.readthedocs.io/en/latest/installation-containerized/docker.html#using-a-custom-docker-image)
> steps — `conf/requirements.txt` populated, and the `build:` section
> uncommented under `x-allianceauth-base` in `docker-compose.yml`. Adding this
> app is one more line in that file. If `docker-compose.yml` still has
> `image: ${AA_DOCKER_TAG?err}` active and the `build:` block commented out,
> do the custom image steps first.

### 1. Add to `conf/requirements.txt`

One entry per line. Pin to a tag so builds are reproducible:

```
zeroc-ice
allianceauth-mumble-tags @ git+https://github.com/KitchenSinkhole/allianceauth-mumble-tags.git@v1.0.0
```

`zeroc-ice` will already be there for the Mumble authenticator — leave it.

The repository is public, so the build pulls it directly — no registry account,
no mirroring, no credentials. If you would rather not pull from GitHub at build
time, see [Installing from a local copy](#installing-from-a-local-copy) below.

### 2. Add to `INSTALLED_APPS` in `conf/local.py`

**Order matters** — `mumbletags` must come after the Mumble service:

```python
INSTALLED_APPS += [
    "allianceauth.services.modules.mumble",
    "mumbletags",
]
```

If Mumble already appears earlier in the file, just append `"mumbletags"`.

### 3. Rebuild and bring the stack up

```bash
cd ~/aa-docker
docker compose build
docker compose --env-file=.env up -d
```

`docker compose build` is required — `up -d` alone will reuse the cached image
and your new package will not appear.

### 4. Run migrations

```bash
docker compose exec allianceauth_gunicorn bash
auth migrate
auth collectstatic
exit
```

(`auth` is the alias for `python manage.py` inside the container.)

### 5. Confirm the authenticator picked up the new image

In the upstream compose file the authenticator
shares the same YAML anchor as the web containers:

```yaml
allianceauth_mumble_authenticator:
  container_name: allianceauth_mumble_authenticator
  <<: [*allianceauth-base]
  entrypoint: ["python", "manage.py", "mumble_authenticator", "--server_id=1"]
```

Because of `<<: [*allianceauth-base]` it runs the *same image* as
`allianceauth_gunicorn`, so `docker compose --env-file=.env up -d` should
recreate it automatically after a rebuild. Verify rather than assume:

```bash
docker compose ps allianceauth_mumble_authenticator
```

The container should have been created just now. If it wasn't:

```bash
docker compose --env-file=.env up -d --force-recreate allianceauth_mumble_authenticator
```

If the authenticator is still running the old image, tags will appear in the
Auth web UI but **not** in Mumble.

### Installing from a local copy

Only needed if the build host has no outbound access to GitHub, or you are
testing local modifications. Clone or copy this directory inside `aa-docker/`
so it falls within the Docker build context, then check `custom.dockerfile`. It
copies `conf/requirements.txt` and pip-installs it; a local path must also be
copied in *before* that install runs. Add a line above it:

```dockerfile
COPY allianceauth-mumble-tags /tmp/allianceauth-mumble-tags
```

and reference it in `conf/requirements.txt`:

```
/tmp/allianceauth-mumble-tags
```

The Git approach is preferable — it needs no `custom.dockerfile` changes and
survives upstream edits to that file.

---

## Installation — bare metal

For the non-containerized layout: user `allianceserver`, virtualenv at
`/home/allianceserver/venv/auth`, project at `/home/allianceserver/myauth`.

```bash
sudo su allianceserver
source /home/allianceserver/venv/auth/bin/activate
pip install git+https://github.com/KitchenSinkhole/allianceauth-mumble-tags.git@v1.0.0
```

Drop the `@v1.0.0` to track `main`; pinning to a tag is recommended so a later
`pip install --upgrade` on an unrelated package can't drag in a new version.

Or from a cloned directory: `cd allianceauth-mumble-tags && pip install .`
(add `-e` to keep editing the source in place).

Add to `INSTALLED_APPS` in
`/home/allianceserver/myauth/myauth/settings/local.py` as shown above, then:

```bash
cd /home/allianceserver/myauth
python manage.py migrate mumbletags
python manage.py collectstatic --noinput
exit
sudo supervisorctl restart all
sudo supervisorctl status
```

> Restart **all**, not just gunicorn. The Mumble authenticator runs under
> supervisor as `[program:authenticator]` executing
> `manage.py mumble_authenticator --server_id=1`, and it needs to restart to
> pick up the patch.

---

## Verifying the install

The app logs at INFO on startup:

```
Patched MumbleUser.display_name with mumbletags.
```

Docker:

```bash
docker compose logs allianceauth_mumble_authenticator | grep mumbletags
docker compose logs allianceauth_gunicorn | grep mumbletags
```

Bare metal:

```bash
grep mumbletags /home/allianceserver/myauth/log/allianceauth.log
```

Two other messages both mean the app is inactive:

| Log line | Meaning |
|---|---|
| `Alliance Auth's Mumble service is not in INSTALLED_APPS` | Ordering problem, or the Mumble module isn't enabled |
| `MumbleUser.display_name is not a readable property` | Alliance Auth changed upstream; the app disabled itself rather than half-working |

End-to-end check without touching Mumble — configure a tag in the admin first,
then:

```bash
docker compose exec allianceauth_gunicorn bash
auth shell
```

```python
from allianceauth.services.modules.mumble.models import MumbleUser
mu = MumbleUser.objects.first()
print(mu.display_name)
```

The name should reflect your tags immediately. No restart is needed after
changing tags.

---

## Configuration

All configuration is in the admin. There is no settings file for tags.

**Admin → Mumble Tags → Tag associations → Add**

### Fields

| Field | What it does |
|---|---|
| **Tag** | The literal text inserted into the name. Whatever you type is what appears — `[FC]`, `★`, `~AFK~`. Include your own brackets; nothing is added for you. |
| **Groups** | Members of **any** group in this box receive the tag. It is OR, not AND. |
| **Enabled** | Off = tag ignored, row kept. Useful for seasonal tags. |
| **Position** | `Suffix` (default) places it after the name; `Prefix` before. |
| **Order** | Sorts multiple tags on one user. Lower first. Negatives allowed. |

### One tag, many groups

The model is **one tag → many groups**, not one group → many tags.

- `[FC]` for both *Fleet Commanders* and *Senior FC* → one row, both groups in the box.
- A user in two groups showing two different tags → two rows.

### Worked example

| Tag | Groups | Position | Order |
|---|---|---|---|
| `★` | Directors | Prefix | 0 |
| `[FC]` | Fleet Commanders, Senior FC | Suffix | 10 |
| `[LOGI]` | Logistics | Suffix | 20 |
| `[NEW]` | Recruits | Suffix | 30 |

For a pilot whose base name is `[BRAVE]Wojtek Kowalski`:

| Groups held | Resulting display name |
|---|---|
| Directors | `★ [BRAVE]Wojtek Kowalski` |
| Fleet Commanders + Logistics | `[BRAVE]Wojtek Kowalski [FC] [LOGI]` |
| Directors + Fleet Commanders | `★ [BRAVE]Wojtek Kowalski [FC]` |
| Fleet Commanders *and* Senior FC | `[BRAVE]Wojtek Kowalski [FC]` (deduplicated) |

The `[BRAVE]` portion is Alliance Auth's own name format
(`MumbleService.name_format`, default `[{corp_ticker}]{character_name}`) and is
not controlled by this app.

### Practical notes

- **Prefix is underrated.** Mumble sorts the user list alphabetically, so a
  prefix tag physically clusters those users at the top of the channel — handy
  for spotting who is running the fleet.
- **Leave gaps in `order`** (10, 20, 30) so you can slot new tags in without
  renumbering.
- **Changes apply on next connect.** Editing a tag flushes the cache
  immediately, but a user already sitting in Mumble keeps their current name
  until they reconnect.
- **Test long combinations.** Mumble servers can enforce name length or
  character restrictions. Check a worst case (director + FC + logi on a long
  character name) against your live server.
- **Non-ASCII glyphs** like `★` render fine on modern clients but can look
  wrong on old ones. If your corp runs mixed client versions, stick to ASCII.

### Bulk setup

Docker: `docker compose exec allianceauth_gunicorn bash`, then `auth shell`.
Bare metal: `python manage.py shell`.

```python
from django.contrib.auth.models import Group
from mumbletags.models import TagAssociation

tag = TagAssociation.objects.create(tag="[FC]", order=10)
tag.groups.set(Group.objects.filter(name__in=["Fleet Commanders", "Senior FC"]))
```

---

## Updating

### Docker

1. Bump the pinned version in `conf/requirements.txt`
2. `docker compose build`
3. `docker compose --env-file=.env up -d`
4. `docker compose exec allianceauth_gunicorn bash` → `auth migrate` → `auth collectstatic`
5. Confirm `allianceauth_mumble_authenticator` was recreated

### Bare metal

```bash
pip install --upgrade git+https://github.com/KitchenSinkhole/allianceauth-mumble-tags.git@v1.0.0
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart all
```

---

## How it works

In Alliance Auth 5, `MumbleUser.display_name` is computed at authentication
time rather than stored:

```python
@property
def display_name(self) -> str:
    return NameFormatter(MumbleService(), self.user).format_name()
```

This app wraps that property in `AppConfig.ready()` and appends tags on the way
out. It captures the *existing* getter rather than reimplementing
`NameFormatter`, so any upstream change to how the base name is built is
inherited automatically.

Nothing is written to the database, which means there is no state to keep in
sync. A user's name is correct the next time they connect, always — group
changes need no signal handling at all.

The tag→group mapping is cached (Redis) because the authenticator reads it on
every connect. It is invalidated by signals whenever a tag or its group list
changes, so no `redis-cli flushall` is needed after editing tags.

### Known trade-offs

- **It is a monkeypatch.** Alliance Auth offers no hook here. The app validates
  the property's shape before patching and disables itself with a loud log
  message if that shape ever changes, but pin `allianceauth<6` and re-test on
  major upgrades.
- **Tag resolution runs per authentication** rather than per group change. The
  cache keeps this to a single `user.groups` query per connect.

---

## Why this exists

The original `allianceauth-mumble-tagger` (last commit January 2021) applies
tags by assigning to `MumbleUser.display_name`:

```python
mu_instance.display_name = new_display_name
```

That worked while `display_name` was a database column. Alliance Auth 5 dropped
the column (migration `0016_idlerhandler_alter_mumbleuser_options_and_more`)
and replaced it with a computed, read-only property, so there is no longer
anything to assign to — the write raises `AttributeError` and the tag is never
applied.

What broke is the approach rather than one line, which is why this is a
separate app instead of a patch. Tags here are produced by *reading* the
property and wrapping it, so nothing is stored and nothing can drift out of
sync with group membership.

---

## Settings reference

| Setting | Default | Purpose |
|---|---|---|
| `MUMBLETAGS_CACHE_TTL` | `3600` | Cache backstop in seconds. Invalidation is signal-driven, so this rarely matters. |

Set it in `conf/local.py` (Docker) or `myauth/settings/local.py` (bare metal).

---

## Troubleshooting

**Tags show in the Auth web UI but not in Mumble.**
The authenticator is running an older image or was never restarted. Docker:
`docker compose up -d --force-recreate allianceauth_mumble_authenticator`.
Bare metal: `sudo supervisorctl restart all`.

**Nothing changed at all after a Docker rebuild.**
`docker compose build` was skipped, or the `build:` section in
`docker-compose.yml` is still commented out and the stack is pulling the stock
image.

**No tags anywhere, no log lines from mumbletags.**
`"mumbletags"` is missing from `INSTALLED_APPS`, or appears before
`allianceauth.services.modules.mumble`.

**`MumbleUser.display_name is not a readable property` in the log.**
Alliance Auth changed the Mumble service. The app has disabled itself
deliberately. Check which AA version you upgraded to.

**Tag edits don't take effect.**
Users already connected keep their name until they reconnect. If a fresh
connect is also stale, check that Redis is reachable — the cache falls back to
its TTL otherwise.

**A user has a group but no tag.**
Confirm the `TagAssociation` is *enabled* and that the group is in its
**Groups** box, not the other way round.

---

## Uninstalling

```bash
# Docker: docker compose exec allianceauth_gunicorn bash, then:
auth migrate mumbletags zero
```

Remove the requirement line from `conf/requirements.txt` (or
`pip uninstall allianceauth-mumble-tags` on bare metal), remove `"mumbletags"`
from `INSTALLED_APPS`, rebuild and restart.

Nothing is written to the Mumble tables, so removal leaves no residue — names
revert to Alliance Auth's plain format on the next connect.

### Migrating from `allianceauth-mumble-tagger`

The app label is `mumbletags`, not `mumbletagger`, so the two do not collide.
Uninstall the old app and remove it from `INSTALLED_APPS`. Existing tags are
not imported automatically; there are usually only a handful, so re-enter them
in the admin.

---

## Development

```bash
pip install "django>=5.2,<6"
PYTHONPATH=. DJANGO_SETTINGS_MODULE=testsettings django-admin test mumbletags
```

The test suite runs against a stub that mirrors AA 5's `MumbleUser` property
shape, so it needs no Alliance Auth install. It covers tag resolution,
prefix/suffix ordering, deduplication, cache invalidation, patch idempotency,
the upstream-change guard, and graceful fallback when tag lookup fails.

To regenerate migrations after a model change:

```bash
PYTHONPATH=. DJANGO_SETTINGS_MODULE=testsettings django-admin makemigrations mumbletags
```

---

## Contributing

Issues and pull requests are welcome at
[KitchenSinkhole/allianceauth-mumble-tags](https://github.com/KitchenSinkhole/allianceauth-mumble-tags).

When reporting a problem, include:

- Alliance Auth version and whether you run Docker or bare metal
- Any `mumbletags` lines from the log (see [Verifying the install](#verifying-the-install))
- What the display name shows in the Auth web UI versus in Mumble — the two
  differing almost always means the authenticator wasn't restarted

Pull requests should keep `django-admin test mumbletags` green; CI runs it on
Python 3.10 – 3.13.

Release notes live in [CHANGELOG.md](CHANGELOG.md).

---

## License

MIT. See [LICENSE](LICENSE).
