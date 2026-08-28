---
description: Full oral exam on a completed project, across the whole stack, with anchored scoring
---

PROJECT VIVA.

This runs once a project is considered complete — a full oral examination as
if Denis designed and now operates this system in production, in front of a
panel that will ask follow-ups.

Cover, across the session: architecture, Terraform, state, IAM, networking,
Linux, Docker, CI, the registry, Kubernetes, Helm, ArgoCD, secrets, TLS,
RBAC, NetworkPolicy, HPA, node scaling, storage, metrics, logs, traces,
alerts, backup/recovery, security, cost, and the trade-offs behind the
non-obvious decisions in this specific project.

Rules:

1. Ask **one question at a time**, ~30 across the session. Favor "what
   happens if...", "why did you...", "how would you...", "how do you know
   this is actually working...", "what would you check first..." over
   definition recall.
2. **Score each answer against specific, named criteria** stated before you
   give the number — e.g. "full credit here requires naming resource
   requests as the HPA scaling denominator and explaining why an
   under-set request causes noisy scaling" — not a bare gut-feel number.
   This is what makes scores comparable across different projects later.
3. Don't reveal the criteria in advance of the answer, only when scoring it.
4. At the end:
   - Give an overall level assessment (junior / mid / senior / staff-level
     reasoning) with the specific evidence for that call, not just the label.
   - Name the five weakest areas, specifically, not generically.
   - Append those five areas to `docs/learning-gaps.md`.
   - If anything broke or was discovered to be wrong during this viva about
     the actual implementation, note it — don't fix it live, that's a
     `/build` session.

This is meant to feel harder than `/interview` — it's the graduation check
for the whole project, not a single-topic practice round.
