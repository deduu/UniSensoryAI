# AWS demo hosting guide

Assessed on 2026-10-17 for the full application: uploads, document extraction,
saved history and PAPER review, using external model APIs.

For the selected **no domain / no Google login / shared password** setup, use
[the public IP HTTPS demo guide](AWS_DEMO_NO_DOMAIN.md). It serves the complete
frontend and API together on EC2. The domain/OAuth instructions below are the
alternative for individual accounts.

Lambda can reduce idle compute costs, but this application needs changes before
it can run reliably there. For scheduled demonstrations, use the existing Docker
stack on an EC2 instance and stop the instance between sessions. For a demo that
stays online, Lightsail offers a predictable VM bill with the same stack.

## Cost comparison

| Option | Fit for this demo | Costs to include |
| --- | --- | --- |
| Lambda on demand | Good after storage and worker changes | API and worker execution, PostgreSQL, S3, queue, logs, frontend and model API calls; networking can add fixed costs. |
| EC2 during demo sessions | Smallest change for occasional demonstrations | Running instance hours, EBS, public IPv4, frontend and model calls. EBS and an allocated Elastic IP can still cost money while the instance is stopped. |
| Lightsail VM | Simple for a demo that stays online | Published Linux bundles with IPv4 include 2 GB at $12/month and 4 GB at $24/month. Model calls, frontend, domain and optional backups are additional. Stopped instances still accrue charges. |

Illustrative Lambda worker calculation: 1,000 jobs/month, each taking 120 seconds
at 2 GB, consume 240,000 GB-seconds. Using AWS's US East x86 example rate of
$0.0000166667/GB-second, compute is approximately **$4 before free allocation**,
plus approximately $0.0002 for those 1,000 requests. This excludes initialization,
API requests, streams, retries, storage, database and model charges. Eligible
unused free allocation could cover that compute; the complete demo is not
necessarily free. Confirm prices for the chosen Region and account.

