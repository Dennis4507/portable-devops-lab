# Reference Application — v0 Specification (Tier 1)

> **Status:** Phase 0 — frozen spec, not yet implemented.
> **Scope:** Tier 1 only — `frontend → API → PostgreSQL`. No Redis, no
> worker, no object storage, no tracing.
> **Freeze rule:** this contract is frozen for projects **01, 02, 03 and
> 04** (all of Tier 1). Changing it mid-tier breaks the experiment described
> in CLAUDE.md — the app is the control variable, the infrastructure is the
> independent variable. Any change during Tier 1 requires a stated,
> deliberate exception recorded in this file's changelog, not a quiet edit.

---

## 1. Why this app exists

It is a measuring instrument, not a product. Every endpoint below exists
because some DevOps concept needs a surface to be demonstrated against:

| Endpoint | The concept it makes observable |
|---|---|
| `/health` | Liveness probes, restart loops, the difference between "process alive" and "app working" |
| `/ready` | Readiness probes, rolling updates, endpoint removal, dependency-driven traffic gating |
| `/metrics` | Prometheus scraping, RED metrics, cardinality discipline, alert rules |
| `/info` | Load-balancing, round-robin, canary, region failover — all made *visible* |
| `/work` | CPU load generation → HPA, resource requests/limits, CFS throttling |
| `/error-test` | Error-rate dashboards, alert thresholds, log↔metric correlation, OOMKill, CrashLoopBackOff |
| Business endpoints | A real DB write path, a real transaction, a real constraint violation |

**Design constraint:** the business logic must stay boring. If a design
choice makes the app more interesting but the infrastructure less clear,
choose the other one.

---

## 2. Business domain

An Order/Inventory service. Deliberately dull.

### Data model

```
products
  id                BIGSERIAL PRIMARY KEY
  sku               TEXT NOT NULL UNIQUE
  name              TEXT NOT NULL
  price_cents       INTEGER NOT NULL CHECK (price_cents >= 0)
  stock_qty         INTEGER NOT NULL CHECK (stock_qty >= 0)   -- load-bearing, see below
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()

orders
  id                BIGSERIAL PRIMARY KEY
  order_ref         TEXT NOT NULL UNIQUE        -- ULID, the public handle
  status            TEXT NOT NULL               -- 'created' | 'rejected'
  total_cents       INTEGER NOT NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

order_items
  id                BIGSERIAL PRIMARY KEY
  order_id          BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE
  product_id        BIGINT NOT NULL REFERENCES products(id)
  qty               INTEGER NOT NULL CHECK (qty > 0)
  unit_price_cents  INTEGER NOT NULL            -- price captured at order time
  UNIQUE (order_id, product_id)
```

The `stock_qty >= 0` CHECK constraint is load-bearing for the lab: it makes
an over-sell attempt fail *in the database* rather than in Python, which
produces a genuine `IntegrityError` to observe, log, alert on and later
trace.

### Business endpoints (v0)

| Method | Path | Behaviour |
|---|---|---|
| `GET` | `/api/v1/products` | List products. `?limit=` (default 50, max 200), `?offset=`. |
| `GET` | `/api/v1/products/{id}` | One product, or 404. |
| `POST` | `/api/v1/orders` | Create an order. Decrements stock **inside one transaction** using `SELECT ... FOR UPDATE` on the product rows. Returns 201 + `order_ref`, or **409** when stock is insufficient. |
| `GET` | `/api/v1/orders/{order_ref}` | One order with its items, or 404. |

`POST /api/v1/orders` is the only write path, and it is deliberately the
one place where a row lock, a transaction, a rollback and a business-rule
rejection all live. It is what makes the database matter.

---

## 3. The operational contract

This is the part every project depends on. It does not change within a
tier.

### 3.1 `GET /health` — liveness

**Answers exactly one question:** is this process alive enough to serve
HTTP?

```json
200 OK
{ "status": "alive", "service": "reference-api", "uptime_seconds": 1043.2 }
```

**It must never touch PostgreSQL, or any other network dependency.**

This is the most important rule in the contract and the most commonly
broken one. If `/health` checks the database and the database blips for 40
seconds, the kubelet fails the liveness probe on *every* replica and
restarts all of them — turning a recoverable dependency outage into a
self-inflicted total outage, and destroying in-flight requests that had
nothing to do with the database. Liveness answers "should this container be
killed and restarted"; a database outage is never fixed by restarting the
app.

