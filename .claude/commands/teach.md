---
description: Walk back through recently changed files - why they exist, what they connect to
---

TEACH MODE.

Walk Denis through the files changed most recently (check git status/diff if
this is a git repo yet, otherwise ask which files/session to cover). This is
not a re-explanation of what a generic Terraform/Kubernetes/Ansible concept
is in the abstract — it's a trace through *this specific repo's* files and
how they actually connect.

For each file changed:

1. Why does this file exist — what would be missing without it?
2. Who or what reads it (a human running a command, Terraform, Ansible,
   Kubernetes, ArgoCD, CI)?
3. What inputs does it need, and where do those inputs come from?
4. What does it create or produce?
5. Which other files depend on its output? Which files does it depend on?
6. What would visibly break if this file were deleted?

Then trace the full execution path end to end, from the command Denis would
type to the final effect, as a simple chain — for example:

```
main.tf → terraform apply → cloud provider API → actual resource
outputs.tf → terraform output → Ansible inventory / next layer's input
```

Do this for every layer touched, not just the last one, if more than one
layer changed in the same session.

Ask one check-back question per file or small group of related files —
something like "what would happen if this value were wrong?" — and wait for
Denis's answer before moving to the next file. Don't just lecture straight
through; this mode only works if he's answering, not just reading.
