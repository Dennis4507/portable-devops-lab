# Definition of Done — Project 01 (Local, WSL2 + k3d)

> **The checklist half of the DoD.** The mechanical half is
> [`scripts/verify-01-local.sh`](../../../scripts/verify-01-local.sh), run via
> `make verify`. Per CLAUDE.md, **both** must pass. The checklist is for
> understanding; the script is for not lying to yourself about whether it
> actually passed.
>
> **Layer IDs are the canonical 15 from CLAUDE.md** (`L01` Requirements …
> `L15` Cost), not a per-project list. `L00` items are workstation
> prerequisites, which sit deliberately outside the 15 — see spec §3.
>
> Items marked **`[auto]`** have a corresponding check in the verify script
> tagged with the same ID. Items marked **`[human]`** cannot be mechanised:
> they are "can you explain this out loud" checks, which is the entire point
> of this lab and the reason the doc half exists at all.
>
> **A `[human]` item is complete only when you can answer it from memory,
> cold, without opening the repository.**

---

## Layer 00 — Prerequisites (not one of the canonical 15)

- [ ] `L00-1` **`[auto]`** WSL2 has systemd enabled and the Docker daemon responds to `docker info`.
- [ ] `L00-2` **`[auto]`** All pinned tools are installed at the versions in `.tool-versions`.
- [ ] `L00-3` **`[auto]`** `.wslconfig` exists and WSL2's visible memory matches the cap it declares.
- [ ] `L00-4` **`[auto]`** The repository is a git repository with a remote configured.
- [ ] `L00-5` **`[auto]`** `.gitattributes` enforces LF for `*.sh`, `*.yaml`, `*.yml`, `Dockerfile`, and no tracked file of those types contains CRLF.
- [ ] `L00-6` **`[auto]`** No tracked file contains a plaintext secret; `.env` is gitignored.
- [ ] `L00-7` **`[auto]`** `make up`, `make down`, `make verify` and `make cost` all exist.
- [ ] `L00-8` **`[human]`** You can explain why Docker Engine in WSL2 was chosen over Docker Desktop, and what that costs.
- [ ] `L00-9` **`[human]`** You can explain why CRLF breaks a shell script inside a Linux container, and recognise `/bin/bash^M: bad interpreter` on sight.

## Layer 01 — Requirements

- [ ] `L01-1` **`[auto]`** `requirements.md` exists and states both SLIs, both SLOs, RTO and RPO.
- [ ] `L01-2` **`[auto]`** The Layer 13 alert thresholds are traceable to the SLOs (the `HighErrorRate` threshold equals `100% − availability SLO`).
- [ ] `L01-3` **`[human]`** You can state the single stateful component in this system without hesitating, and say what its loss would cost.
- [ ] `L01-4` **`[human]`** You can defend why 4xx is excluded from the availability SLI, and name a case where that exclusion would be wrong.
- [ ] `L01-5` **`[human]`** You recorded RPO as *infinite* before backups existed, and can explain why writing the honest number mattered more than writing a plausible one.

## Layer 02 — IAM

- [ ] `L02-1` **`[auto]`** App pods use a dedicated ServiceAccount, not `default`.
- [ ] `L02-2` **`[auto]`** `automountServiceAccountToken: false`, and no token is mounted inside the running pod.
- [ ] `L02-3` **`[auto]`** The app ServiceAccount has no cluster-scoped write permissions.
- [ ] `L02-4` **`[human]`** You can explain why cloud IAM does not exist in this project, and what specifically appears at project 05 to fill that gap.
- [ ] `L02-5` **`[human]`** You can explain why `docker` group membership equals host root, and connect it to why a ServiceAccount that can create pods is effectively cluster-admin.

## Layer 03 — Network

- [ ] `L03-1` **`[auto]`** The frontend is reachable from the Windows host at `http://localhost:8080`.
- [ ] `L03-2` **`[auto]`** The frontend proxies `/api/` to the API Service (no CORS, no 502).
- [ ] `L03-3` **`[auto]`** CoreDNS resolves `postgres.<ns>.svc.cluster.local` from inside a pod.
- [ ] `L03-4` **`[auto]`** With ≥2 API replicas, 20 sequential `/info` calls return ≥2 distinct hostnames.
- [ ] `L03-5` **`[human]`** You can recite all eight hops from Windows browser to container port, in order, and name what breaks at each.

## Layer 04 — IaC