- Latency budget: under 5 ms. Pure in-memory.
- Returns 200 unconditionally while the process can respond. The only real
  "unhealthy" signal it can produce is failing to respond at all — a wedged
  event loop or a deadlock — which the probe's `timeoutSeconds` catches.
  That is by design, not a gap.
- Probe config: `initialDelaySeconds: 5`, `periodSeconds: 10`,
  `timeoutSeconds: 2`, `failureThreshold: 3`.

### 3.2 `GET /ready` — readiness

**Answers:** should this pod receive traffic *right now*?

Unlike `/health`, this **does** check real dependencies, because "cannot
reach the DB" genuinely means "do not send me requests" — and the correct
response is to remove this pod from the Service endpoints, not to kill it.

Checks performed, in order, under a total budget of **500 ms**
(`READY_TIMEOUT_MS`):

1. **Connection acquire** — take a connection from the SQLAlchemy async
   pool with a 250 ms acquire timeout. A fully checked-out pool is itself a
   not-ready condition and must not be masked by a long wait.
2. **Connection liveness** — `SELECT 1`. Measures round-trip latency to
   Postgres.
3. **Migration check** — read `alembic_version.version_num` and compare it
   to the head revision compiled into the image. Fails when the application
   container is running against a database that has not been migrated to
   its expected schema. Controlled by `READY_CHECK_MIGRATIONS` (default
   `true`). This single check prevents the classic "new pods roll out
   against the old schema, 500s everywhere" incident.

```json
200 OK
{
  "status": "ready",
  "checks": {
    "database":   { "status": "ok", "latency_ms": 3.2 },
    "migrations": { "status": "ok", "version": "a1b2c3d4e5f6" }
  }
}
```

```json
503 Service Unavailable
{
  "status": "not_ready",
  "checks": {
    "database":   { "status": "fail", "error": "connection acquire timeout after 250ms" },
    "migrations": { "status": "skipped" }
  }
}
```

- **503, not 500.** 503 means "temporarily unable, try later", which is what
  a load balancer and a human operator both expect. A 500 here would read
  as an application bug and send the on-call person to the wrong place.
- **No caching beyond 1 second.** Readiness must reflect current truth; a
  cached ready response is a lie that keeps a broken pod in rotation.
- Never returns 200 with a failing sub-check. The detailed body is for
  humans; the status code is for the kubelet.
- Probe config: `initialDelaySeconds: 3`, `periodSeconds: 5`,
  `timeoutSeconds: 2`, `failureThreshold: 3`, `successThreshold: 1`.
- **Drain hook:** `POST /admin/ready/{true|false}` flips an in-memory
  override so readiness can be failed without touching manifests — the
  lever `/incident` mode and graceful-drain exercises pull. **Gated behind
  `ENABLE_CHAOS_ENDPOINTS` (default `false`).** The gate is itself the
  security lesson: a debug endpoint that ships enabled is a
  denial-of-service primitive handed to anyone who can reach the pod.

### 3.3 `GET /metrics` — Prometheus exposition

`Content-Type: text/plain; version=0.0.4; charset=utf-8`. Backed by
`prometheus-client` with `prometheus-fastapi-instrumentator`.

| Metric | Type | Labels | Why it exists |
|---|---|---|---|
| `http_requests_total` | counter | `method`, `path`, `status` | The R and E of RED. Error rate = `status=~"5.."` over total. |
| `http_request_duration_seconds` | histogram | `method`, `path` | The D of RED. Buckets 5ms…10s. Drives p95/p99 via `histogram_quantile`. |
| `db_pool_connections` | gauge | `state` (`in_use`/`idle`) | Pool exhaustion is a top-three cause of "the app is slow but CPU is flat". |
| `db_query_duration_seconds` | histogram | `operation` | Separates "the database is slow" from "the app is slow". |
| `app_orders_created_total` | counter | — | A *business* metric, so dashboards are not purely infrastructural. |
| `app_stock_rejections_total` | counter | — | 409s are expected behaviour, not failures. Proves the alerting distinction. |
| `app_work_iterations_total` | counter | `mode` | From `/work`. |
| `app_work_duration_seconds` | histogram | `mode` | From `/work`. |
| `app_errors_total` | counter | `kind` | From `/error-test` and from real handled errors. |
| `app_ready` | gauge | — | 1/0. Lets you alert on readiness without kube-state-metrics. |
| `app_info` | gauge (= 1) | `version`, `git_commit`, `service` | The standard info-metric pattern — carries build identity as labels. |

