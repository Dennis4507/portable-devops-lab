# Project 01 — Local (WSL2 + Docker + k3d)

> **Status:** Phase 0 — spec written, nothing implemented.
> **Tier:** 1 — Own everything.
> **App:** reference app v0, frozen. See
> [`docs/projects/00-reference-app/spec.md`](../00-reference-app/spec.md).
> **Layers:** the canonical 15-layer lifecycle in CLAUDE.md, walked in order
> in §4 below. No competing per-project list.
> **Cost:** €0 direct. See Layer 15.

---

## 0. What this project is actually for

Project 01 is not "get the app running locally." It is the **rehearsal for
project 02** (Hetzner VM + K3s). Every decision below is judged against one
question: *does doing it this way here make project 02 easier or harder?*

Anything learned here that has to be unlearned at project 02 is a bad choice
for this project, even if it is a good choice in general. That single
criterion decides the k3d-vs-kind question below and most of the rest.

---

## 1. k3d or kind? — recommendation and reasoning

**Recommendation: k3d.** Not close, for *this* lab.

Both tools run Kubernetes inside Docker containers on the same WSL2 Docker
daemon, both support multi-node, both are free, both are mature. The
difference is *which Kubernetes*.

- **kind** — "Kubernetes IN Docker". Runs upstream, kubeadm-bootstrapped
  Kubernetes. It is what the Kubernetes project itself uses for conformance
  testing.
- **k3d** — a thin wrapper that runs **K3s** (Rancher's lightweight
  Kubernetes distribution) in Docker containers.

### Why k3d wins here

**1. Projects 02, 03, 04, 05 and 06 are all K3s.** That is the whole of
Tier 1 and Tier 2 — five of the ten projects. k3d gives the identical
distribution: the same bundled Traefik ingress controller, the same ServiceLB
(klipper) LoadBalancer implementation, the same local-path-provisioner
default StorageClass, the same containerd runtime, the same
`/etc/rancher/k3s/` layout and the same `--disable` flags. Muscle memory
transfers directly from `k3d cluster create` to Ansible installing K3s on a
Hetzner VM. With kind, the defaults differ enough that a chunk of what you
learn at 01 is wrong at 02.

**2. `type: LoadBalancer` actually resolves.** k3d runs a `serverlb` proxy
container in front of the cluster and K3s ships ServiceLB, so a LoadBalancer
Service gets an address and the published Docker port works. On kind, a
LoadBalancer Service sits at `<pending>` forever unless you additionally
install MetalLB or `cloud-provider-kind`. That is real friction on the exact
path the reference app needs, and it teaches a workaround that does not exist
at project 02.

**3. The registry story is closer to real.** `k3d registry create` stands up
a registry container *and* writes the containerd registry-mirror
configuration into the nodes automatically — the same shape as a real private
registry with a pull path, which is the Layer 08 lesson. kind's
`kind load docker-image` sideloads the image into the node filesystem: fast
and convenient, but it teaches a mechanism that exists nowhere else and skips
the registry entirely.

**4. Lighter, which matters inside WSL2.** A K3s server uses roughly half the
memory of a kubeadm control plane. With three nodes plus Postgres plus
Prometheus plus Grafana plus ArgoCD on one laptop, that headroom is not
academic.

### The honest counter-argument

kind is closer to vanilla upstream Kubernetes, and Tier 3 (AKS, EKS, GKE) is
upstream, not K3s. If Tier 3 were next, kind would be the better rehearsal.
But Tier 3 is six projects away, and by then the rehearsal happens on real
managed clusters rather than locally. K3s' divergences from upstream are also
mostly *additive* — bundled components you can disable — rather than
behavioural, so the transfer cost is low.

**Where the difference will actually bite, and the plan for it:** K3s bundles
Traefik, whereas AKS/EKS/GKE ship no ingress controller at all. Mitigation:
swapping Traefik for ingress-nginx is scheduled as an explicit exercise at
project 03, once the Traefik path is solid — sequenced, not skipped.

### Second decision: Docker Desktop or Docker Engine inside WSL2?

**Recommendation: Docker Engine (`docker-ce`) installed natively inside the
WSL2 Ubuntu distribution.** Not Docker Desktop.

- No licensing question for commercial use.
- The Docker daemon becomes a systemd service on a Linux host — exactly what
  you configure with Ansible at project 02. Docker Desktop's Windows-side
  daemon with a WSL2 backend is an abstraction that exists nowhere in
  Tiers 1–4.
- One fewer moving part between you and the container runtime when debugging.