- [ ] `L04-1` **`[auto]`** `k3d/lab-01.yaml` exists and is the only source of cluster topology — no imperative `k3d cluster create` flags in the Makefile.
- [ ] `L04-2` **`[auto]`** `make down && make up` reproduces identical topology from that file alone. *(Destructive — this is the `FINAL-2` gate.)*
- [ ] `L04-3` **`[human]`** You can state what this layer shares with Terraform (declarative, version-controlled, reproducible) and precisely what it lacks (state, drift detection, plan/apply).

## Layer 05 — Configuration

- [ ] `L05-1` **`[human]`** `whys.md` contains the written list of everything k3d configures invisibly that Ansible must do explicitly at project 02 — kernel modules, sysctls, swap, firewall, time sync, users, the K3s systemd unit.
- [ ] `L05-2` **`[human]`** You can explain why this layer is nearly empty here and is the largest layer at project 02.

## Layer 06 — Build

- [ ] `L06-1` **`[auto]`** `/health` returns 200 in under 500 ms **and issues no database query** (proven by stopping Postgres and confirming `/health` still returns 200).
- [ ] `L06-2` **`[auto]`** `/ready` returns 200 with `checks.database.status == "ok"` and `checks.migrations.status == "ok"`.
- [ ] `L06-3` **`[auto]`** `/ready` returns **503** within 500 ms when Postgres is unreachable, recovering to 200 within 10 s. *(Destructive — run with the Layer 14 exercises.)*
- [ ] `L06-4` **`[auto]`** `/info` returns non-empty `version`, `git_commit`, `hostname`, `node`, `pod_ip`, and `git_commit` matches the deployed image tag.
- [ ] `L06-5` **`[auto]`** `/work?ms=200&mode=cpu` returns `actual_ms` within ±30%; `?ms=999999` returns **400**.
- [ ] `L06-6` **`[auto]`** `/error-test?kind=http_500` returns 500 and increments `app_errors_total{kind="http_500"}`.
- [ ] `L06-7` **`[auto]`** Gated chaos kinds (`panic`, `memory`) return **404** when `ENABLE_CHAOS_ENDPOINTS=false`.
- [ ] `L06-8` **`[auto]`** All app log output is valid JSON on stdout and carries `correlation_id`.
- [ ] `L06-9` **`[auto]`** No container runs as root; all set `runAsNonRoot: true`.
- [ ] `L06-10` **`[auto]`** All containers set `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, and drop all capabilities.
- [ ] `L06-11` **`[auto]`** `.dockerignore` exists and excludes `.git`, `.venv`, `.env`.
- [ ] `L06-12` **`[auto]`** The same image runs under `docker compose` and under Kubernetes, differing only in environment variables.
- [ ] `L06-13` **`[human]`** You can explain why `/health` must not check the database, and describe the specific outage that results when it does.
- [ ] `L06-14` **`[human]`** You can explain what a multi-stage build removes and why that matters for both size and attack surface.

## Layer 07 — CI

- [ ] `L07-1` **`[auto]`** The CI workflow exists and its last run on `main` succeeded.
- [ ] `L07-2` **`[auto]`** `trivy image` reports zero CRITICAL findings outside a documented, dated allowlist.
- [ ] `L07-3` **`[auto]`** `trivy config` over `helm/` and `gitops/` reports zero HIGH findings outside that allowlist.
- [ ] `L07-4` **`[auto]`** The CI workflow contains no `kubectl`, `helm upgrade` or `argocd app sync` step — CI never touches the cluster.
- [ ] `L07-5` **`[human]`** You can defend that separation against "why not just `kubectl apply` from the pipeline?"

## Layer 08 — Registry

- [ ] `L08-1` **`[auto]`** The k3d local registry responds and pods pull from it successfully.
- [ ] `L08-2` **`[auto]`** No pod is in `ImagePullBackOff`.
- [ ] `L08-3` **`[auto]`** No image reference anywhere uses `latest` or is untagged.
- [ ] `L08-4` **`[auto]`** The GHCR pull secret is present as a `SealedSecret` and a pod successfully pulls from GHCR with it.
- [ ] `L08-5` **`[human]`** You can explain why a `latest` tag makes rollback undefined, and why image signing was deferred to Tier 3.

## Layer 09 — Platform

- [ ] `L09-1` **`[auto]`** Three nodes exist and all report `Ready`.
- [ ] `L09-2` **`[auto]`** `kubectl get --raw /healthz` returns `ok`.
- [ ] `L09-3` **`[auto]`** The kubeconfig context is `k3d-lab-01`.
- [ ] `L09-4` **`[auto]`** The Postgres StatefulSet is ready and its PVC is `Bound`.
- [ ] `L09-5` **`[human]`** You can describe the K3s bootstrap: SQLite not etcd in single-server mode, the node token, the 6443 join, and the auto-apply manifests directory.
- [ ] `L09-6` **`[human]`** You can explain why a `local-path` PV pins its pod to one node, and what the resulting failure looks like in `kubectl describe`.

## Layer 10 — Deployment

- [ ] `L10-1` **`[auto]`** `helm lint` passes and the chart templates cleanly for `values-01-local.yaml`.
- [ ] `L10-2` **`[auto]`** Every ArgoCD Application is `Synced` and `Healthy`.
- [ ] `L10-3` **`[auto]`** Alembic reports the database at head and the migration hook Job completed.
- [ ] `L10-4` **`[auto]`** The seed job is idempotent — running it twice does not duplicate products.
- [ ] `L10-5` **`[auto]`** **Drift correction proven:** scaling a Deployment out of band is reverted by ArgoCD within the sync window.
- [ ] `L10-6` **`[human]`** You can explain why migrations run as a Helm hook Job rather than an initContainer, and what that costs on rollback.
- [ ] `L10-7` **`[human]`** You can defend GitOps pull over CI push, including that it needs no inbound connectivity — which is why it works from a laptop behind NAT *and* for a private production cluster.

## Layer 11 — Security

- [ ] `L11-1` **`[auto]`** cert-manager is running and every `Certificate` is `Ready=True`.
- [ ] `L11-2` **`[auto]`** The ingress serves HTTPS using that certificate.
- [ ] `L11-3` **`[auto]`** The sealed-secrets controller is ready and `kubeseal` round-trips a secret.
- [ ] `L11-4` **`[auto]`** No plain Kubernetes `Secret` manifest is committed anywhere — only `SealedSecret`.
- [ ] `L11-5` **`[auto]`** Every container declares CPU/memory **requests and limits**.
- [ ] `L11-6` **`[auto]`** Kyverno is installed and its policy report shows zero violations for the app namespace.
- [ ] `L11-7` **`[auto]`** A default-deny NetworkPolicy exists in the app namespace with explicit allows for frontend→API and API→Postgres.
- [ ] `L11-8` **`[human]`** You can explain why the browser warns on the self-signed certificate, and the difference between encryption and trust.
- [ ] `L11-9` **`[human]`** You can answer: what happens if the sealed-secrets private key is lost, and where should it be backed up?

## Layer 12 — Scaling/HA

- [ ] `L12-1` **`[auto]`** An HPA exists on the API deployment and reports a current metric (not `<unknown>`).
- [ ] `L12-2` **`[auto]`** k6 load against `/work?mode=cpu` scales the deployment out, and it scales back in afterwards.
- [ ] `L12-3` **`[auto]`** The same load against `/work?mode=sleep` does **not** trigger scaling. *(The contrast is the point.)*
- [ ] `L12-4` **`[auto]`** A PodDisruptionBudget exists on the API and blocks a drain that would remove the last replica.
- [ ] `L12-5` **`[auto]`** Pod anti-affinity spreads API replicas across at least two nodes.
- [ ] `L12-6` **`[human]`** You can explain why resource *requests* are the HPA denominator, and what an under-set request does to scaling behaviour.
- [ ] `L12-7` **`[human]`** You can explain why node autoscaling is genuinely N/A here and what replaces it at projects 05 and 06.
- [ ] `L12-8` **`[human]`** Failure exercise run and written up: drain the node holding the Postgres PVC; pod goes `Pending` with a volume node-affinity conflict; recovered by uncordon.

## Layer 13 — Observability

- [ ] `L13-1` **`[auto]`** Prometheus reports `up{job="reference-api"} == 1` for every API replica.
- [ ] `L13-2` **`[auto]`** All metrics named in app spec §3.3 are present in `/metrics`.
- [ ] `L13-3` **`[auto]`** **No `path` label contains a raw numeric ID** — cardinality discipline holds.
- [ ] `L13-4` **`[auto]`** Both alert rules (`HighErrorRate`, `AppNotReady`) are loaded in Prometheus.
- [ ] `L13-5` **`[auto]`** Alertmanager is **not** installed (deferred to Tier 2 per the observability curriculum) — its absence is deliberate, not an oversight.
- [ ] `L13-6` **`[auto]`** Driving `/error-test?kind=http_500&rate=0.5` causes `HighErrorRate` to fire within its `for:` window.
- [ ] `L13-7` **`[auto]`** The RED dashboard is committed as a JSON file, not only in Grafana's database.
- [ ] `L13-8` **`[auto]`** `queries.md` contains at least six working PromQL queries.
- [ ] `L13-9` **`[human]`** You can explain the difference between an alert *rule* and alert *routing*, and why Project 01 has the first without the second.
- [ ] `L13-10` **`[human]`** You can explain why the app's `/metrics` needed no change for this layer, and which observability addition *will* require touching the frozen app, and at which tier.

## Layer 14 — Reliability

- [ ] `L14-1` **`[auto]`** A `pg_dump` CronJob exists and has produced at least one backup artefact.
- [ ] `L14-2` **`[auto]`** **The restore was actually performed:** a table was dropped, restored from the dump, and the data verified. *(An untested backup is a hypothesis.)*
- [ ] `L14-3` **`[auto]`** `requirements.md` has been updated with the *measured* RPO (the backup interval), replacing the original "infinite".
- [ ] `L14-4` **`[auto]`** `helm rollback` to the previous revision succeeds and serves the previous `git_commit` at `/info`.
- [ ] `L14-5` **`[auto]`** **POSITIVE CONTROL:** a pod in an allowed namespace *can* reach `postgres:5432` before the policy is applied.
- [ ] `L14-6` **`[auto]`** **NEGATIVE TEST:** a pod in another namespace *cannot* reach `postgres:5432` after it is applied.
- [ ] `L14-7` **`[auto]`** The frontend can still reach the API after the policy — the allow rule is correct, not merely absent.
- [ ] `L14-8` **`[auto]`** At least one incident is appended to `docs/incidents.md` in the required format.
- [ ] `L14-9` **`[human]`** Failure exercise run and written up: readiness failed on one replica; it left the Service endpoints; **no restart occurred**; no user-visible errors.
- [ ] `L14-10` **`[human]`** Failure exercise run and written up: NetworkPolicy blocks frontend→API; 502 from Traefik; diagnosed from the symptom alone.
- [ ] `L14-11` **`[human]`** You can explain why the positive control must run first, and what a NetworkPolicy test proves on a CNI that does not enforce policy.

## Layer 15 — Cost

- [ ] `L15-1` **`[auto]`** `cost.md` exists containing cost per hour, actual runtime, actual cost, largest cost driver, and the lab-vs-production comparison.
- [ ] `L15-2` **`[auto]`** The lab-vs-production figures are explicitly labelled as estimates pending measurement at project 02.
- [ ] `L15-3` **`[human]`** You can name the largest cost driver in the cloud version of this architecture and explain why ephemeral `apply → destroy` is what protects the €20/month ceiling.
- [ ] `L15-4` **`[human]`** You can explain why OpenCost was deferred rather than installed here.
- [ ] `L15-5` **`[human]`** `whys.md` explains every non-obvious decision — k3d over kind, Traefik retained, sealed-secrets over external-secrets, Kyverno in audit mode, three nodes not one, Alertmanager deferred.

---

## Final gate

- [ ] `FINAL-1` **`[auto]`** `make verify STRICT=1` exits 0 — zero FAIL and zero SKIP.
- [ ] `FINAL-2` **`[auto]`** `make down && make up && make verify` passes from a clean state, inside the 15-minute RTO from Layer 01.
- [ ] `FINAL-3` **`[human]`** A `/recall` session reconstructs this architecture from memory with no material gaps.
- [ ] `FINAL-4` **`[human]`** A `/viva` session scores mid-level or above with no weak area that blocks project 02.
- [ ] `FINAL-5` **`[human]`** `whys.md` is good enough to harvest into `denis-knowledge-base/interview/projects/` — flag it, do not copy it automatically.

> **`FINAL-2` is the one that matters most.** Everything else can be true by
> accident on a cluster hand-patched over three weeks. Only a full teardown
> and rebuild proves that the *repository*, rather than your shell history,
> holds the system — and timing it is what turns the Layer 01 RTO from an
> aspiration into a measurement.
