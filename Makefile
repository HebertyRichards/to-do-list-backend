# Requer GNU Make (Linux/macOS ja tem; Windows: "choco install make" ou "scoop install make" —
# o Git Bash sozinho NAO inclui o make). Se "make" falhar, veja a secao
# "Se make falhar (Windows)" no README, que inclui os comandos equivalentes sem make.
#
# Detecta o SO: no Windows o venv usa Scripts/ e o python do sistema chama "python".
ifeq ($(OS),Windows_NT)
    VENV_PY := venv/Scripts/python.exe
    SYS_PY  := python
else
    VENV_PY := venv/bin/python
    SYS_PY  := python3
endif

# Tudo roda via "python -m" para nao depender de caminhos de binarios por SO.
PY      := $(VENV_PY)
ALEMBIC := $(VENV_PY) -m alembic
UVICORN := $(VENV_PY) -m uvicorn

.PHONY: help venv install dev migrate upgrade downgrade current history fresh-db lint \
        docker-build docker-up docker-down docker-logs docker-upgrade docker-shell

help:
	@echo "Local (venv):"
	@echo "  make venv                 Cria o venv (se ainda nao existir)"
	@echo "  make install              Cria o venv se preciso e instala dependencias"
	@echo "  make dev                  Sobe o servidor em modo dev (reload)"
	@echo "  make migrate m=\"msg\"      Gera nova migration a partir dos models"
	@echo "  make upgrade              Aplica migrations pendentes no banco"
	@echo "  make downgrade            Reverte a ultima migration"
	@echo "  make current              Mostra a revision aplicada no banco"
	@echo "  make history              Lista todas as migrations"
	@echo "  make fresh-db             Apaga historico e regenera init (DESTRUTIVO - so dev)"
	@echo "  make lint                 Roda ruff check"
	@echo ""
	@echo "Docker (stack completa):"
	@echo "  make docker-build         Builda as imagens (backend + frontend)"
	@echo "  make docker-up            Sobe a stack em background"
	@echo "  make docker-down          Para a stack e remove containers"
	@echo "  make docker-logs          Mostra logs em tempo real"
	@echo "  make docker-upgrade       Roda migrations dentro do container do backend"
	@echo "  make docker-shell         Abre bash no container do backend"

# Cria o venv apenas quando o interpretador ainda nao existe (alvo = arquivo).
$(VENV_PY):
	$(SYS_PY) -m venv venv
	@echo "venv criado em ./venv"

venv: $(VENV_PY)

install: $(VENV_PY)
	$(PY) -m pip install -r requirements.txt

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	$(if $(m),,$(error Uso: make migrate m="descricao curta"))
	$(ALEMBIC) revision --autogenerate -m "$(m)"
	@echo ""
	@echo "-> Revise o arquivo gerado em alembic/versions/ antes de aplicar."
	@echo "-> Depois rode: make upgrade"

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
	@$(PY) -c "import time; time.sleep(3)"
	-$(ALEMBIC) downgrade base
	$(PY) -c "import glob, os, pathlib; [os.remove(f) for f in glob.glob('alembic/versions/*.py')]; pathlib.Path('alembic/versions/.gitkeep').touch()"
	$(ALEMBIC) revision --autogenerate -m "init"
	$(ALEMBIC) upgrade head

lint:
	$(PY) -m ruff check app/

docker-build:
	docker compose build

docker-up:
	docker compose up -d
	@echo ""
	@echo "Stack no ar - veja portas em .env (APP_PORT, FRONTEND_PORT)"
	@echo "Logs: make docker-logs"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-upgrade:
	docker compose run --rm backend alembic upgrade head

docker-shell:
	docker compose exec backend /bin/bash