What it costs: no automatic start on boot, no Windows-side GUI. Fix by
enabling systemd in WSL2 via `/etc/wsl.conf`:

```ini
[boot]
systemd=true
```

(requires WSL 0.67.6+), then `sudo systemctl enable --now docker`.

### Third decision: where the repository lives

The repo is currently at `C:\Users\OnlyM\Denis Cloud Projects\portable-devops-lab`
— on the Windows filesystem, reachable from WSL2 as `/mnt/c/...`.

**Recommendation: move the working copy onto the WSL2 ext4 filesystem**
(e.g. `~/lab/portable-devops-lab`) and edit through VS Code's WSL remote
extension.

Cross-boundary access via `/mnt/c` goes through the 9p protocol, roughly an
order of magnitude slower for the many-small-files operations that Docker
builds, `helm template` and `git status` all perform — and `inotify`
file-watching does not fire reliably across the boundary, which breaks
hot-reload outright.

A genuine trade-off, not a free win: the files become less convenient to
reach from Windows-native tools. Keeping the repo on the Windows side is a
legitimate choice — the slow builds are then a known cost rather than a
mystery to debug later.

---

## 2. Target architecture

```
Windows 11 host
└── WSL2 (Ubuntu 22.04/24.04), systemd enabled
    └── Docker Engine (docker-ce), native
        ├── k3d-registry.localhost:5000          ← local image registry
        └── k3d cluster "lab-01"
            ├── k3d-lab-01-serverlb              ← nginx, publishes :8080 → :80
            ├── k3d-lab-01-server-0              ← K3s control plane (SQLite)
            ├── k3d-lab-01-agent-0
            └── k3d-lab-01-agent-1

Inside the cluster:
  traefik            (kube-system)   ingress controller, K3s default
  local-path         (kube-system)   default StorageClass
  metrics-server     (kube-system)   K3s default — makes HPA possible at Tier 1
  cert-manager       (platform)      self-signed ClusterIssuer
  sealed-secrets     (kube-system)   offline-capable GitOps secrets
  kyverno            (platform)      policy, audit mode
  prometheus/grafana (observability) metrics only at this tier
  argocd             (argocd)        pulls from GitHub, syncs gitops/
  reference-app      (app)           frontend → api → postgres
```

**Three nodes, not one**, deliberately: scheduling, node affinity,
`kubectl drain`, pod anti-affinity, PodDisruptionBudgets and "which node is
my PVC pinned to" are all meaningless on a single node, and every one of them
is a Tier 1 concept.

**Access path:** `k3d cluster create -p "8080:80@loadbalancer"` publishes port
8080 on the WSL2 host; WSL2's localhost forwarding makes
`http://localhost:8080` work from a Windows browser. Hostname routing uses
`*.localhost` names (`app.lab.localhost`, `api.lab.localhost`), falling back
to entries in both `C:\Windows\System32\drivers\etc\hosts` and WSL2's
`/etc/hosts` if any tool refuses to resolve them.

---

## 3. Layer 0 — Prerequisites (deliberately *not* one of the 15)

The canonical 15 layers describe **the workload's lifecycle**, not the
workstation it is driven from. Project 01 is the only project where the
workstation is also the infrastructure, so its setup is recorded here as a
Layer 0 rather than distorting the canonical list. At projects 02–10 this
reduces to "have the CLIs installed".

- WSL2 with systemd enabled; Ubuntu 22.04 or 24.04.
- `.wslconfig` on the Windows side (`C:\Users\OnlyM\.wslconfig`) capping
  memory and CPU — WSL2 will otherwise balloon to a large fraction of host
  RAM and starve Windows. Starting point: `memory=10GB`, `processors=6`,
  `swap=4GB`. Tune after measuring.
- Docker Engine native in WSL2; user in the `docker` group.
- Pinned tool versions in `.tool-versions`, so versions are reproducible and
  comparable to project 02: `k3d`, `kubectl`, `helm`, `k9s`, `jq`, `yq`,
  `trivy`, `k6`, `argocd`, `kubeseal`.
- **`git init` plus a GitHub remote.** This repository is **not currently a
  git repository**. That is a hard blocker for Layer 10, since ArgoCD's only
  input is a git repository — so it happens first, not last.
- `.gitattributes` enforcing `* text=auto eol=lf`, with `*.sh`, `*.yaml`,
  `*.yml` and `Dockerfile` pinned to `eol=lf`. **Windows-specific necessity,
  not boilerplate:** git's `core.autocrlf` will otherwise rewrite shell
  scripts with CRLF endings, and a CRLF script inside a Linux container fails
  with the famously unhelpful `/bin/bash^M: bad interpreter`.
