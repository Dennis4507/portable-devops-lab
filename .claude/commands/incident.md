---
description: Introduce one hidden, reversible failure; Denis diagnoses it blind
---

INCIDENT MODE.

Pick one realistic, safe, reversible failure that fits the currently-built
architecture (examples: wrong `targetPort`, a broken readiness probe, a
NetworkPolicy blocking a needed path, a bad env var, an expired/rotated
secret, a DNS misconfiguration, a resource limit set too low, a scaled-to-zero
dependency). Confirm it's reversible and won't touch anything outside this
lab before introducing it.

Hard rules for this mode:

1. **Do not reveal the root cause.** Give Denis only the symptom a real
   operator would see first (e.g. "users are getting 502s", "the pod is
   stuck in CrashLoopBackOff", "requests are timing out after 30s") — not
   the cause, not which file you changed.
2. **Restrict yourself to read-only diagnostic actions while Denis
   investigates** — `kubectl describe`/`get`/`logs`, `curl`, `dig`/
   `nslookup`, reading files. Do not run any command that would fix or
   further change the system while he's still diagnosing, even if you can
   see the fix clearly. The pull to just resolve it is strong — resist it;
   that's the entire point of this mode.
3. Answer Denis's diagnostic questions honestly and with real command output
   — don't fabricate results, don't steer him.
4. **Only help if he explicitly asks for a hint, is completely stuck, or is
   about to make the situation worse** (e.g. about to delete something that
   won't fix it). Even then, give the smallest nudge that unsticks him, not
   the answer.
5. Once he identifies the root cause (or asks to be told it), confirm
   whether he was right, then let him drive the fix — don't apply it for
   him unless he asks you to.
6. After resolution, write up the incident and append it to
   `docs/incidents.md`:

```
## Incident NNN — <one-line symptom>
### Symptom
### Initial hypotheses
### Evidence
### Root cause
### Fix
### Prevention
```

Number incidents sequentially across the whole lab, not per project.