Plus the default process and Python collectors
(`process_resident_memory_bytes`, `process_cpu_seconds_total`,
`python_gc_collections_total`, …).

**Cardinality rule — non-negotiable.** The `path` label is the *route
template* (`/api/v1/products/{id}`), never the raw request path. Raw paths
mean one time series per product ID; a few thousand products becomes a few
thousand series per method per status, and Prometheus falls over. This is
the single most common way a team destroys its own monitoring.

**Exposure trade-off.** At Tier 1, `/metrics` is served on the main
application port (8000) because it is the simplest thing that works. The
production-correct answer is a **separate admin port**, not routed through
the ingress, so internal metrics are never reachable from outside. Recorded
here so the shortcut is a known shortcut rather than an oversight; revisit
at Tier 3.

### 3.4 `GET /info` — identity

Makes load-balancing, canaries and failover visible to the naked eye.

```json
200 OK
{
  "service":     "reference-api",
  "version":     "0.1.0",
  "git_commit":  "a1b2c3d",
  "build_time":  "2026-08-28T10:14:03Z",
  "hostname":    "reference-api-5d7f9c4b6-x2k9p",
  "node":        "k3d-lab-01-agent-0",
  "pod_ip":      "10.42.1.17",
  "region":      "local",
  "environment": "dev",
  "tier":        1
}
```

Where each field comes from — this mapping is itself the lesson:

| Field | Source | Mechanism |
|---|---|---|
| `version`, `git_commit`, `build_time` | Docker build args → `ENV` | Baked at **image build time**. Immutable per image, which is the entire point. |
| `hostname` | `HOSTNAME` env var | Kubernetes sets this to the **pod name** automatically. |
| `node` | `NODE_NAME` env var | Downward API — `fieldRef: spec.nodeName`. |
| `pod_ip` | `POD_IP` env var | Downward API — `fieldRef: status.podIP`. |
| `region`, `environment`, `tier` | Helm values → env | Per-deployment, not per-image. |

The demo this enables:

```bash
for i in $(seq 1 20); do
  curl -s http://app.lab.localhost:8080/api/v1/info | jq -r .hostname
done | sort | uniq -c
```

Even distribution proves round-robin. Skewed distribution proves session
affinity, a removed endpoint, or a pod failing readiness. At Tier 4 the
`region` field is what proves failover actually happened.

### 3.5 `GET /work` — controllable CPU load

The thing `k6` drives to trigger autoscaling.

| Param | Default | Range | Meaning |
|---|---|---|---|
| `ms` | `250` | 1 – `WORK_MAX_MS` (10000) | Target duration of work. Out of range returns **400**, not a silent clamp — a load test whose parameters are silently ignored produces false conclusions. |
| `mode` | `cpu` | `cpu` \| `sleep` \| `db` | See below. |

**`mode=cpu`** — busy loop: repeated SHA-256 over a small fixed buffer,
counting iterations until `time.monotonic()` passes the deadline. Runs in a
thread-pool executor via `run_in_executor`, **not** on the asyncio event
loop.

> **The teaching point, stated plainly.** Running the busy loop directly on
> the event loop would block *every* other request on that worker,
> including `/health` — causing the kubelet to fail the liveness probe and
> restart a pod that was merely busy. Moving it to a thread avoids that.
> But Python's Global Interpreter Lock means the thread still contends for
> the interpreter, so throughput still degrades under load — which is
> exactly *why* the answer is multiple uvicorn workers and multiple
> replicas, not more threads. Both halves of that need to be sayable out
> loud.

**`mode=sleep`** — `await asyncio.sleep(ms/1000)`. Burns wall-clock time and
holds a connection, but **zero CPU**. Its entire purpose is contrast: drive
load against `mode=sleep` and watch an HPA configured on CPU utterly fail
to scale while latency and concurrency climb. That is the empirical
argument for scaling on requests-per-second or queue depth instead of CPU.