- Root `Makefile` exposing `up`, `down`, `verify`, `cost`. The Makefile is
  the stable interface: `make up` must mean the same thing at project 09 as
  here, even though what it does underneath is entirely different.

**Known WSL2 traps, documented up front because each costs an hour the first
time:** the WSL2 VM IP changes on every Windows reboot (harmless here, since
access is via localhost forwarding, but it breaks anything hardcoding it);
`ext4.vhdx` grows and never automatically shrinks; Docker Engine will not
start without systemd enabled.

**DoD convention decision (CLAUDE.md asks for this to be settled on Project
01 and then kept):** use **`scripts/verify-<NN-name>.sh`**, not
`terraform/projects/<NN-name>/verify.sh`. Decisive reason: project 01 has no
`terraform/projects/01-local/` directory at all — it is explicitly a
no-Terraform project — so the alternative convention has nowhere to put this
project's script. A convention that cannot express its own first project is
the wrong convention. Project 01's script is therefore
[`scripts/verify-01-local.sh`](../../../scripts/verify-01-local.sh).

---

## 4. The 15 layers, applied to this project

Walked in canonical order. Where a layer is trivial or genuinely absent
locally, that is stated explicitly and the reason given — per CLAUDE.md, "this
doesn't apply here, and here's why" is itself the deliverable.

---

### Layer 01 — Requirements · *What does this workload need?*

Nothing gets built in this layer; it is where the targets everything else is
measured against get written down. Skipping it is how a project ends with a
dashboard nobody can interpret because no one ever said what "good" was.

**SLIs** (what is measured):
- *Availability* — proportion of requests to `/api/v1/*` returning non-5xx.
  4xx is explicitly excluded: a client sending a malformed order is not the
  service failing.
- *Latency* — p95 of `http_request_duration_seconds` for `GET /api/v1/products`.

**SLOs** (the target, deliberately loose for a laptop, and stated so the
alert thresholds in Layer 13 have a source):
- Availability ≥ 99% over a rolling 1h window.
- p95 latency < 300 ms.

These numbers are lab numbers. Their job is to make the *reasoning* real, not
the figures — the exercise is defending why 99% over 1h is loose and what
changes at 99.9% over 30 days.

**RTO / RPO** (recovery time / recovery point objectives):
- RTO: rebuild the entire cluster from the repository in under 15 minutes.
  That is a real, testable target — it is the `FINAL-2` gate.
- **RPO: currently infinite, and that is the finding.** With no backup, the
  data loss window on losing the Postgres PVC is *everything*. Naming that
  here is what motivates the backup/restore work in Layer 14. Writing an
  honest RPO of "total loss" in Layer 01 and then fixing it in Layer 14 is
  the intended arc.

**Traffic:** single developer, plus k6-generated load. No real concurrency
requirement — which means every capacity number produced in this project is
synthetic, and must be labelled as such rather than quoted later as evidence.

**State:** exactly one stateful component (PostgreSQL). Everything else is
disposable. Being able to name the single stateful thing in a system, quickly
and correctly, is most of disaster planning.

**Verification:** `docs/projects/01-local/requirements.md` exists and the
Layer 13 alert thresholds visibly derive from the SLOs above rather than from
round numbers picked by feel.

---

### Layer 02 — IAM · *Who can do what?*

**The cloud IAM half of this layer does not exist at project 01.** No IAM
control plane, no roles, no policies, no workload identity, no OIDC
federation. Saying that plainly is the point: when `modules/iam/azure`
appears at project 05, its purpose is clear by contrast rather than absorbed
as ambient ceremony.

**What genuinely does exist locally, and is not trivial:**

- **Kubernetes RBAC** — a dedicated ServiceAccount per workload;
  `automountServiceAccountToken: false` on anything that does not call the API
  server. The reference app never talks to Kubernetes, so a mounted token is
  pure attack surface with no benefit. A least-privilege Role/RoleBinding for
  anything that does need API access.
- **The Linux identity boundary** — containers run as UID 1000, not root.
- **The real local security boundary, worth naming out loud:** membership in
  the `docker` group is equivalent to root on the WSL2 host, because anyone
  who can reach the Docker socket can start a privileged container that mounts
  `/`. That is the same reasoning that makes a Kubernetes ServiceAccount with
  `create pods` permission effectively cluster-admin — the concept transfers
  exactly even though the local implementation is trivial.

