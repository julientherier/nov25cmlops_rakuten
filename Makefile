#################################################################################
# GLOBALS
#################################################################################

PROJECT_NAME := nov25cmlops_rakuten
PYTHON_VERSION := 3.12
PYTHON_INTERPRETER := python

# Docker compose command (supports docker-compose v1 or docker compose v2)
COMPOSE_CMD := $(shell \
	if command -v docker-compose >/dev/null 2>&1; then \
		echo docker-compose; \
	else \
		echo docker compose; \
	fi \
)

# Services
SVC_NGINX   := nginx
SVC_GATEWAY := gateway
SVC_PREDICT := api-predict
SVC_TRAIN   := api-train
SVC_INGEST  := api-ingest

# Data injection
TRAIN_CSV_LOCAL ?= data/interim/rakuten_train.csv
TRAIN_CSV_DEST  ?= /app/data/interim/rakuten_train.csv

#################################################################################
# PYTHON (LOCAL)
#################################################################################

## Install Python dependencies (local)
.PHONY: requirements
requirements:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt

## Create local venv
.PHONY: create_environment
create_environment:
	uv venv --python $(PYTHON_VERSION)
	@echo "Activate with: source ./.venv/bin/activate"

## Lint using ruff
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format

## Run tests
.PHONY: test
test:
	$(PYTHON_INTERPRETER) -m pytest tests

## Clean python caches
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

#################################################################################
# DOCKER COMPOSE
#################################################################################

## Build all images
.PHONY: docker-build
docker-build:
	$(COMPOSE_CMD) build

## Start the full stack (nginx + gateway + services)
.PHONY: docker-up
docker-up:
	$(COMPOSE_CMD) up -d --build $(SVC_NGINX) $(SVC_GATEWAY) $(SVC_PREDICT) $(SVC_TRAIN) $(SVC_INGEST)

## Stop everything (keep volumes)
.PHONY: docker-down
docker-down:
	$(COMPOSE_CMD) down

## Stop everything + remove volumes (DANGER: deletes persisted data/models)
.PHONY: docker-down-v
docker-down-v:
	$(COMPOSE_CMD) down -v

## Show containers
.PHONY: docker-ps
docker-ps:
	$(COMPOSE_CMD) ps

## Tail logs (all services)
.PHONY: docker-logs
docker-logs:
	$(COMPOSE_CMD) logs -f

## Tail logs for a single service: make docker-logs-svc SVC=api-train
.PHONY: docker-logs-svc
docker-logs-svc:
	$(COMPOSE_CMD) logs -f $(SVC)

#################################################################################
# DATA INJECTION (into Docker volume)
#################################################################################

## Check that local rakuten_train.csv exists
.PHONY: csv-check
csv-check:
	@test -f "$(TRAIN_CSV_LOCAL)" || (echo "Missing file: $(TRAIN_CSV_LOCAL)" && exit 1)

## Copy local data/interim/rakuten_train.csv into the Docker volume via the train container
## This is the simplest, explicit injection method (compatible with later DVC).
.PHONY: docker-cp-traincsv
docker-cp-traincsv: csv-check
	$(COMPOSE_CMD) exec -T $(SVC_TRAIN) sh -lc "mkdir -p $(dir $(TRAIN_CSV_DEST))"
	$(COMPOSE_CMD) cp "$(TRAIN_CSV_LOCAL)" "$(SVC_TRAIN):$(TRAIN_CSV_DEST)"
	$(COMPOSE_CMD) exec -T $(SVC_TRAIN) sh -lc "ls -lah $(TRAIN_CSV_DEST)"

#################################################################################
# QUICK SMOKE TESTS
#################################################################################

## Check gateway health (through nginx). Uses -k for self-signed TLS.
.PHONY: smoke-health
smoke-health:
	curl -k -s https://localhost/health | cat

## Open Swagger in browser (macOS). If not macOS, just open https://localhost/docs manually.
.PHONY: swagger
swagger:
	open https://localhost/docs

#################################################################################
# HELP
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z0-9_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)