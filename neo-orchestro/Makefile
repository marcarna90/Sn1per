# Convenience targets. Backend/frontend have their own Makefile / npm scripts.
.PHONY: up down logs ps create-org backup check-backend check-frontend check e2e

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# Interactive: prompts for the administrator password (never put it on the command line).
create-org:
	docker compose run --rm -it api python -m neo_orchestro.cli create-org \
	  --name "$(NAME)" --slug "$(SLUG)" --admin-email "$(EMAIL)"

backup:
	./scripts/backup.sh

check-backend:
	$(MAKE) -C backend check

check-frontend:
	cd frontend && npm run check

check: check-backend check-frontend

# Real-process end-to-end smoke test (see e2e/README.md). Needs NEO_E2E_DATABASE_URL / NEO_E2E_REDIS_URL.
e2e:
	./e2e/run.sh