**Verification:**
`kubectl auth can-i --list --as=system:serviceaccount:app:reference-api`
returns a minimal set; `ls /var/run/secrets/kubernetes.io/` inside the app pod
finds nothing.

---

### Layer 03 — Network · *How does traffic flow?*

No VPC, no subnets, no NAT gateway, no cloud firewall — those arrive at
project 02. What exists locally is the entire in-cluster network path, which
is most of what actually breaks in production anyway.

- K3s pod CIDR `10.42.0.0/16`, service CIDR `10.43.0.0/16` — K3s defaults,
  kept unchanged so the numbers recur at project 02 and become familiar
  rather than arbitrary.
- CoreDNS: `<svc>.<ns>.svc.cluster.local` resolution, demonstrable from inside
  a pod.
- Traefik as ingress (K3s default, retained deliberately — see §1).
- Ingress routes for `app.lab.localhost` and `api.lab.localhost`.

**The full path, which should be recitable from memory by the end of the
project:**

```
Windows browser
  → WSL2 localhost forwarding
  → published Docker port 8080
  → k3d-serverlb (nginx) container
  → node port 80
  → Traefik pod
  → Service (ClusterIP)
  → kube-proxy iptables/IPVS rule
  → pod IP : container port
```

Eight hops, *every one of which can break independently* — which is precisely
why this is the diagnostic chain `/incident` mode will exercise.

**Verification:** `curl` reaches the frontend from Windows; `nslookup`
resolves the API Service from a debug pod; deliberately break one hop and
identify which one from the symptom alone.

---

### Layer 04 — IaC · *Can I reproduce everything?*

**There is no Terraform at project 01, by design** — CLAUDE.md's repo tree
states `01-local/ (no terraform — k3d/kind)`. There is no cloud API to call
and no state worth managing remotely.

**The underlying principle still applies and is what actually gets practised:**
the cluster must be defined *declaratively and in version control*, not
created by an imperative command line whose flags live only in shell history.
So this layer produces a **k3d cluster config file** (`k3d/lab-01.yaml`,
consumed by `k3d cluster create --config`) declaring node counts, port
mappings, registry wiring and K3s flags.

That file is project 01's Terraform, and the parallel is worth being able to
state precisely: *declarative, version-controlled, reviewable, and produces
the same cluster every time it is applied.*

**What is missing compared to real Terraform, named explicitly so project 02
lands properly:** **state**. k3d has no state file, no drift detection, and no
plan/apply distinction. It cannot tell you that someone changed something out
of band, and it has no concept of "what would this change if I ran it".
Meeting `terraform plan` for the first time with that gap already articulated
is the difference between it being a revelation and it being a ceremony.

**Verification:** `make down && make up` reproduces identical cluster topology
from the config file alone, with no additional flags.

---

### Layer 05 — Configuration · *How are machines prepared?*

**Almost entirely absent at project 01, and that is worth sitting with.** k3d
nodes are containers running Rancher's `rancher/k3s` image. There is no OS to
configure, no SSH, no package manager to manage, no firewall, no systemd unit
for K3s — the container *is* the unit. The only host that genuinely exists is
the WSL2 distribution itself, configured manually in Layer 0 (automating a
single developer workstation is not worth the Ansible).

**This is the single largest structural difference between project 01 and
project 02.** At project 02 this layer becomes the main event: SSH key
distribution, `apt` package state, kernel modules (`br_netfilter`, `overlay`),
sysctls (`net.ipv4.ip_forward`), swap disabled, `ufw` rules, `chrony` time
sync, an unprivileged `k3s` user, unattended security upgrades. Every one of
those is a real requirement that k3d has already solved invisibly on your
behalf.

**Being able to list what k3d hid from you is the actual deliverable of this
layer at project 01.** Write it into `whys.md` *before* starting project 02,
then check it afterwards — the delta between the predicted list and the real
Ansible role is a precise measurement of what this layer taught.

**Verification:** the written list exists and survives contact with project 02.

---

### Layer 06 — Build · *How is software packaged?*

Note the canonical list has no "write the application" layer, and that is
correct rather than an omission: the app is frozen for all of Tier 1, so at
projects 02, 03 and 04 there is literally nothing to write and Build's input
is a given. **Project 01 is the one project in Tier 1 where implementing the
app happens at all** — and if it ever recurs at 02–04, the tier discipline
has been broken and should be called out loudly.

At project 01:

- Implement reference app v0 exactly as frozen in the
  [app spec](../00-reference-app/spec.md) — FastAPI service, six contract
  endpoints, four business endpoints, structured JSON logging, env-only
  configuration, plus the static frontend.
