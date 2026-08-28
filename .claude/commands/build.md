---
description: Implement one layer of one project, small steps, explained out loud
---

BUILD MODE.

Read `CLAUDE.md` at the repo root before doing anything else if it hasn't
been read this session. Identify which project and which layer we're on from
what Denis just said, or ask if it's ambiguous — don't guess silently.

Rules for this session:

1. **Inspect before implementing.** Look at what already exists in the
   relevant `terraform/projects/<name>/`, `ansible/`, `helm/`, or
   `application/` folders before writing anything new.
2. **State the plan before building.** In one short paragraph: what needs to
   exist for this layer, which files will be touched, and why this is the
   smallest correct version of it. Don't implement later layers while here —
   if something clearly belongs to a later layer, name it and leave it.
3. **Build in steps of roughly three**, matching the pacing that worked on
   `cloud-native-ha-platform`: build a step, explain it in full sentences in
   chat (not only as code comments — what it does, what it connects to, what
   to verify), then move to the next step. After three steps, stop and wait
   for Denis to confirm before continuing, unless he explicitly says to keep
   going.
4. **Every resource gets its reasoning stated**, unprompted: why it exists,
   what depends on it, what it depends on, how to verify it worked, how it
   can fail, roughly what it costs.
5. **Never run `terraform destroy`, delete a cloud resource, or any other
   hard-to-reverse command without explaining the command and its expected
   impact first and getting an explicit go-ahead** — this applies even
   though this is BUILD MODE and even under an autonomous permission
   setting.
6. At the end of the session (or the layer, whichever comes first), state
   what to verify before the next session, and whether anything from this
   layer should get logged to `docs/incidents.md` (if something broke and
   got fixed along the way) or `docs/learning-gaps.md` (if something took
   longer than it should have because a concept wasn't solid).

Do not switch into `/teach`, `/interview`, `/incident`, `/recall` or `/viva`
behavior mid-session unless Denis explicitly asks for one of those.
