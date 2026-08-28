# CLAUDE.md — Portable DevOps Engineering Lab

> **Read this first.** This is the permanent operating contract for this
> repository. It governs every project built inside it, not just the current
> one. Revise it deliberately, not by accident — if a rule here stops making
> sense once real building starts, say so explicitly and change the rule,
> don't just quietly ignore it.

---

## Purpose

This repository is two things at once, in this order of priority:

1. **A deliberate learning environment.** The goal is for Denis to internalize
   the one system every cloud-native application actually runs on — IaC,
   networking, IAM, Linux, containers, Kubernetes, GitOps, observability,
   security, reliability, cost — deeply enough to reason about it without
   looking anything up, across managed and self-managed infrastructure, across
   providers.
2. **A reusable scaffold.** The same reference application gets deployed
   through the same golden path on ~10+ different infrastructure targets, so
   the infrastructure — not the application — is what's actually being
   studied each time.

**Finishing a deployment is not the goal.** Understanding it well enough to
defend every decision live, and to diagnose a failure in it from a cold
start, is the goal. See "The six modes" below — most of the value here comes
from *operating* what's built, not from building it.

## Who Denis is and how he learns

Denis Riungu is a DevOps/Cloud Engineer with production experience across the
eBay listing automation platform (FastAPI, Celery, K3s on Hetzner,
PostgreSQL), a Jenkins/ArgoCD/K3s-on-AWS platform, an Azure→AWS migration
(Terraform, DMS CDC, Route 53), and the `cloud-native-ha-platform` CGI
challenge build (Azure VMSS + K3s multi-region HA — see
`C:\Users\OnlyM\Denis Cloud Projects\cloud-native-ha-platform\CLAUDE.md` for
that project's own contract; it's a good reference for how a build session
under this kind of contract actually reads once it's running).

He learns by building and by being questioned on what he built — not by
reading finished code. Every meaningful change needs its reasoning stated out
loud, not just implemented: what the file is, why it exists, who reads it,
what it depends on, what depends on it, how to verify it, how it fails, what
it costs. Don't repeat definitions of things he already knows cold; do spell
out any acronym or non-obvious tool in full plain English the first time it
appears in a given session.

This work also directly feeds `C:\Users\OnlyM\denis-knowledge-base\`, the
interview-prep KB and its live interview assistant — a well-documented
project here (a "Whys" doc explaining every non-obvious decision, the way the
CGI project's own post-mortem does) is worth harvesting into
`interview/projects/` in that repo once a project is solid. Flag that
opportunity when a project reaches that point; don't do it automatically.

## The core rule

**Claude may accelerate implementation. It must never hide the reasoning.**

For every meaningful change, be ready to answer, unprompted:
1. What are we changing?
2. Why does this file/resource exist?
3. Who reads or executes it?
4. What does it create or change?
5. What does it depend on?
6. What depends on it?
7. How do we verify it?
8. How can it fail?
9. How would we troubleshoot it?
10. What does it cost?

---

## The locked design (do not relitigate without saying so explicitly)

These were decided deliberately after weighing alternatives. Don't quietly
drift from them — if one stops working in practice, name it and change it on
purpose.

**One reference app, growing only between tiers, not between every project.**
Changing both the infrastructure *and* the application in the same project
makes it impossible to tell what was actually learned from that rep. So the
app is held fixed within a tier and only grows when the tier changes:

| Tier | Infra | App adds |
|---|---|---|
| 1 — Own everything | Local (WSL2/K3d), VM+K3s (2+ clouds), bare metal/Proxmox | API + DB only |
| 2 — Elastic self-managed | Azure VMSS+K3s, AWS ASG+K3s | + Redis, + worker |
| 3 — Managed Kubernetes | AKS, EKS, GKE | + object storage, + tracing |
| 4 — Sovereign + graduation | STACKIT (VM+K3s, then SKE) | graduation: same app, distributed, real failover |

**Ordering is VM-and-bare-metal-first, managed Kubernetes last.** Own what a
managed control plane hides before trusting the managed version of it. This
is the opposite of how most tutorials sequence it, and that's deliberate.

**Module contract, not shared code.** Terraform modules are not literally
shared across cloud providers — that always rots into unreadable
`count`/`dynamic` hacks. Instead: one module *per cloud, per concern*
(`modules/network/azure`, `modules/network/aws`, `modules/network/gcp`, and
likewise for `compute`, `iam`, `storage`, `dns`), each exposing an **identical
variable and output contract** regardless of provider. Portability lives in
the interface, not in shared implementation.

**Terraform's job ends at "a reachable host or a managed control plane
exists."** Ansible's job starts there — OS config and K3s server/agent
bootstrap, for every self-managed tier, regardless of which cloud the host is
on. There is no Terraform "kubernetes" module for self-managed tiers; that
concern doesn't exist until Ansible creates it. Managed tiers (AKS/EKS/GKE/
SKE) skip the Ansible K3s roles entirely and go straight to Helm/ArgoCD
bootstrap on the managed cluster.

**Definition of Done is enforced two ways at once**, not one or the other:
a doc checklist **per project**, at `docs/projects/<NN-name>/definition-of-done.md`
(a single lab-wide file was tried in the original draft of this file and
doesn't survive past the second or third project — every project's DoD needs
its own file since what's checkable differs by tier) AND an automated
`make verify` script per project at `scripts/verify-<NN-name>.sh` (or
`terraform/projects/<NN-name>/verify.sh` — pick one convention on Project 01
and keep it, don't let it drift per project) that checks the same things
mechanically. The doc is for understanding; the script is for not lying to
yourself about whether it actually passed.

---

## The 15-layer lifecycle

Every project is checked against these 15 layers, in this order, every time
— this is the canonical list, not a per-project invention. If a layer is
trivial or genuinely doesn't apply at a given tier (there's no real IAM
concern on a local K3d cluster), say that explicitly in that project's spec
and DoD rather than omitting the layer silently — the point is to notice
"this doesn't apply here, and here's why," not to only list layers that do.

| # | Layer | Standard question | Core tooling / concepts |
|---|---|---|---|
| 01 | Requirements | What does this workload need? | SLI/SLO, RTO/RPO, traffic, state |
| 02 | IAM | Who can do what? | RBAC, service identities, least privilege |
| 03 | Network | How does traffic flow? | VPC/VNet, subnets, DNS, firewall, NAT |
| 04 | IaC | Can I reproduce everything? | Terraform, remote state, modules |
| 05 | Configuration | How are machines prepared? | Ansible, cloud-init, idempotency |
| 06 | Build | How is software packaged? | Docker, multi-stage builds |
| 07 | CI | How do changes become artifacts? | GitHub Actions, tests, Trivy |
| 08 | Registry | Where do immutable images live? | GHCR/ECR/ACR/GAR |
| 09 | Platform | Where does the workload execute? | K3s/AKS/EKS/GKE/SKE/VMs |
| 10 | Deployment | How does production match Git? | Helm, Kustomize, ArgoCD |
| 11 | Security | How is runtime protected? | Secrets, NetworkPolicy, RBAC, Kyverno |
| 12 | Scaling/HA | What happens under pressure/failure? | HPA, node autoscaling, PDB |
| 13 | Observability | How do I know what's happening? | Prometheus, Grafana, Loki, OTel |
| 14 | Reliability | Can I break and recover it? | backup, restore, chaos, rollback |
| 15 | Cost | Is this architecture economically sensible? | OpenCost, right-sizing, provider billing |

This is also the layer list `/build` refers to when it says "identify which
layer we're on" — don't derive a competing one per project.

---

## The reference application

Lean by design — it exists to exercise DevOps concepts, not to become a
serious piece of software. Don't over-engineer its business logic; do give
it a standard operational contract every project can build on:

```
/health        liveness — is the process up
/ready         readiness — checks real dependencies (DB, cache) before 200
/metrics       Prometheus-format metrics
/info          {service, version, hostname/pod-name, region} — makes
               round-robin, canary and failover demos visible
/work          does controllable CPU work — the thing k6 drives to trigger HPA
/error-test    produces a controlled error — the thing that exercises
               error-rate dashboards, alerts and log correlation
```

Tier 1 shape: `frontend (nginx or plain HTML) → API (FastAPI) → PostgreSQL`.
Tier 2 adds Redis + a Celery/RQ worker. Tier 3 adds S3-compatible object
storage + OpenTelemetry tracing. Business purpose: something boring and
concrete — an Order/Inventory app — specifically so the infrastructure stays
the interesting part.

---

## Repo structure

```
portable-devops-lab/
├── CLAUDE.md                    ← this file
├── application/                 ← the one reference app, grows per tier
│   ├── frontend/
│   ├── api/
│   └── worker/                  ← added at Tier 2
├── terraform/
│   ├── modules/                 ← per-cloud, per-concern, shared contract
│   │   ├── network/{azure,aws,gcp,stackit}/
│   │   ├── compute/{azure,aws,gcp,stackit}/
│   │   ├── iam/{azure,aws,gcp,stackit}/
│   │   ├── kubernetes/{azure,aws,gcp,stackit}/   ← managed tiers only
│   │   ├── storage/{azure,aws,gcp,stackit}/
│   │   └── dns/{azure,aws,gcp,stackit}/
│   └── projects/                ← thin root modules, one per project
│       ├── 01-local/            (no terraform — k3d/kind)
│       ├── 02-hetzner-vm/
│       ├── 03-<second-cloud>-vm/
│       ├── 04-baremetal-proxmox/
│       ├── 05-azure-vmss/
│       ├── 06-aws-asg/
│       ├── 07-azure-aks/
│       ├── 08-aws-eks/
│       ├── 09-gcp-gke/
│       └── 10-stackit/
├── ansible/
│   └── roles/
│       ├── common/               ← OS prep, every cloud, unmodified
│       ├── k3s-server/           ← self-managed tiers only
│       ├── k3s-agent/            ← self-managed tiers only
│       └── observability/
├── helm/
│   └── reference-app/
├── gitops/
│   └── argocd/
├── platform/                     ← cert-manager, external-secrets, kyverno,
│                                    prometheus, grafana, loki, otel, opencost
├── tests/
│   ├── smoke/  load/  security/  resilience/
├── docs/
│   ├── learning-gaps.md          ← updated only from demonstrated weaknesses
│   ├── incidents.md              ← one running log across the whole lab
│   ├── concept-map.md
│   └── projects/<NN-name>/       ← per project: definition-of-done.md,
│                                    cost.md, spec.md, "Whys" doc
├── scripts/
│   └── verify-<NN-name>.sh       ← per-project automated half of DoD
└── Makefile                      ← up / down / verify / cost
```

---

## Baselines every project must meet

**Security:** least privilege, nothing secret committed to Git, workload
identity where the provider has it, external secret management, Kubernetes
RBAC, NetworkPolicy, non-root containers, resource requests/limits, image
scanning (Trivy), IaC scanning, TLS, and at least one deliberate check that
tries to violate the assumption ("can pod A reach database B when it
shouldn't be able to?").

**Observability curriculum — built up progressively, not all at once:**
the app's `/metrics` endpoint exists from Project 01 onward (it's part of
the frozen v0 contract), but which platform tools consume it grows tier by
tier, deliberately decoupled from the app-growth table above — deploying
Prometheus doesn't require touching the app, so this can progress on its own
schedule:

- **Tier 1 (P01–04):** metrics only. Deploy Prometheus + Grafana, learn
  PromQL against the app's existing `/metrics`. Add Loki from P02 onward
  (logs need no app change — container stdout is already there) and start
  correlating a metric spike to the specific pod's logs.
- **Tier 2 (P05–06):** add Alertmanager and think in SLI/SLO/error-budget
  terms — the worker/queue this tier adds is what makes alerting on
  backpressure actually meaningful rather than academic.
- **Tier 3 (P07–09):** add OpenTelemetry + Tempo. This is the one
  observability addition that *does* require an app change, which is why
  it's gated here — it lines up with "+ tracing" in the app-growth table
  above, not a coincidence. Practice full correlation: alert → metric →
  trace → log → root cause.
- **Tier 4 (P10 + graduation):** the same full-correlation loop, now across
  a distributed/multi-cloud failure instead of a single cluster.

Don't just install Prometheus/Grafana/Loki/OTel; produce actual queries,
dashboards and alerts tied to the reference app's endpoints.

**Reliability:** every project ships with at least one deliberate, reversible
failure exercise (pod kill, DNS break, bad image, secret removal,
NetworkPolicy block, CPU/memory saturation, node failure). Every incident —
real or deliberate — gets written up as symptom → scope → evidence →
diagnosis → mitigation → root cause → prevention, appended to
`docs/incidents.md`.

**Cost:** every project's `docs/projects/<name>/cost.md` states architecture
cost per hour, actual lab runtime, actual cost, the largest cost driver, and
a lab-design vs production-design comparison. Budget discipline: local-first
for most reps (`€0`), one small persistent cloud playground, everything else
ephemeral (`terraform apply` → practice → `terraform destroy`, same session).
Target ceiling: **€20/month** in normal operation; an occasional heavier
"production simulation day" is a deliberate exception, not the default.

---

## The six modes

Default interaction when nothing else is specified is plain build-and-explain
(see "Default build behavior" below). For the specific, repeated training
patterns, use the slash commands in `.claude/commands/` — each is the source
of truth for its own exact behavior, kept there rather than duplicated here:

| Command | Use it for |
|---|---|
| `/build` | Implementing one layer, one project, at a time |
| `/teach` | Walking back through what was just built and why |
| `/interview` | Rapid-fire Q&A on the currently-implemented system |
| `/incident` | A hidden, deliberate, reversible failure you diagnose blind |
| `/recall` | Reconstructing an architecture from memory before checking it |
| `/viva` | Full oral exam at the end of a project, across the whole stack |

**Permission-mode discipline:** `/teach`, `/interview`, `/incident` and
`/viva` work best under an ask-before-tool-use permission mode — an
autonomous/auto-approve mode biases toward solving things immediately, which
defeats the point of a knowledge check or a blind diagnosis. Reserve
autonomous mode for `/build` reps and pure re-run/operate loops where speed
matters more than reflection.

## Default build behavior (when no mode is specified)

Borrowed from what already worked on the CGI project: work in small,
explicit steps, not a single large diff.

1. State what's about to be built and why, in plain sentences, before
   writing anything.
2. Build the smallest correct version of it.
3. Explain what was built, what it connects to, and how to verify it —
   in chat, not only as code comments. Comments carry the *why* for later
   reference; the chat explanation is what actually needs to be repeated
   back later.
4. Stop after a small, coherent unit of work (roughly 3 steps, matching the
   pacing that worked on `cloud-native-ha-platform`) and wait for
   confirmation before continuing, unless told explicitly to keep going.

**Never run `terraform destroy`, delete a cloud resource, or force-push
automatically.** Explain the command and its expected impact first, always —
this holds even during a `/build` session and even in autonomous permission
mode.

---

## Current status

Phase 0 — planning. This file, plus the six mode commands, is the first
artifact. Nothing has been provisioned yet. Next: freeze the reference-app
v0 spec and the Tier-1/Project-01 spec (local WSL2/K3d), then start `/build`.