- Multi-stage Dockerfiles for API and frontend; final stage on
  `python:3.12-slim` / `nginxinc/nginx-unprivileged`. No build toolchain in
  the runtime image.
- Non-root UID 1000, read-only root filesystem, all capabilities dropped.
- `.dockerignore` — omitting it silently ships `.git`, `.venv` and every local
  secret into the build context and often into the image itself.
- Build args carrying `GIT_COMMIT`, `APP_VERSION` and `BUILD_TIME` through to
  the environment variables `/info` reads.
- A `docker-compose.yml` running api + postgres + frontend with no Kubernetes
  at all. Its purpose is not convenience: it is the **control experiment**
  proving the image is genuinely portable across environments via
  configuration alone (app spec §8, final bullet).

**Verification:** `docker compose up` and every contract endpoint behaves as
specified; `docker image inspect` shows the expected non-root user; `/info`
reports the correct commit.

---

### Layer 07 — CI · *How do changes become artifacts?*

**GitHub Actions**, on push to `main`: lint → unit tests → build image →
Trivy scan → push to registry → commit the new image tag into
`gitops/argocd/`.

- Trivy fails the build on HIGH or CRITICAL findings, with a documented,
  time-boxed allowlist for anything deliberately accepted. An allowlist with
  no expiry date is just a decision to stop looking.
- IaC scanning (`trivy config`) over the Helm charts and Kubernetes manifests.
- **The split that matters: CI pushes an image and updates a manifest. CI
  never touches the cluster.** That separation is the whole point of GitOps
  and is worth being able to defend against the obvious "why not just
  `kubectl apply` from the pipeline?"

**Verification:** a push to `main` produces a new tagged image and a manifest
commit, and touches the cluster not at all.

---

### Layer 08 — Registry · *Where do immutable images live?*

Two registries at project 01, deliberately:

- **`k3d registry create registry.localhost --port 5000`** — the local
  registry, which also wires containerd's registry-mirror config into the
  nodes. This is the fast inner loop.
- **GHCR** — where CI pushes. The GHCR pull secret is delivered as a
  `SealedSecret` (Layer 11), which makes the private-registry authentication
  path a real exercise rather than a skipped one.

Immutability rules: tags are the **git short SHA**, never `latest`, anywhere.
`latest` makes a rollback undefined and a running cluster unreproducible —
`kubectl describe` will happily tell you the pod runs `app:latest` while
telling you nothing at all about what code that is.

**Image signing (cosign) is explicitly deferred to Tier 3**, where a real
registry with an OIDC identity makes keyless signing meaningful. Locally it
would be theatre.

**Verification:** a pod pulls successfully from the local registry; a pod
pulls successfully from GHCR using the sealed pull secret; no image reference
anywhere is untagged or `latest`.

---

### Layer 09 — Platform · *Where does the workload execute?*

`k3d cluster create --config k3d/lab-01.yaml` — one command that hides the
entire bootstrap. The deliverable here is therefore **not running the
command**; it is being able to describe what it did:

- The K3s server starts and initialises its datastore — **SQLite by default
  in single-server mode, not etcd.** That is an important detail and the
  reason `--cluster-init` exists for embedded-etcd HA at project 05.
- A node token is generated at `/var/lib/rancher/k3s/server/node-token`.
- Agents join using that token against the server on port **6443**.
- The server writes a kubeconfig; k3d rewrites its `server:` address to the
  host-reachable port and merges it into `~/.kube/config`.
- Bundled manifests in `/var/lib/rancher/k3s/server/manifests/` are applied
  automatically — CoreDNS, Traefik, ServiceLB, local-path, metrics-server.
  That auto-apply directory is a K3s-specific mechanism and is exactly where a
  "why did my deleted resource come back?" mystery originates.

**Storage lives here too**, since it determines where a workload *can*
execute: `local-path` is the default StorageClass, and Postgres gets a
StatefulSet with one PVC on it.

**The instructive limitation, used deliberately later:** `local-path` creates
a `hostPath`-backed volume on one specific node, and the resulting PV carries
a node affinity. If that node goes away, the Postgres pod cannot be
rescheduled — it stays `Pending` with a volume node-affinity conflict, *not*
`CrashLoopBackOff`. Recognising the difference between those two failure
signatures on sight is worth more than any amount of reading about
StorageClasses. Exercised in Layer 12.

**Verification:** three nodes `Ready`; `kubectl get --raw /healthz` returns
`ok`; kubeconfig context correct and scoped to this cluster; you can state
which components K3s started that upstream Kubernetes would not have.