Sources: [Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[Lightsail bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html),
[EC2 stop and start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html),
[Lightsail billing](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html),
[public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

## Current requirements

| Requirement | Finding |
| --- | --- |
| CPU container calling cloud models | Present. `Dockerfile` uses Python 3.11 and excludes the optional `local-vlm` dependencies by default. |
| Dependency lock | `uv lock --check --offline` passes. |
| Local container tools | Docker daemon 29.8.2 and Compose v5.5.1 are available. Production Compose requires 2.24.4 or newer. |
| Existing configuration and storage tests | 23 focused tests pass for extraction composition and upload storage. |
| Production Compose | Configuration validation passes; `API_DOMAIN` and `ACME_EMAIL` are unset locally. |
| PostgreSQL, Redis and migrations | Present in Compose/Alembic; the production image needs a separate migration command before first API startup. |
| Public frontend | Vite build exists. Set `VITE_API_BASE` during the production build; the frontend Dockerfile is a development server. |
| Public access settings | Local auth/OAuth secrets and public-domain settings are missing. Configure them before exposure. A cloud model key is present locally; validity and quota were not tested. |
| AWS CLI and SAM | Not found on local PATH. CLI is optional for the console-based VM setup below; SAM is needed only if chosen for future Lambda infrastructure. |
| AWS account access and quota | Must be checked in the intended account. No account identity, permissions or resource quota was inspected. |
| Cloud deployment | No AWS resources were created and no cloud image or live cloud workflow was tested. |

## Why Lambda needs application changes

The limits here apply to ordinary on-demand Lambda event functions. Managed
Instances have different limits and billing; their longer asynchronous timeout
does not establish that this application works unchanged.

| Area | Current behavior | Required change |
| --- | --- | --- |
| HTTP runtime | `Dockerfile:71` starts Uvicorn through tini. | Add a Lambda runtime integration, such as Lambda Web Adapter, and a separate deployment definition. |
| Job processing | `src/api/server.py:163` starts queue workers inside FastAPI startup. Both queue backends use background asyncio tasks. | Submit durable messages to SQS and process them in an invoked worker. Redis alone does not keep execution running after Lambda returns. |
| Startup recovery | `src/api/server.py:144` marks interrupted jobs failed when using the memory backend. | Replace process-wide recovery with job ownership/leases; one cold start must not fail another worker's jobs. |
| Originals and artifacts | `src/services/upload_storage.py` and `src/services/paper_extraction.py` use local files, including saved extraction JSON and source previews. | Store sources and artifacts in S3 and use `/tmp` as processing scratch space. A `/tmp` setting alone cannot preserve history between execution environments. |
| File uploads | The API permits 100 MiB files. | Add direct, authorized uploads to S3; synchronous Lambda requests are limited to 6 MB, and binary encoding reduces usable file size further. Downloads/previews also need an appropriate storage response path. |
| Workflow duration | Queued PAPER extraction defaults to 1,800 seconds. | Measure the complete job including OCR and field extraction. Ordinary Lambda invocations have a 900-second limit; split longer jobs or use a container worker. |
| PostgreSQL connections | `src/db/session.py` creates substantial read/write pools per process. | Bound concurrency and connection use; select a reachable PostgreSQL service and an appropriate pooling strategy. |
| Streaming | Chat and job status use SSE. | Configure and test a streaming-capable integration. Python can use Lambda Web Adapter. Existing job polling can avoid long status streams. |
| Model execution | Cloud dependencies are optional separately from local GPU dependencies. | Keep external inference for this design; a local GPU model is a different hosting requirement. |

Lambda freezes idle environments and does not guarantee unfinished background
tasks will run. Its container filesystem is read-only except for `/tmp`.
See [execution lifecycle](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html),
[container requirements](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html),
[quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html) and
[Python response streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html).

## Set up the current app on AWS

### 0. Prepare settings before launching EC2

For a public HTTPS demo with login, prepare the model credential, domain names
and OAuth client before starting paid compute. You can finish configuring them
after launch, but the following order avoids paying for an idle setup session:

| Setting | When to prepare it | Where it belongs |
| --- | --- | --- |
| Cloud model key and image-capable model ID | Before launch; use the model already tested with your documents. | Backend `.env`: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `EXTRACTION_API_KEY`, `EXTRACTION_BASE_URL`, `EXTRACTION_MODEL`. |
| Public names | Before OAuth/frontend configuration. These examples use `app.example.com` and `api.example.com`. | DNS, backend URLs and frontend build configuration. |
| Google OAuth client and random secrets | Before public API access. | Backend `.env`; register the exact API callback below. |
| Frontend API URL | Before the production frontend build. | `VITE_API_BASE=https://api.example.com`; changing it requires rebuilding the frontend. |
| PAPER approval role | After the intended reviewer signs in for the first time, before approval testing. | The persisted user's role in PostgreSQL; see step 6. |

PAPER extraction uses server configuration. Entering a key in the browser's
Settings page does not configure its extraction runtime. Keep the shared demo
provider key on the backend. The legacy document/chat model selector is separate
from `EXTRACTION_MODEL`; select a configured cloud model there as well.

The existing production layout runs API, PostgreSQL, Redis and Caddy on one EC2
host. Cloudflare Pages can serve the static frontend on its free plan, using a
second subdomain of the same domain. Static asset requests do not incur Pages
Functions charges. This avoids an additional paid frontend service; an AWS-only
frontend alternative is described in step 5. See [Pages pricing](https://developers.cloudflare.com/pages/functions/pricing/).

### EC2 budget example for Singapore

AWS's public price data published on 2026-10-15 lists Linux On-Demand
`t3a.medium` (4 GiB, x86_64) at **$0.0472/hour**, `t3.medium` at $0.0528/hour,
and Singapore gp3 storage at **$0.096 per GB-month**. A single `t3a.medium`
with 40 GiB gp3, kept for a month but running for 20 hours, is approximately:

| Item | Calculation | USD |
| --- | --- | --- |
| EC2 compute | 20 hours × $0.0472 | $0.944 |
| EBS storage retained for the month | 40 × $0.096 | $3.840 |
| Automatic public IPv4 while running | 20 hours × $0.005 | $0.100 |
| Infrastructure subtotal | Before tax, transfer, backups, model usage, domain or account credits | **$4.884** |

Keeping an Elastic IP for 730 hours makes its charge $3.65 instead of $0.10,
raising that example to about $8.43. Running the instance for all 730 hours is
about $41.95 including the same disk and one IPv4. These are estimates, not a
spending cap. Verify your account's regional launch quote and credits.

For the lowest cost, use an automatic public IPv4 and update the API DNS record
after each stop/start. The hostname and OAuth callback stay the same. Allow time
for DNS caching before the next demonstration. Use a retained Elastic IP when
avoiding those DNS changes is worth its ongoing cost.

Sources: [AWS Singapore Linux price data](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20%28Singapore%29/Linux/index.json),
[EBS regional price data](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ebs.json),
[IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

### 1. Create the host

In the AWS console, select your Region and create an EC2 instance with Ubuntu
24.04 LTS, x86_64, approximately 4 GB RAM (`t3a.medium` where offered, otherwise
`t3.medium`), and an encrypted 40 GiB gp3 root volume. This is a starting estimate for the API,
PostgreSQL, Redis and builds; memory use with the chosen documents must be
measured. Keep cloud model inference enabled. Review the regional quote before
launching. Create a billing budget alert suited to your demo budget.

In EC2, choose **Launch instance**, name it `unisensory-demo`, choose the Ubuntu
image and instance type above, and create/download an SSH key pair. Select
On-Demand purchasing for predictable demo availability. Under Advanced details,
choose **Standard** CPU credits to avoid surplus-credit charges; this can slow
builds/processing when credits run out. T3/T3a default to Unlimited.
See [CPU credit settings](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-how-to.html).
Leave optional paid add-ons off initially, including detailed monitoring.

Keep API, PostgreSQL and Redis together for this small demo. RDS, ElastiCache,
a load balancer and NAT gateway would add services and costs without being
required by this deployment.

Use a public subnet with an internet gateway and a public IPv4 address. In its
security group allow SSH/22 only from your current IP, and HTTP/80 plus HTTPS/443
for the demo audience. Keep PostgreSQL, Redis and port 8010 private. A NAT gateway
or load balancer is unnecessary for this single-host layout.

For a demo that stays online, a 4 GB Lightsail Linux instance can host the same
stack. Configure its firewall equivalently and attach a static IP. Check the
[available Regions](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html)
and the selected bundle's quote.

### 2. Prepare Docker and the application

Connect through SSH or the AWS console. Install Docker Engine, Buildx and the
Compose plugin using the [official Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/).
Verify `sudo docker version` and `sudo docker compose version`; Compose must be
at least 2.24.4 because this project uses `!reset` and `!override`.

From Windows PowerShell, SSH into the Ubuntu host using the key downloaded at
launch (use your real paths/address):

```powershell
ssh -i "C:\path\unisensory-demo.pem" ubuntu@<EC2_PUBLIC_IPV4>
```

After installing Docker on Ubuntu, install Git if needed, clone your repository
and select the reviewed demo branch/tag. For a private repository, use your
normal authenticated Git workflow without embedding an access token in the URL.
The current working tree contains uncommitted features: cloning the remote alone
will not include them. Decide which snapshot to demo before transferring it.
Alternatively, copy the reviewed source snapshot to the host. Transfer source
separately from secrets and production data, then work from the project root.

Run the following **on the Ubuntu host**, inside the project folder. Copy the
environment example only on first setup:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` privately. Configure these values, replacing all placeholders:

```dotenv
POSTGRES_USER=unisensory
POSTGRES_PASSWORD=<unique URL-safe random password>
POSTGRES_DB=unisensory
QUEUE_BACKEND=redis
AUTH_ENABLED=true
JWT_SECRET_KEY=<unique random secret>
SESSION_SECRET=<different unique random secret>
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
FRONTEND_URL=https://app.example.com
OAUTH_REDIRECT_BASE_URL=https://api.example.com
CORS_ALLOW_ORIGINS=https://app.example.com
API_DOMAIN=api.example.com
ACME_EMAIL=<your email>
OAUTH_GOOGLE_CLIENT_ID=<OAuth client ID>
OAUTH_GOOGLE_CLIENT_SECRET=<OAuth client secret>
OPENAI_API_KEY=<model provider key>
OPENAI_API_BASE=https://api.openai.com/v1
EXTRACTION_CONFIG_PATH=/app/configs/extraction.yaml
EXTRACTION_BASE_URL=https://api.openai.com/v1
EXTRACTION_MODEL=<your available vision and text model>
EXTRACTION_API_KEY=<model provider key>
EXTRACTION_WORKFLOW_TIMEOUT_SECONDS=1800
PAPER_RECONCILIATION_CONFIG_PATH=/app/configs/paper_reconciliation.yaml
LOG_FORMAT=json
```

Generate high-entropy secrets locally, for example with a password manager.
Use a URL-safe PostgreSQL password because Compose interpolates it into the
database connection URL. The example uses one OpenAI-compatible provider; choose
the endpoint, model and credential you actually use. Preserve an existing custom
`OPENAI_API_BASE`, and set `EXTRACTION_BASE_URL` to the same URL if PAPER uses
that provider. An explicit extraction URL overrides Compose's fallback to
`OPENAI_API_BASE`. For another configured
provider, also supply its corresponding key for legacy model routes. Leave
`DOCKER_LOCAL_VLM` false.

Create an OAuth client of type **Web application** in Google Cloud's OAuth
settings. Configure the app's branding/audience, then register
`https://api.example.com/v1/auth/callback/google` as an authorized redirect URI.
Copy the client ID and client secret into the backend variables above. GitHub
OAuth can be used instead, with its matching environment variables and callback.
Use `app.example.com` and `api.example.com` under the same parent domain so the
existing cookie settings work straightforwardly.

The current app accepts a valid identity from any configured provider; login
alone does not create an invited-email restriction. Google testing mode also
does not enforce a test-user allowlist for the basic `openid email profile`
scopes used here. If you need selected-email access, configure a supported
organization restriction or add an application allowlist before sharing the
demo publicly. See [Google OAuth audience behavior](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).

### 3. Configure the public API address

Point the `api.example.com` DNS A record to the host's public IPv4. An EC2 Elastic
IP keeps this stable across stops and starts but continues to incur IPv4 charges
while allocated. Without one, update DNS after the instance's address changes.
Start with direct DNS resolution to the host and verify TLS and streaming before
adding another proxy.

### 4. Build and migrate before starting the API

Use the production overlay for every command. This keeps database ports private,
uses the production image and retains uploaded files in the uploads volume.

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml build api
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait db redis
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api caddy
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

The migration uses a one-off container so a fresh database is ready before
FastAPI startup. Caddy obtains HTTPS certificates once DNS and ports 80/443 work.

### 5. Publish the frontend

The existing [deployment instructions](README.md) use Cloudflare Pages. That
works with the AWS backend. For the lowest-cost existing frontend route, create
a Pages project from the reviewed repository/branch, set root directory
`frontend`, build command `npm ci && npm run build`, and output directory `dist`.
Add `VITE_API_BASE=https://api.example.com` as a production build variable, then
attach `app.example.com` through Pages' custom-domain flow. See the
[React deployment guide](https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/).

For a local snapshot that has not been pushed, build that same snapshot locally
with `VITE_API_BASE` set, then upload only `frontend/dist` through Pages Direct
Upload. A Direct Upload project cannot later switch to Git integration; that
requires a new project. See [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/).

For AWS frontend hosting, use Amplify Hosting with
this repository and the reviewed demo branch, set the application root to
`frontend`, and configure `npm ci` followed by `npm run build`, publishing `dist`.
Set the production build variable `VITE_API_BASE=https://api.example.com`.
Only public configuration belongs in `VITE_*`; keep provider keys on the backend.

Attach `app.example.com` and add the SPA rewrite to `/index.html` for application
routes. `frontend/public/_redirects` serves Cloudflare Pages and is not an Amplify
rewrite configuration. Follow the [Amplify build settings](https://docs.aws.amazon.com/amplify/latest/userguide/build-settings.html)
and [SPA rewrite example](https://docs.aws.amazon.com/amplify/latest/userguide/redirect-rewrite-examples.html).
Amplify has its own hosting/build charges. S3 plus CloudFront is another option
if you prefer to manage the static deployment yourself.

### 6. Verify the complete demo

Sign in as the intended reviewer first. OAuth creates a personal tenant and a
`member` role for a new user. Each account sees its own tenant's records; local
auth-disabled data or another reviewer's uploads will not automatically appear.
Upload the demo documents after signing into the account you intend to present.

Full agreement/AP approval also requires an allowed persisted role. To grant
only the intended reviewer `accountant` under the default policies, open a local
PostgreSQL console **on the EC2 host** (these names match the `.env` above):

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db psql -U unisensory -d unisensory
```

Inside `psql`, identify the exact account:

```sql
SELECT id, tenant_id, email, role FROM users
WHERE email = 'your-demo-email@example.com';
```

Replace the ID placeholders below with the values returned for that account:

```sql
BEGIN;
UPDATE users SET role = 'accountant'
WHERE id = '<exact user ID>' AND tenant_id = '<exact tenant ID>' AND role = 'member'
RETURNING id, email, tenant_id, role;
```

Confirm exactly the intended row was returned, then enter `COMMIT;`. If the row
is wrong, enter `ROLLBACK;`. Exit with `\q` and refresh PAPER. This is a deliberate
one-account role assignment; the deployment does not perform it automatically.
The role is checked from PostgreSQL for agreement and invoice decisions.

1. Open `https://api.example.com/health` and `/openapi.json`. The health route
   alone does not prove PostgreSQL, queue or model access works.
2. Open the frontend, sign in, upload a short representative PDF and wait for
   extraction to finish. Confirm the original PDF, extracted fields and saved
   history load after a page refresh.
3. Exercise agreement review, invoice association and reconciliation in PAPER.
   Verify source-page previews and saved decisions.
4. Test chat and incremental SSE where supported. Inspect browser errors and
   host logs if requests fail or streams arrive buffered.
5. Once jobs are finished, restart the API container. Confirm saved sources,
   extraction artifacts, agreements and cases remain accessible.
6. Monitor RAM, disk and actual model spending with the intended document sizes.
   Back up both PostgreSQL and the uploads volume before deleting the host.

For the first acceptance run, use short representative documents and process one
job at a time. Check the model provider's usage page as well as AWS billing.
Do not choose local Qwen/DeepSeek/LLaVA weights on this small CPU host.

For diagnostics, use:

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 api caddy
sudo docker stats --no-stream
```

Logs can contain document metadata; review them privately. Existing rate limiting
is per process and configured as 100 requests **per minute**, while `AGENTS.md`
specifies 100 per second. This assessment leaves that policy mismatch unchanged;
do not treat the existing limiter as a distributed model-spend cap.

### 7. Control costs after the demo

For EC2, let active jobs finish, then stop the instance in the AWS console.
Compute billing stops; EBS, snapshots and retained Elastic IPs can still accrue
charges. Starting it again preserves the EBS-backed Docker volumes. Wait for the
services and verify the demo before the next session.

Stopping Lightsail does not stop its instance bill. If removing a demo
permanently, export the needed database and uploads first, then deliberately
delete resources you no longer need and inspect retained storage, snapshots,
addresses and frontend hosting. A budget alert is a notification, not a hard
spending limit.

## Lambda setup after the required changes

This is a migration sequence; the current repository does not yet contain the
handler, S3 storage layer, SQS worker or SAM template needed to execute it.

1. Install [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   and your chosen infrastructure tool, such as AWS SAM. Authenticate to the
   intended account and verify `aws sts get-caller-identity` before deployment.
2. Choose the PostgreSQL location and price it first. RDS needs a private network
   and appropriate connection management; a compatible database reachable over
   TLS outside a VPC is a different tradeoff. Avoid assuming the database scales
   to zero. Keeping Redis/another always-on worker would retain fixed costs.
3. Add an injected asynchronous object-storage abstraction for original files,
   extracted JSON and preview access. Create a private S3 bucket and authorized,
   tenant-scoped direct uploads; verify file ownership/type/size on submission.
   Use `/tmp` only for processing. See [S3 upload URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html).
4. Add SQS and a dead-letter queue. Separate API submission from worker execution,
   preserve job IDs and tenant ownership, and make repeated message delivery
   idempotent. Start with worker batch size 1 and low concurrency. Configure queue
   visibility to at least six times the worker timeout, with an appropriate
   retry/redrive policy. See [SQS configuration](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html).
5. Replace startup recovery and perpetual workers with invocation-scoped
   processing. Measure representative PDFs; use page/chunk orchestration or an
   on-demand container task if a job cannot finish inside the invocation limit.
6. Create a cloud-only Linux Lambda image in ECR. Use Python 3.11 within this
   project's supported range, add [Lambda Web Adapter](https://github.com/aws/aws-lambda-web-adapter)
   for HTTP, use a dedicated worker entry point, and run Alembic separately.
   Test read-only filesystem startup and bound database pools/concurrency.
7. Define API, worker, S3, SQS, IAM roles, secrets and log retention in SAM or an
   equivalent template. Grant only the bucket/queue access each role needs.
   Configure authenticated application access, exact CORS origins and OAuth
   URLs. Enable and verify response streaming if retaining SSE; check feature
   availability in the chosen Region and integration. Job polling is simpler.
8. If using VPC-connected Lambda with private RDS and an IPv4-only model
   endpoint, plan outbound connectivity. A public subnet alone does not give an
   ordinary Lambda function public internet access. NAT can dominate the bill:
   AWS's Ohio example is $0.045/hour, about $32.85 for 730 hours, before data and
   IPv4. See [VPC internet access](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc-internet.html)
   and [NAT pricing](https://aws.amazon.com/vpc/pricing/).
9. Deploy only after tests cover queue retries, duplicate delivery, cold starts,
   cross-environment source/artifact retrieval, authentication, source previews
   and saved PAPER workflows. Test a document above 6 MB through direct S3 upload
   and the longest supported demo document. Then publish the frontend against
   the new API and verify the complete workflow from a browser.

Lambda is a reasonable future option when low idle cost is worth these changes.
The current full demo can be hosted sooner using the VM procedure above.