**`mode=db`** — issues real queries in a loop for the duration, loading the
connection pool and Postgres rather than the app. Shows a saturated pool
alongside idle CPU.

```json
200 OK
{ "mode": "cpu", "requested_ms": 250, "actual_ms": 253.4,
  "iterations": 184203, "hostname": "reference-api-5d7f9c4b6-x2k9p" }
```

`actual_ms` consistently exceeding `requested_ms` is itself a signal: it
means CFS throttling from the container CPU limit. Correlate with
`container_cpu_cfs_throttled_seconds_total`.

### 3.6 `GET /error-test` — controlled failure generator

Exercises error dashboards, alert thresholds and log correlation.

| `kind=` | Effect | HTTP | Gated | What it exercises |
|---|---|---|---|---|
| `http_500` *(default)* | Raises an unhandled exception | 500 | no | Error-rate alerts; stack trace in structured logs with correlation ID |
| `http_4xx&code=422` | Returns the given 4xx | 4xx | no | Proves 4xx must **not** page. Client errors are not availability failures — the SLO-math distinction. |
| `db_error` | Runs `SELECT * FROM table_that_does_not_exist` | 500 | no | A real `ProgrammingError` from Postgres — the database error path end to end |
| `timeout&ms=5000` | Sleeps past the ingress timeout | 504 *(from the proxy)* | no | The difference between an **app** error (500 from the pod) and a **proxy** error (504 from Traefik). Different dashboards, different root causes. |
| `panic` | `os._exit(1)` — kills the process | conn reset | **yes** | CrashLoopBackOff, restart counters, backoff timing, `kubectl logs --previous` |
| `memory&mb=512` | Allocates and holds N MB | 200 or OOMKill | **yes** | Memory limits, OOMKilled vs Evicted, `lastState.terminated.reason` |

**`?rate=0.3`** — apply the chosen failure to that fraction of requests
rather than all of them. Essential for tuning alerts: a 100% error rate
fires everything trivially, whereas a 30% error rate is where threshold and
`for:` duration choices actually get tested.

Every failure increments `app_errors_total{kind=...}` and emits a
structured ERROR log carrying the `correlation_id`, so the
metric → log → (later) trace correlation exercise works end to end.

Gated kinds require `ENABLE_CHAOS_ENDPOINTS=true`; otherwise **404**, not
403 — do not advertise the existence of a disabled capability.

---

## 4. Cross-cutting behaviour

### Logging

Structured JSON to **stdout only** — no files, no rotation, no log shipping
inside the app. Twelve-factor: the platform owns log routing.

```json
{"ts":"2026-08-28T10:14:03.221Z","level":"info","logger":"api.orders",
 "msg":"order created","service":"reference-api","version":"0.1.0",
 "correlation_id":"01J8X...","method":"POST","path":"/api/v1/orders",
 "status":201,"duration_ms":18.4,"pod":"reference-api-5d7f-x2k9p"}
```

`correlation_id` is taken from the inbound `X-Request-ID` header when
present, otherwise generated, and is **echoed back in the response
header**. This is what makes "a user reports a failure and gives you their
request ID" resolve to a single Loki query at project 02.

`LOG_FORMAT=console` gives human-readable output for local development;
`json` everywhere else.

### Configuration — twelve-factor, environment only

No config files. Every setting is an environment variable so that the same
image runs on all ten targets.

```
SERVICE_NAME, APP_VERSION, GIT_COMMIT, BUILD_TIME
ENVIRONMENT, REGION, TIER
LOG_LEVEL, LOG_FORMAT
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
DB_POOL_SIZE (5), DB_MAX_OVERFLOW (5), DB_CONNECT_TIMEOUT_S (5)
READY_TIMEOUT_MS (500), READY_CHECK_MIGRATIONS (true)
ENABLE_CHAOS_ENDPOINTS (false), WORK_MAX_MS (10000)
UVICORN_WORKERS (2)
```

Postgres settings are **split into parts rather than one `DATABASE_URL`** —
deliberately. Host, port, database and user come from a ConfigMap; only
`POSTGRES_PASSWORD` comes from a Secret. A single URL forces the whole
connection string into the Secret, which hides non-sensitive configuration
from `kubectl get configmap` and needlessly widens what has to be encrypted
and rotated.

