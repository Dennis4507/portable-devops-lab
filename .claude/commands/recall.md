---
description: Reconstruct the architecture from memory before checking it against reality
---

RECALL MODE.

**Do not inspect the repository yet.** This mode only works if Denis
reconstructs the system from memory first, before either of you looks at the
actual files.

Ask Denis to walk through the current project's architecture from memory, in
this order, one section at a time — wait for his answer to each before
moving to the next:

1. **Request flow**: from the user's browser through DNS, load balancer/
   ingress, service, pod, to the application and its database.
2. **Deployment flow**: from `git push` through CI, the registry, GitOps
   (ArgoCD), Helm, to the running cluster.
3. **Infrastructure flow**: from Terraform through the provider, network,
   compute, IAM, to the cluster or host existing.
4. **Observability**: what emits metrics/logs/traces, where they go, what a
   dashboard or alert would actually show if something in this system broke.
5. **Security**: identity, secrets, RBAC, NetworkPolicy — what's actually
   enforced in this specific project, not the general concept.
6. **Cost**: the largest cost driver in this specific project's architecture,
   and what the cheaper alternative would have cost in trade-offs.

For each section, note silently (don't interrupt) where his explanation is
vague, wrong, or missing something specific to this project's actual
implementation.

**Only after he's finished all six sections**, open the repo and compare his
explanation against what's actually there. Go through the mismatches one by
one: where he was right, where he was close, where he was off. Append any
real gap to `docs/learning-gaps.md`, worded as the specific thing to revisit
next time, not a vague "review Kubernetes."
