# =============================================================================
# Makefile — the one stable command surface across all 10 projects in this lab.
#
# `make verify` must mean the same thing here as it does at project 09, even
# though what happens underneath is entirely different (a k3d cluster here,
# real cloud infrastructure there). WHO READS THIS: you, by hand, from either
# a WSL2 terminal or Windows PowerShell with `wsl.exe` on PATH.
#
# STATUS: Project 01, Session A. `verify` is fully wired. `up`/`down`/`cost`
# are honest stubs — they say what Session C/F will wire them to rather than
# silently doing nothing.
# =============================================================================

CLUSTER_NAME := lab-01

.PHONY: help up down verify cost logs shell

help:
	@echo "portable-devops-lab / project 01-local"
	@echo ""
	@echo "  make up               create the local k3d cluster"
	@echo "  make down             tear down the local k3d cluster"
	@echo "  make verify           run the mechanical Definition of Done checks"
	@echo "  make verify STRICT=1  same, but zero skips required (the FINAL-1 gate)"
	@echo "  make cost             print this project's cost summary"
	@echo "  make logs             tail the reference-app pods' logs"
	@echo "  make shell            open a debug shell inside the cluster"

up:
	@echo "Not yet implemented — Session C adds k3d/lab-01.yaml and wires this to:"
	@echo "  k3d cluster create --config k3d/lab-01.yaml"
	@exit 1

down:
	@echo "Not yet implemented — Session C wires this to:"
	@echo "  k3d cluster delete $(CLUSTER_NAME)"
	@exit 1

verify:
	@STRICT=$(STRICT) bash scripts/verify-01-local.sh

cost:
	@echo "Not yet implemented — Session F adds docs/projects/01-local/cost.md"
	@echo "and this target will cat it here."
	@exit 1

logs:
	@echo "Not yet implemented — Session C+ wires this to:"
	@echo "  kubectl --context k3d-$(CLUSTER_NAME) -n app logs -f -l app=reference-api"
	@exit 1

shell:
	@echo "Not yet implemented — Session C+ wires this to:"
	@echo "  kubectl --context k3d-$(CLUSTER_NAME) -n app exec -it deploy/reference-api -- sh"
	@exit 1
