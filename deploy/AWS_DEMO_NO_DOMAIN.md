# EC2 demo: public HTTPS without a domain

This is the setup for a temporary shared demo: one EC2 host, a public link such
as `https://<EC2_PUBLIC_IPV4>`, and a browser username/password prompt. The
frontend, API, PostgreSQL and Redis run together. No domain, Google OAuth,
CloudFront or separate frontend hosting is required.

Let’s Encrypt now issues trusted IP address certificates. They last 160 hours;
Caddy manages issuance and renewal using the `shortlived` profile. The gateway
pins Caddy 2.11.7, including its fix for long POST SSE responses. Sources:
[IP certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability),
[Caddy TLS](https://caddyserver.com/docs/caddyfile/directives/tls),
[Caddy 2.11.7](https://github.com/caddyserver/caddy/releases/tag/v2.11.7).

## 1. Launch EC2 and install Docker

Use the EC2 launch and Docker installation portions of steps 1–2 in
[the AWS guide](AWS_DEMO.md): Ubuntu 24.04 x86_64, `t3a.medium` (4 GB), 40 GiB gp3,
Standard CPU credits, and Docker Compose 2.24.4+. Follow the configuration below
for this shared demo; the other guide's domain/OAuth settings are unnecessary.
Allow public TCP 80 and 443 so certificate validation and HTTPS can work. Restrict
SSH/22 to your IP. Leave the API, PostgreSQL and Redis ports closed.

Use an automatic public IPv4 for the lowest idle cost. Its address/link can
change after stopping and starting EC2. A retained Elastic IP keeps the link
stable and has ongoing IPv4 charges, including while the instance is stopped.
The cost calculation in the AWS guide still applies; this option removes domain
and separate frontend hosting costs.

Copy the reviewed source snapshot to EC2. Uncommitted local changes are not
included by cloning a remote branch. Work from the project root on Ubuntu for
the following commands. Use a dedicated demo database and non-sensitive files:
everyone using these credentials shares documents, history and approval rights.

## 2. Prepare model settings and the shared password

On first setup only:

```bash
cp .env.example .env
chmod 600 .env
```

Generate a password hash interactively, so the password is not in shell history:

```bash
sudo docker run --rm -it caddy:2.11.7-alpine caddy hash-password
```

The username can be `admin`. You can enter `admin` as the password for the
requested demonstration, but anyone guessing it could access documents and
spend the configured model credits. A random shared password is preferable for
a publicly reachable instance. No password is hardcoded into the repository.

Edit `.env` privately. Replace placeholders, including the current public IPv4:

```dotenv
POSTGRES_USER=unisensory
POSTGRES_PASSWORD=<unique URL-safe database password>
POSTGRES_DB=unisensory
DEMO_PUBLIC_IP=<EC2 public IPv4, without https:// or a port>
DEMO_USERNAME=admin
DEMO_PASSWORD_HASH='<paste the entire generated bcrypt hash here>'
ACME_EMAIL=<your email>
AUTH_ENABLED=false
QUEUE_BACKEND=redis
OPENAI_API_KEY=<your model provider key>
OPENAI_API_BASE=https://api.openai.com/v1
EXTRACTION_API_KEY=<your model provider key>
EXTRACTION_BASE_URL=https://api.openai.com/v1
EXTRACTION_MODEL=<your tested image-capable model ID>
EXTRACTION_WORKFLOW_TIMEOUT_SECONDS=1800
LOG_FORMAT=json
```

Keep the single quotes around the hash: they preserve its dollar signs in
Compose's `.env` parser. The URLs above illustrate the official OpenAI endpoint.
Preserve your existing `OPENAI_API_BASE` when using another compatible provider;
set `EXTRACTION_BASE_URL` to the same URL when PAPER uses that provider too.

`OPENAI_API_BASE` configures backend chat and the configured OpenAI cloud-model
entry. `EXTRACTION_BASE_URL` configures PAPER OCR/field extraction. In Compose,
an unset or empty `EXTRACTION_BASE_URL` falls back to `OPENAI_API_BASE`, then to
`https://api.openai.com/v1`. An explicit extraction URL overrides that fallback.
Use the tested model ID and matching credential for each endpoint. Supply the
corresponding key for other cloud providers selected through legacy model routes.
PAPER uses the backend extraction key; the browser Settings page does not
configure it.

Here `AUTH_ENABLED=false` selects the app's shared workspace. **The gateway
requires the password on every public frontend and API route.** The demo overlay
removes direct API/database ports and requires a nonempty password hash. Do not
publish the base development Compose stack with authentication disabled.

## 3. Build, migrate and enable the shared reviewer

Define this helper in your Ubuntu SSH session. This deployment uses the base
file plus the **demo overlay**, without the separate production overlay:

```bash
dc() { sudo docker compose -f docker-compose.yml -f docker-compose.demo.yml "$@"; }
dc config --quiet
dc build api caddy
dc up -d --wait db redis
dc run --rm --no-deps api alembic upgrade head
dc exec -T db psql -v ON_ERROR_STOP=1 -U unisensory -d unisensory < deploy/demo-reviewer.sql
```

The SQL explicitly adds the existing shared identity, `dev-user`, in tenant
`default` with the allowed `accountant` role. This enables full agreement/AP
decisions. It does not store the gateway password and refuses to silently change
an existing conflicting identity. Do not run it against a non-demo database.

The gateway image builds the frontend with an empty `VITE_API_BASE`, so every
browser API request uses the same HTTPS origin. Its build also enables the
shared-demo account notice, replacing OAuth sign-out. No frontend keys or URLs
need to be entered manually for this mode.

## 4. Start HTTPS and share the link

```bash
dc up -d api caddy
dc ps
dc logs --tail=100 caddy
```

Wait for certificate issuance, then open **`https://<EC2_PUBLIC_IPV4>`**. Enter
the username and password in the browser prompt. Do not bypass certificate
warnings: check the public IP setting, inbound 80/443 and Caddy logs instead.
Persist the Caddy data volume so certificate/account state survives restarts.

Use a private browser window for the demo and close all its windows when done.
Browsers cache Basic credentials; the app's OAuth logout does not clear them.
The credentials grant one shared workspace rather than individual user accounts.

## 5. Verify the full workflow

- In a new private window, confirm the frontend and `/v1/auth/me` require the
  password. Confirm the wrong password is rejected.
- Open `/paper` directly, upload a short PDF, wait for extraction, and confirm
  the source preview and saved history still load after refreshing.
- Approve an agreement and exercise invoice association, reconciliation and a
  saved AP decision. Confirm chat/job streams work with your cloud model.
- Once jobs finish, restart the API with `dc restart api` and confirm documents,
  artifacts and saved decisions survive.
- Monitor memory with `sudo docker stats --no-stream`, AWS charges and the model
  provider's usage. Process one representative document at a time initially.

Public gateway writes require `Origin: https://<EC2_PUBLIC_IPV4>`; browsers set
this automatically. Include it when testing uploads/mutations with a CLI client.
The gateway strips the shared Basic credential before forwarding API requests.

## 6. Stop and resume

Finish active jobs, then stop EC2 in the AWS console. Keep its EBS disk and Docker
volumes. Storage and retained IPs still cost money; the demo is offline while
the instance is stopped. Do not use `docker compose down -v` on data you need.

After starting it again, check the public IPv4. If it changed, update
`DEMO_PUBLIC_IP` in `.env`, redefine `dc` in the new SSH session, then run:

```bash
dc up -d --force-recreate api caddy
dc logs --tail=100 caddy
```

Share the new address after Caddy obtains its trusted certificate. Even with a
stable IP, allow renewal time if the instance was stopped past certificate
expiry. Verify HTTPS before each demo. Back up database and uploads before
permanently deleting the host.

## Local verification

The isolated gateway tests use temporary local Caddy/PostgreSQL containers and a local CA;
they do not create AWS resources, call models or modify your database:

```powershell
$env:RUN_DEMO_GATEWAY_TESTS = '1'
python -m pytest tests/deployment --confcutdir=tests/deployment -o addopts= -q
```

The tests exercise password protection on frontend/API routes, deep links,
credential stripping, exact-origin writes, blocked OAuth routes, and repeatable
reviewer provisioning that refuses conflicting identities. Actual
public certificate issuance and the complete application workflow must still
be verified on the EC2 host.
