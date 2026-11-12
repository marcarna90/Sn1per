# Convenience targets. Backend/frontend have their own Makefile / npm scripts.
.PHONY: up down logs ps create-org backup check-backend check-frontend check

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
