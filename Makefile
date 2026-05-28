PY := venv/bin/python
ALEMBIC := venv/bin/alembic
UVICORN := venv/bin/uvicorn

.PHONY: help install dev migrate upgrade downgrade current history fresh-db lint \
        docker-build docker-up docker-down docker-logs docker-upgrade docker-shell

help:
	@echo "Local (venv):"
	@echo "  make install              Instala dependências no venv"
	@echo "  make dev                  Sobe o servidor em modo dev (reload)"
	@echo "  make migrate m=\"msg\"      Gera nova migration a partir dos models"
	@echo "  make upgrade              Aplica migrations pendentes no banco"
	@echo "  make downgrade            Reverte a última migration"
	@echo "  make current              Mostra a revision aplicada no banco"
	@echo "  make history              Lista todas as migrations"
	@echo "  make fresh-db             Apaga histórico e regenera init (DESTRUTIVO — só dev)"
	@echo "  make lint                 Roda ruff check"
	@echo ""
	@echo "Docker (stack completa):"
	@echo "  make docker-build         Builda as imagens (backend + frontend)"
	@echo "  make docker-up            Sobe a stack em background"
	@echo "  make docker-down          Para a stack e remove containers"
	@echo "  make docker-logs          Mostra logs em tempo real"
	@echo "  make docker-upgrade       Roda migrations dentro do container do backend"
	@echo "  make docker-shell         Abre bash no container do backend"

install:
	$(PY) -m pip install -r requirements.txt

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	@if [ -z "$(m)" ]; then \
		echo "Uso: make migrate m=\"descricao curta\""; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(m)"
	@echo ""
	@echo "→ Revise o arquivo gerado em alembic/versions/ antes de aplicar."
	@echo "→ Depois rode: make upgrade"

upgrade:
	$(ALEMBIC) upgrade head

downgrade:
	$(ALEMBIC) downgrade -1

current:
	$(ALEMBIC) current

history:
	$(ALEMBIC) history

fresh-db:
	@echo "Isso vai apagar TODAS as migrations e dados. Ctrl+C para abortar."
	@sleep 3
	$(ALEMBIC) downgrade base || true
	rm -f alembic/versions/*.py
	touch alembic/versions/.gitkeep
	$(ALEMBIC) revision --autogenerate -m "init"
	$(ALEMBIC) upgrade head

lint:
	$(PY) -m ruff check app/

docker-build:
	docker compose build

docker-up:
	docker compose up -d
	@echo ""
	@echo "Stack no ar — veja portas em .env (APP_PORT, FRONTEND_PORT)"
	@echo "Logs: make docker-logs"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-upgrade:
	docker compose run --rm backend alembic upgrade head

docker-shell:
	docker compose exec backend /bin/bash