---

### Layer 10 — Deployment · *How does production match Git?*

- **Helm chart** at `helm/reference-app/` — one chart, one values file per
  project. The chart must be written so projects 02–10 change only
  `values-<project>.yaml`, never the templates. If a later project needs a
  template change, that is a signal the chart's abstraction was wrong; record
  it as such rather than patching over it.
- **Migrations** run as a Helm `pre-install,pre-upgrade` hook **Job**.
  - *Why a Job rather than an initContainer:* an initContainer runs once per
    pod, so N replicas race N migrations against one database. A hook Job runs
    exactly once per release.
  - *What that choice costs:* the Job must be idempotent, and a failed
    migration blocks the release instead of rolling back cleanly.
    Backwards-compatible expand/contract migrations are the real answer, and
    that is a Tier 2 exercise.
- **Idempotent seed job** loading ~10 products, so `GET /api/v1/products` is
  never empty on a fresh cluster and smoke tests have something deterministic
  to assert against.
- **ArgoCD** in-cluster, app-of-apps pattern, source = the GitHub repository.
  - **The property that makes this work locally at all:** ArgoCD *pulls*.
    GitHub never needs to reach into the laptop; no inbound connectivity, no
    tunnel, and the cluster can sit behind NAT. That is also precisely why
    GitOps is the standard for private production clusters — the local
    constraint and the production justification are the same constraint.
  - **Prove drift correction:** `kubectl scale` a Deployment out of band and
    watch ArgoCD revert it. That single demonstration is the most convincing
    argument for GitOps there is.

**Verification:** a commit to `main` results in a new pod running the new
image with no human running `kubectl`; every Application reports `Synced` and
`Healthy`; a manual out-of-band change is reverted automatically.

---

### Layer 11 — Security · *How is runtime protected?*

1. **Secrets — sealed-secrets (Bitnami).** Chosen over external-secrets at
   this tier because it works fully offline with no cloud secret store, and
   because it is genuinely GitOps-correct: a `SealedSecret` is safe to commit
   to a public repository, whereas a plain Kubernetes `Secret` is base64 —
   *encoding, not encryption*, readable by anyone with the file. It also
   raises the right disaster question: **what happens if the controller's
   private key is lost?** (Every sealed secret in the repository becomes
   permanently undecryptable. So the key needs backing up — which is itself a
   secret-management problem. The recursion is the lesson.) External-secrets
   against a real provider arrives at Tier 2/3.
2. **TLS — cert-manager with a self-signed ClusterIssuer.** Let's Encrypt is
   impossible locally (no public DNS, no reachable HTTP-01 or DNS-01
   challenge), but the plumbing is identical: Issuer → Certificate → Secret →
   Ingress `tls:`. The browser will warn, and that warning is itself the
   lesson: it is a failure of **trust chain**, not of encryption. The traffic
   is genuinely encrypted; nothing vouches for the identity. Those are
   different properties and conflating them is extremely common.
3. **NetworkPolicy** — default-deny in the app namespace, with explicit allows
   for frontend→API and API→Postgres. Exercised and *proven* in Layer 14.