### Container and process

- Non-root: UID/GID **1000**, `runAsNonRoot: true`,
  `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`,
  `readOnlyRootFilesystem: true` with an `emptyDir` mounted at `/tmp`.
- Multi-stage Dockerfile, final stage on `python:3.12-slim`. No build
  toolchain in the runtime image.
- Image tag = **git short SHA**. Never `latest`, anywhere — `latest` makes
  a rollback undefined and a running cluster unreproducible.
- Graceful shutdown: on `SIGTERM`, immediately fail `/ready`, then finish
  in-flight requests before exiting. `terminationGracePeriodSeconds: 30`.
  Failing readiness *before* refusing connections is what removes the pod
  from the Service endpoints so no new traffic arrives mid-shutdown.
- Ports: API `8000`, frontend `8080`, Postgres `5432`.

---

## 5. Frontend (Tier 1)

A single static HTML page served by `nginxinc/nginx-unprivileged`, which
listens on 8080 as a non-root user. The stock `nginx` image wants port 80,
which requires either root or `CAP_NET_BIND_SERVICE`.

Two panels:

1. **Store** — lists products and places orders. The happy path and the 409
   over-sell path.
2. **Ops** — polls `/info`, `/health` and `/ready` every two seconds and
   shows which pod answered, colour-coded. Round-robin, rolling updates and
   failover become *watchable in a browser*, which is worth considerably
   more than a curl loop when explaining the system to someone else.

nginx reverse-proxies `/api/` to the API Service, so there is no CORS
configuration anywhere. That proxy hop is also what produces the **502**
(all API pods down) and **504** (API too slow) that `/error-test` needs —
the frontend is part of the observability surface, not decoration.

---

## 6. Database and migrations

- **PostgreSQL 16**, in-cluster StatefulSet, single replica, one PVC.
- **This is a lab choice, not a production one.** Production is managed
  Postgres (RDS / Azure Database / Cloud SQL) or an operator such as
  CloudNativePG. A single-replica database on a node-local volume means no
  automatic failover, no point-in-time recovery, and — on the local-path
  provisioner K3s ships with — a volume **bound to one node**, so the pod
  cannot reschedule elsewhere. That last consequence is genuinely
  instructive and is used deliberately as a failure exercise in project 01.
- **Alembic** for migrations, run as a Helm `pre-install,pre-upgrade` hook
  **Job**.
  - *Why a Job rather than an initContainer:* an initContainer runs once per
    pod, so N replicas race N migrations against one database. A hook Job
    runs exactly once per release.
  - *What that choice costs:* the Job must be idempotent, and a failed
    migration blocks the release instead of rolling back cleanly.
    Backwards-compatible expand/contract migrations are the real answer,
    and that is a Tier 2 exercise.
- Seed data: roughly ten products loaded by a separate idempotent seed
  step, so `GET /api/v1/products` is never empty on a fresh cluster and
  smoke tests have something deterministic to assert against.

---

## 7. Explicitly out of scope for v0

Named here so their absence is a decision rather than an omission:

Redis · background workers / Celery (Tier 2) · object storage ·
OpenTelemetry tracing (Tier 3) · authentication and authorization ·
multi-tenancy · rate limiting · caching of any kind · pagination beyond
limit/offset · websockets · file upload · an admin UI · read replicas.

---

## 8. What "the app is done" means

The app is done for Tier 1 when, against a running instance:

- All six contract endpoints behave exactly as specified above.
- `/ready` returns 503 within 500 ms when Postgres is stopped, and returns
  200 again within 10 seconds of Postgres returning — verified by actually
  stopping Postgres, not by reading the code.
- `/metrics` exposes every metric named in §3.3, and no `path` label
  contains a raw ID.
- The container runs as non-root with a read-only root filesystem.
- The same image runs unchanged against Postgres in Docker Compose and
  against Postgres in Kubernetes, differing only in environment variables.

The last item is the real test of the whole design: if the image needs a
change to move between environments, the configuration boundary is in the
wrong place.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-08-28 | v0 spec frozen for Tier 1 | Phase 0 planning |