4. **Pod-level hardening** — `runAsNonRoot`, `readOnlyRootFilesystem`,
   `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, resource
   requests **and** limits on every container.
5. **Policy — Kyverno in `audit` mode** with three policies: require resource
   limits, disallow `latest` tags, require `runAsNonRoot`. Audit rather than
   enforce so violations are visible before they are blocking; flipping to
   `enforce` is a project 02 exercise.

**Verification:** a `Certificate` reaches `Ready=True` and produces a Secret;
`kubeseal` round-trips; no plain `Secret` manifest is committed anywhere;
Kyverno's policy report shows zero violations for the app namespace.

---

### Layer 12 — Scaling/HA · *What happens under pressure or failure?*

Locally constrained, but far less N/A than it first appears — **K3s bundles
metrics-server, so HPA genuinely works at Tier 1.** That was easy to
under-scope.

**What is real here:**

- **HPA on the API deployment**, targeting CPU. `/work?mode=cpu` driven by k6
  is what pushes it over the threshold. The full loop — load → CPU rises above
  the request → HPA scales out → latency recovers — is observable locally.
- **The `/work?mode=sleep` contrast, which is the actual lesson.** Drive the
  same load against `mode=sleep` and watch a CPU-based HPA utterly fail to
  scale while latency and concurrency climb. That is the empirical argument
  for scaling on requests-per-second or queue depth instead of CPU, and it is
  far more convincing demonstrated than asserted.
- **Resource requests as the HPA denominator** — an under-set request makes
  utilisation percentages meaningless and scaling noisy. Demonstrate by
  halving the request and re-running.
- **PodDisruptionBudget** on the API, then `kubectl drain` a node and watch
  the PDB refuse to let the last replica go.
- **Pod anti-affinity** spreading API replicas across the three nodes — which
  is why three nodes exist.
- **The node-pinned PVC constraint from Layer 09**, exercised here: drain the
  node holding the Postgres PVC and observe `Pending` with a volume
  node-affinity conflict. This is the concrete demonstration that *stateless
  and stateful workloads have different HA stories*, and that adding replicas
  does nothing for the stateful one.

**What is genuinely N/A:** cluster/node autoscaling. The three nodes are
fixed containers; there is no cloud API to request a fourth. Node autoscaling
arrives at projects 05 and 06 (VMSS / ASG), and *that* is the layer's main
event there.

**Verification:** k6 against `/work?mode=cpu` scales the deployment out and
back in; the same load against `mode=sleep` does not; the PDB blocks a drain
that would take the last replica.

---

### Layer 13 — Observability · *How do I know what's happening?*

Per CLAUDE.md's observability curriculum: **Tier 1 is metrics only.** Loki
arrives from project 02, OpenTelemetry + Tempo at Tier 3.

**A distinction the curriculum makes that is worth stating precisely:**
Alertmanager is a Tier 2 addition, but CLAUDE.md's baseline requires alerts at
every project. Both hold, because they are different things — **Prometheus
evaluates alert *rules* on its own** and shows them firing in its UI;
**Alertmanager does *routing*** — grouping, deduplication, silencing,
delivery to a destination. Project 01 gets real alert rules with no routing.
Nothing is being skipped; the notification path is what is deferred, and it is
deferred to the tier where a worker and a queue make on-call routing
meaningful rather than academic.

At project 01:

- `kube-prometheus-stack`, trimmed for a laptop: retention 6h, no persistent
  volume for Prometheus, most bundled dashboards disabled, **Alertmanager
  disabled** (Tier 2, per above — and it saves memory).
- A `ServiceMonitor` scraping the app's `/metrics`.
- **One dashboard actually built, not imported** — RED for the reference app:
  request rate by route, error ratio (`5xx / total`, with 4xx excluded per the
  Layer 01 SLI definition), p50/p95/p99 from the histogram, plus `app_ready`
  and pod restart count.
- **Two alert rules whose thresholds derive from the Layer 01 SLOs**, not from
  round numbers:
  - `HighErrorRate` — 5xx ratio > 1% for 5 minutes. The 1% comes directly from
    the 99% availability SLO. The `for: 5m` is what makes
    `/error-test?kind=http_500&rate=0.3` a genuine tuning exercise rather than
    a trivially-firing one.
  - `AppNotReady` — `app_ready == 0` for 2 minutes; deliberately shorter,
    because readiness failure is a more specific and less noisy signal than an
    error ratio.
- Named PromQL queries in `docs/projects/01-local/queries.md` — CLAUDE.md is
  explicit that installing Prometheus is not the deliverable; the queries are.

**Verification:** `up{job="reference-api"} == 1`; driving
`/error-test?rate=0.5` fires `HighErrorRate` within the expected window; the
dashboard reacts visibly to `/work` load.

---

### Layer 14 — Reliability · *Can I break and recover it?*

The canonical layer names **backup and restore** alongside chaos and
rollback — and that is the gap Layer 01's honest "RPO: infinite" finding
pointed at. Fixing it here closes the arc.

**Backup / restore:**

- A `pg_dump` CronJob writing to a PVC, plus a documented restore procedure.
- **The restore must actually be performed, not just written down.** Drop a
  table, restore from the dump, verify the data. An untested backup is a
  hypothesis, not a backup — and this is the cheapest environment in the whole
  lab in which to learn that.
- Re-state the RPO afterwards: it moves from *infinite* to *the backup
  interval*. That measured change is the deliverable.

**Rollback:**

- `helm rollback` and ArgoCD revert-to-previous-commit, both exercised.
- The immutable-SHA tagging from Layer 08 is what makes rollback meaningful —
  demonstrate that rolling back to a `latest`-tagged image would be undefined.

**Failure exercises** (CLAUDE.md requires at least one; three are specified,
because they exercise structurally different failure modes):

1. **Node-pinned PVC** — cordon and drain the node holding the Postgres PVC.
   Expected: `Pending`, not `CrashLoopBackOff`, with a volume node-affinity
   conflict in the events. Reversible via `uncordon`.
2. **Readiness failure** — `POST /admin/ready/false` on one replica. Expected:
   that pod leaves the Service endpoints within roughly one probe period,
   traffic continues on the others with zero user-visible errors, and the pod
   is **not restarted** (readiness ≠ liveness). Reversible.
3. **NetworkPolicy block** — the frontend→API allow rule removed under
   default-deny. Expected: 502 from Traefik. The canonical `/incident`
   scenario for this project.

**Security validation — the deliberate assumption-violating check CLAUDE.md
requires:** from a throwaway pod in a different namespace, attempt to reach
`postgres.app.svc.cluster.local:5432`. It **must** fail.

> ⚠️ **Verify enforcement before trusting this test.** K3s ships a
> NetworkPolicy controller, but a policy applied to a cluster that does not
> enforce it is *silently inert*, and the test then passes for entirely the
> wrong reason. So run a **positive control first**: confirm the connection
> **succeeds** before the policy is applied and **fails** after. A security
> test that has never been observed failing is not evidence of anything.

**Verification:** the restore produces correct data; each failure exercise is
written up in `docs/incidents.md` in the required format.

---

### Layer 15 — Cost · *Is this architecture economically sensible?*

`docs/projects/01-local/cost.md`:

- **Direct cost: €0.** No cloud resources exist.
- Real cost: electricity, and roughly 12 GB of RAM while running. Record the
  actual wall-clock runtime anyway, so the €0 result is comparable *in form*
  to project 02's non-zero one — the discipline of recording it matters more
  here than the number.
- **The lab-design vs production-design comparison CLAUDE.md requires** — what
  this same architecture would cost as real infrastructure. Order of magnitude
  only; **these are estimates to be replaced with measured figures at project
  02, not quoted as fact:** three small VMs on Hetzner is roughly €10–15/month;
  the equivalent on Azure or AWS is several times that; managed Kubernetes
  adds a control-plane charge on top (free on AKS's standard tier, roughly
  $70/month on EKS).
- **The largest cost driver in every cloud version of this architecture is
  compute node-hours** — not storage, not egress. Which is exactly why the
  ephemeral `apply → practice → destroy` discipline in CLAUDE.md is the thing
  that actually protects the €20/month ceiling. OpenCost is deferred: with no
  provider billing data to attribute, it would produce numbers with nothing
  behind them.

**Verification:** `cost.md` contains cost/hour, actual runtime, actual cost,
largest cost driver, and the lab-vs-production comparison.

---

## 5. Build order for the `/build` sessions

Layers group into six sessions of roughly three steps each, matching the
pacing in `build.md`. Note the canonical order is not always the *build*
order — Layer 01 (Requirements) is written first, but Layers 02 and 03 (IAM,
Network) are largely *designed* early and *implemented* alongside the things
they protect and connect.

| Session | Layers | Deliverable |
|---|---|---|
| A | 0, 01 | WSL2 + Docker + tools verified; git repo, `.gitattributes`, Makefile; `requirements.md` with SLIs/SLOs/RTO/RPO |
| B | 06 | The app, its images, validated under docker-compose — no Kubernetes yet |
| C | 04, 09, 03 | `k3d/lab-01.yaml`, cluster up, storage, ingress reachable from a Windows browser |
| D | 08, 07, 10, 02 | Registry, CI, Helm chart, ArgoCD syncing, RBAC and ServiceAccounts |
| E | 11, 13 | sealed-secrets, cert-manager, NetworkPolicy, Kyverno; Prometheus, dashboard, alert rules |
| F | 12, 14, 15 | HPA and PDB, backup/restore, failure exercises, cost doc, DoD, verify script green |

Layer 05 (Configuration) has no session of its own — its deliverable is the
written "what k3d hid from me" list, produced during session C.

---

## 6. Open questions for sign-off

1. **Repository location** — move the working copy to WSL2 ext4, or accept
   the 9p performance penalty and keep it on the Windows side?
2. **GitHub remote** — needs to exist before Layer 10. Public or private?
   Private makes the ArgoCD repo credential a real sealed-secret exercise
   rather than a skipped one, which is arguably the better lab.
3. **Kyverno at `audit` or `enforce`** for project 01? Spec says `audit`;
   `enforce` is more instructive but blocks deployments while the chart is
   still being written.
4. **SLO numbers** — 99% availability / 300 ms p95 are placeholders chosen to
   make the alert thresholds derivable. Confirm or replace before Layer 13,
   since the thresholds inherit from them.
