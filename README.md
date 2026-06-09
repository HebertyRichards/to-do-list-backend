# To-Do List — Backend

API REST + WebSocket construída com **FastAPI**, **SQLAlchemy 2 async** e **PostgreSQL** (Neon). Suporta modo individual, modo grupo e hábitos diários (recorrentes), autenticação JWT em cookies httpOnly, verificação de email, rate limiting por conta e notificações em tempo real.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 (asyncio + asyncpg) |
| Banco | PostgreSQL (Neon) |
| Migrações | Alembic (sync via psycopg2) |
| Validação | Pydantic 2 |
| Autenticação | JWT (`python-jose`) em cookies httpOnly |
| Email | `fastapi-mail` (SMTP — Gmail por padrão) |
| Cache/rate limit | Redis (com fallback `NullRedis` se indisponível) |
| WebSocket | FastAPI nativo |
| Servidor | Uvicorn |

---

## Arquitetura

```
routes/         → recebem request, delegam para service (sem lógica)
services/       → regras de negócio (classes async)
repositories/   → queries SQLAlchemy (sem lógica de negócio)
models/         → ORM (Mapped[T] + mapped_column — SQLAlchemy 2)
schemas/        → Pydantic v2 (input/output)
utils/          → cookies, dependencies, security, rate_limit
ws/             → NotificationManager + rotas WebSocket
```

---

## Estrutura de pastas

```
to-do-list-backend/
├── alembic/                    # Migrations
│   └── versions/
├── app/
│   ├── config/
│   │   ├── database.py         # Engine async + get_db
│   │   ├── email.py            # SMTP config (fastapi-mail)
│   │   ├── redis_client.py     # NullRedis fallback + init_redis()
│   │   └── settings.py         # Pydantic Settings (@lru_cache)
│   ├── errors/                 # Códigos + handlers
│   ├── models/                 # ORM SQLAlchemy
│   ├── repositories/           # Queries SQLAlchemy
│   ├── routes/                 # APIRouter (sem lógica)
│   ├── schemas/                # Pydantic input/output
│   ├── services/               # Regras de negócio
│   ├── utils/
│   │   ├── cookies.py
│   │   ├── dependencies.py     # get_current_user, get_current_user_ws
│   │   ├── rate_limit.py       # Rate limiting por chave/email
│   │   └── security.py         # JWT, hash de senha, chave de grupo
│   └── ws/
│       ├── manager.py          # NotificationManager singleton
│       └── routes.py           # /ws/notifications
├── tests/
├── .dockerignore               # Bloqueia .env, venv, .git, etc. fora da imagem
├── Dockerfile
├── docker-compose.yml
├── Makefile                    # Atalhos: make dev / migrate / upgrade / etc.
├── requirements.txt
└── alembic.ini
```

---

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do backend. Todos os campos são obrigatórios.

### Variáveis usadas

| Variável | Quem lê | Descrição |
|---|---|---|
| `APP_ENV` | FastAPI | `development` ou `production` |
| `LOG_LEVEL` | FastAPI | `INFO`, `DEBUG`, etc. |
| `APP_PORT` | docker-compose local + Dockerfile | Porta do uvicorn em ambiente local (default 8000) |
| `FRONTEND_PORT` | docker-compose local | Porta do Next.js em ambiente local (default 3000) |
| `PORT` | Runtime do uvicorn (via Dockerfile) | Injetado automaticamente pelo ambiente de execução em produção. **Não definir manualmente.** O Dockerfile usa `${PORT:-${APP_PORT:-8000}}` — quando `$PORT` está setado tem prioridade, senão cai em `$APP_PORT`, senão `8000` |
| `DATABASE_URL` | FastAPI (asyncpg) | URL async pro Neon. **Precisa começar com `postgresql+asyncpg://`** |
| `DATABASE_URL_SYNC` | Alembic (psycopg2) | URL sync pro Neon. **Precisa começar com `postgresql+psycopg2://`** |
| `REDIS_URL` | FastAPI | URL do Redis. Local: `redis://localhost:6379/0`. Docker: `redis://redis:6379/0` (nome do serviço) |
| `JWT_SECRET` | FastAPI | Saída de `openssl rand -hex 32` |
| `JWT_ALGORITHM` | FastAPI | `HS256` |
| `ACCESS_TOKEN_MINUTES` | FastAPI | Duração do access token |
| `REFRESH_TOKEN_DAYS` | FastAPI | Duração absoluta da sessão |
| `FRONTEND_ORIGIN` | FastAPI (CORS) | Origem permitida (sem `/` final) |
| `TRUST_FORWARDED_FOR` | FastAPI (rate limit) | `true` só atrás de proxy reverso confiável que sobrescreve o `X-Forwarded-For`. Se o backend ficar exposto direto, mantenha `false` (senão o IP é spoofável) |
| `TRUSTED_PROXY_COUNT` | FastAPI (rate limit) | Nº de proxies confiáveis à frente (padrão `1`). O IP real é o N-ésimo da direita no `X-Forwarded-For`; entradas à esquerda são forjáveis pelo cliente |
| `COOKIE_DOMAIN` | FastAPI | Vazio em dev, domínio em prod |
| `COOKIE_SECURE` | FastAPI | `false` em dev (http), `true` em prod (https) |
| `COOKIE_SAMESITE` | FastAPI | `lax` (padrão) |
| `EMAIL_USER` | FastAPI (SMTP) | Conta Gmail emissora |
| `EMAIL_PASS` | FastAPI (SMTP) | App password do Gmail (16 chars) |

### O que muda entre cenários

| Variável | Dev local (venv) | Docker compose | Produção |
|---|---|---|---|
| `APP_ENV` | `development` | `development` | `production` |
| `REDIS_URL` | `redis://localhost:6379/0` (Redis local) ou vazio | `redis://redis:6379/0` (nome do service) | `redis://redis:6379/0` |
| `FRONTEND_ORIGIN` | `http://localhost:${FRONTEND_PORT}` | `http://localhost:${FRONTEND_PORT}` | `https://seu-dominio.com` |
| `COOKIE_SECURE` | `false` | `false` | `true` |
| `COOKIE_DOMAIN` | vazio | vazio | `seu-dominio.com` |

`DATABASE_URL`, `DATABASE_URL_SYNC`, `JWT_SECRET`, `EMAIL_*` continuam iguais nos três cenários (banco é Neon remoto em todos).

### Duas `DATABASE_URL`

O Neon fornece dois endpoints:

| Variável | Host | Driver | Uso |
|---|---|---|---|
| `DATABASE_URL` | `ep-xxx-pooler…` | `+asyncpg` | Runtime (FastAPI async) |
| `DATABASE_URL_SYNC` | `ep-xxx…` (sem `-pooler`) | `+psycopg2` | Alembic migrations |

`psycopg2-binary` aparece em `requirements.txt` exclusivamente para o Alembic — o runtime do FastAPI usa `asyncpg`.

### Como gerar o `JWT_SECRET`

```bash
openssl rand -hex 32
```

Nunca reutilize o segredo entre ambientes e nunca commite o `.env`. O `.dockerignore` já bloqueia `.env` de entrar na imagem.

---

## Makefile (atalhos)

O `Makefile` na raiz expõe os comandos do dia-a-dia. Rode `make` ou `make help` para listar.

### Local (venv)

| Comando | O que faz |
|---|---|
| `make install` | `pip install -r requirements.txt` no venv |
| `make dev` | Sobe o uvicorn com `--reload` em `0.0.0.0:8000` |
| `make migrate m="descricao"` | Gera migration nova a partir dos models. **Revise o arquivo gerado antes de aplicar** |
| `make upgrade` | Aplica migrations pendentes (`alembic upgrade head`) |
| `make downgrade` | Reverte a última migration |
| `make current` | Mostra a revision aplicada no banco |
| `make history` | Lista todas as migrations |
| `make fresh-db` | Apaga histórico e regenera init. **DESTRUTIVO — só dev** |
| `make lint` | Roda `ruff check app/` |

### Docker (stack completa: backend + redis + frontend)

| Comando | O que faz |
|---|---|
| `make docker-build` | Builda as imagens |
| `make docker-up` | Sobe a stack em background |
| `make docker-down` | Para a stack e remove containers |
| `make docker-logs` | Logs em tempo real |
| `make docker-upgrade` | Roda migrations no container do backend |
| `make docker-shell` | Abre bash no container do backend |

**Quando usar cada um:**
- **Local (venv)**: dia-a-dia, iteração rápida, hot reload instantâneo. Banco é o Neon remoto.
- **Docker**: testar com frontend, ambiente igual ao de produção, Redis local sem precisar instalar.

**Notas sobre `docker compose`:**
- As variáveis `${APP_PORT}` e `${FRONTEND_PORT}` no `docker-compose.yml` são interpoladas a partir do `.env` na raiz do projeto. Defina ambas lá.
- O `env_file: .env` carrega o restante das variáveis dentro do container do backend.
- O frontend lê seu próprio `.env` em `../to-do-list/.env`.

### Quando gerar uma migration

Sempre que mexer em `app/models/*.py` de forma que altere a estrutura do banco:

- Adicionar/remover campo, tabela, índice
- Mudar tipo, tamanho, nullable, default
- Adicionar/mudar constraint (UniqueConstraint, CheckConstraint, FK)
- Renomear coluna/tabela/schema

Mudanças que **não** geram migration: regras de negócio em services, novos endpoints, validações Pydantic, `relationship()` sem FK nova, `@property` no model.

### Workflow típico

```bash
vim app/models/user.py                # mexeu no model
make migrate m="add foo to user"      # gera migration
# → revise o arquivo em alembic/versions/
make upgrade                           # aplica
git add app/models/user.py alembic/versions/<arquivo>.py
git commit -m "feat: add foo to user"
```

> **Cuidado com renomear coluna**: o autogenerate vê como `drop + add` e perde dados. Edite manualmente o arquivo gerado nesses casos.

---

## Desenvolvimento local

### Pré-requisitos

- Python 3.11+
- PostgreSQL (Neon ou local)
- Redis acessível na `REDIS_URL` (opcional — app continua sem ele, mas sem rate limit, denylist de refresh, nem cache de códigos)

### 1. Instalar dependências

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
make install               # ou: pip install -r requirements.txt
```

Para builds totalmente reproduzíveis com deps transitivas pinadas, gere um lock:

```bash
pip freeze > requirements-lock.txt
# em produção:
pip install -r requirements-lock.txt
```

### 2. Criar `.env`

Use a seção **Variáveis de ambiente — Desenvolvimento local** acima.

### 3. Rodar migrações

```bash
make upgrade   # aplica migrations existentes (cria schemas accounts/app se necessário)
```

Para criar nova migration após alterar models, ver seção **Makefile** acima.

### 4. Iniciar servidor

```bash
make dev   # ou: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa em `http://localhost:8000/docs`.

---

## Produção com Docker

A stack completa (backend + frontend) sobe a partir do `docker-compose.yml`. Os dois projetos precisam estar na mesma pasta pai:

```
projetos/
├── to-do-list/          # frontend
└── to-do-list-backend/  # backend ← docker-compose.yml aqui
```

### 1. Configurar `.env` de produção

```env
APP_ENV=production
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=seu-dominio.com
FRONTEND_ORIGIN=https://seu-dominio.com
```

`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `EMAIL_*` devem vir do gestor de segredos da infraestrutura — nunca commitar.

### 2. Rodar migrações

```bash
make docker-upgrade    # ou: docker compose run --rm backend alembic upgrade head
```

### 3. Subir a stack

```bash
make docker-build && make docker-up
make docker-logs       # acompanhar logs
```

### 4. Atualizar deploy

```bash
git pull
make docker-build && make docker-up
```

### 5. Reverse proxy

Em produção, coloque um Nginx / Caddy / Traefik na frente para terminar TLS, rotear `/api/*` e `/ws/*` para o backend, e fazer upgrade de WebSocket. Exemplo Caddy:

```caddy
seu-dominio.com {
  reverse_proxy /api/* backend:8000
  reverse_proxy /ws/*  backend:8000
  reverse_proxy frontend:3000
}
```

---

## Endpoints

### Auth — `/auth`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/auth/register` | — | Registrar usuário. Dispara código de verificação por email |
| `POST` | `/auth/verify-email` | — | Confirma email com código de 6 dígitos. Loga o usuário (sessão curta) |
| `POST` | `/auth/resend-verification` | — | Reenvia código de verificação |
| `POST` | `/auth/login` | — | Login. Aceita `remember_me` para sessão de 30d. Bloqueia se email não verificado |
| `POST` | `/auth/refresh` | cookie `tdl_refresh` | Renova access token (rotaciona refresh com mesmo `sid`) |
| `POST` | `/auth/logout` | — | Logout. Revoga refresh atual via denylist + limpa cookies |
| `GET` | `/auth/session` | cookie `tdl_access` | Sessão atual (`SessionInfo`) |
| `POST` | `/auth/forgot-password` | — | Dispara código de 6 dígitos por email (sempre retorna 200) |
| `POST` | `/auth/reset-password` | — | Redefine senha com código + revoga todas as sessões |
| `DELETE` | `/auth/account` | ✓ + senha | Exclui a conta. Grupos onde o usuário é dono também são deletados |

### Usuário — `/users`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `GET` | `/users/me` | ✓ | Perfil do usuário (inclui `timezone`) |
| `PATCH` | `/users/me` | ✓ | Atualizar perfil (`username`, `avatar_url`, `timezone` IANA, `onboarded`) |

### Tarefas — `/tasks`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/tasks` | ✓ | Criar tarefa |
| `GET` | `/tasks` | ✓ | Listar tarefas do usuário |
| `GET` | `/tasks/group/{group_slug}` | ✓ membro | Listar tarefas do grupo |
| `PATCH` | `/tasks/{task_slug}` | ✓ | Atualizar tarefa (incluindo desatribuir assignee — ver abaixo) |
| `DELETE` | `/tasks/{task_slug}` | ✓ | Deletar tarefa |

**Desatribuir assignee**: envie `{"assignee_username": ""}` (string vazia). Omitir o campo ou enviar `null` significa "não alterar".

### Categorias — `/categories`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/categories` | ✓ | Criar categoria |
| `GET` | `/categories` | ✓ | Listar categorias do usuário |
| `GET` | `/categories/group/{group_slug}` | ✓ membro | Listar categorias do grupo |
| `PATCH` | `/categories/{category_slug}` | ✓ owner ou admin do grupo | Atualizar categoria |
| `DELETE` | `/categories/{category_slug}` | ✓ owner ou admin do grupo | Deletar categoria |

### Subtarefas — `/subtasks`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/subtasks` | ✓ | Criar subtarefa |
| `GET` | `/subtasks/task/{task_slug}` | ✓ | Listar subtarefas de uma tarefa |
| `PATCH` | `/subtasks/{subtask_slug}` | ✓ | Atualizar subtarefa (suporta desatribuir via string vazia) |
| `DELETE` | `/subtasks/{subtask_slug}` | ✓ | Deletar subtarefa |

### Hábitos diários — `/habits`

Seção **recorrente e restrita ao próprio usuário** (não compartilhável, como o modo individual). Cada hábito se repete por dia: ou `every_day` (todos os dias) ou um subconjunto de dias da semana (`days_of_week`, `0`=domingo … `6`=sábado). O progresso de cada dia é registrado num `HabitEntry` com status `pending` (pendente) / `in_progress` (em desenvolvimento) / `done` (finalizada). Só `done` conta como concluído nas porcentagens — `in_progress` é um status próprio, não conta como finalizado. "Hoje" é calculado no **fuso do usuário** (`User.timezone`, default `UTC`).

**Recorrência reflete retroativamente.** As porcentagens recalculam os "dias agendados" a partir da máscara **atual** do hábito. Mudar a recorrência (ex.: de 3 dias/semana para todos os dias) reescreve a % histórica do mês — as marcações `done` são preservadas como dados, mas o denominador se ajusta à regra vigente.

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/habits` | ✓ | Criar hábito. `every_day=true` ⇒ todos os dias; senão informe `days_of_week` (≥1 dia) |
| `GET` | `/habits` | ✓ | Listar todos os hábitos do usuário (com status de hoje) |
| `GET` | `/habits/today` | ✓ | Listar apenas os hábitos programados para hoje |
| `GET` | `/habits/stats` | ✓ | Porcentagem **diária** e **mensal** de conclusão (para a página de perfil) |
| `PATCH` | `/habits/{slug}` | ✓ | Atualizar título/descrição/recorrência |
| `PATCH` | `/habits/{slug}/status` | ✓ | Registrar status do dia (upsert). `date` opcional (default hoje); só dia agendado e não-futuro |
| `DELETE` | `/habits/{slug}` | ✓ | Deletar hábito (entries em CASCADE) |

A porcentagem diária conta `done` ÷ hábitos agendados para o dia; a mensal soma todas as ocorrências agendadas do dia 1 até a data de referência.

### Grupos — `/groups`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/groups` | ✓ | Criar grupo. Criador vira dono + admin. Retorna chave única (exibida só 1×) |
| `GET` | `/groups` | ✓ | Listar grupos do usuário |
| `GET` | `/groups/{group_slug}` | ✓ membro | Detalhes do grupo |
| `PATCH` | `/groups/{group_slug}` | ✓ admin | Atualizar nome/descrição |
| `POST` | `/groups/join` | ✓ | Solicitar entrada com chave |
| `GET` | `/groups/{group_slug}/members` | ✓ membro | Listar membros |
| `GET` | `/groups/{group_slug}/join-requests` | ✓ admin | Listar pedidos pendentes |
| `POST` | `/groups/{group_slug}/join-requests/{slug}/accept` | ✓ admin | Aceitar pedido |
| `POST` | `/groups/{group_slug}/join-requests/{slug}/reject` | ✓ admin | Rejeitar pedido |
| `DELETE` | `/groups/{group_slug}/members/{username}` | ✓ admin | Remover membro (admins só removíveis pelo dono) |
| `POST` | `/groups/{group_slug}/members/{username}/promote` | ✓ admin | Promover membro a admin |
| `DELETE` | `/groups/{group_slug}/leave` | ✓ membro | Sair do grupo (dono precisa deletar, não sair) |
| `DELETE` | `/groups/{group_slug}` | ✓ dono | Deletar grupo |

### Notificações — `/notifications`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `GET` | `/notifications` | ✓ | Listar notificações |
| `PATCH` | `/notifications/{id}/read` | ✓ | Marcar como lida |
| `PATCH` | `/notifications/read-all` | ✓ | Marcar todas como lidas |

### WebSocket

| Path | Auth | Descrição |
|---|---|---|
| `WS /ws/notifications` | cookie `tdl_access` | Notificações em tempo real |

> O WebSocket aceita exclusivamente o cookie `tdl_access`. O parâmetro `?token=` foi removido (vazava em logs, histórico e `Referer`).

### Health

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/health` | Status da aplicação |

---

## Autenticação

### Tokens

- **Access token** (`tdl_access`): JWT HS256, duração configurável (padrão 60 min), httpOnly
- **Refresh token** (`tdl_refresh`): JWT HS256, **duração absoluta** de 30 dias desde o login original (não desliza), httpOnly

### Sessão absoluta de 30 dias

O refresh token guarda dois campos no payload:
- `sid`: timestamp do login original (em segundos)
- `jti`: id único deste token específico

Cada `/auth/refresh` rotaciona o `jti` mas mantém o mesmo `sid`. O `exp` é sempre `sid + 30d`. Resultado: a sessão nunca passa de 30 dias contados do login inicial.

### Revogação

- **Logout**: o `jti` do refresh atual vai para a denylist do Redis (`refresh_denylist:{jti}`) com TTL de 30 dias.
- **Reset de senha**: grava `User.pwd_changed_at = now()`. No próximo refresh, se `sid < pwd_changed_at`, o token é rejeitado e cookies limpos. Funciona mesmo se Redis cair (a flag está no DB).
- **Reuso de refresh**: se um `jti` já na denylist for usado, retorna `REFRESH_REUSE_DETECTED` e limpa cookies.

### Verificação de email

`POST /auth/register` cria o usuário com `verified_at = null` e dispara um código de 6 dígitos por email (TTL 1h, armazenado como `sha256` no Redis). O usuário precisa chamar `POST /auth/verify-email` antes de poder logar (`POST /auth/login` retorna `EMAIL_NOT_VERIFIED` enquanto isso). `verify-email` faz login automático com sessão **curta** (só cookie `tdl_access`, sem `remember_me`).

### Recuperação de senha

`POST /auth/forgot-password` gera um código de 6 dígitos, armazena `sha256` no Redis (`pwd_reset:{user_id}`, TTL 10 min) e dispara email via `BackgroundTasks` — resposta é sempre `200 OK` com timing constante (anti-enumeração de emails).

`POST /auth/reset-password` valida o código, atualiza a senha, seta `pwd_changed_at = now()` (revoga todas as sessões) e limpa cookies.

Tentativas erradas de código são contadas (`rl:verify_code:{user_id}` / `rl:reset_code:{user_id}`) e bloqueadas em 5 falhas (anti-brute-force).

### Rate limiting por email

Implementado em `app/utils/rate_limit.py`, por chave Redis:

| Operação | Limite | Janela |
|---|---|---|
| `login` | 5 | 15 min |
| `register` | 5 | 1 h |
| `forgot-password` | 5 | 1 h |
| `resend-verification` | 5 | 1 h |
| Códigos (verify/reset) | 5 tentativas | TTL do código |

Login bem-sucedido zera o contador. Se o Redis estiver fora, o rate limit cai aberto (consistente com a decisão de tratar Redis como cache).

### Exclusão de conta

`DELETE /auth/account` exige a senha atual no body. CASCADE no banco cuida de:
- Tarefas/categorias/tags do usuário (modo individual) — deletadas
- Memberships, refresh tokens, notificações — deletadas
- Grupos onde o usuário é **dono** (`Group.admin_user_id`) — deletados (notificação WS é enviada aos membros antes da deleção)
- Tarefas onde o usuário é **assignee** (em qualquer grupo) — `assignee_user_id` vira `NULL` (ON DELETE SET NULL)

### Chave de grupo

Gerada com `secrets.token_urlsafe(32)`, exibida uma única vez para o dono, armazenada como `SHA-256`. Comparação usa `secrets.compare_digest` (timing-safe).

---

## Papéis em grupos

```
member  →  cria/edita tarefas e subtarefas (qualquer membro)
admin   →  member + gerencia membros (aceitar/rejeitar pedidos, kickar members,
           promover member a admin) + edita categorias do grupo + edita o grupo
dono    →  admin (criador do grupo, único). Apenas o dono pode deletar o grupo
           ou remover outros admins. Se deletar a conta, o grupo é deletado.
```

O dono é representado por `Group.admin_user_id` e sempre tem `GroupMember.role = admin`. Não há cargo separado de "owner" no enum — a singularidade do dono vive no campo `admin_user_id`.

---

## Banco de dados

### Modelos principais

```
User ──< GroupMember >── Group
User ──< JoinRequest  >── Group
User ──< Notification

Category ──< Task ──< Subtask
Task >──< Tag  (many-to-many via task_tags)

User ──< Habit ──< HabitEntry   (hábitos diários, só individual)
```

### Regra XOR (modo individual vs. grupo)

`Category`, `Task` e `Tag` têm uma constraint `CHECK` que garante que **ou** `owner_user_id` **ou** `group_id` está preenchido, nunca os dois:

```sql
CHECK ((owner_user_id IS NOT NULL) <> (group_id IS NOT NULL))
```

### Hierarquia de tarefas

```
Category → Task → Subtask   (1 nível apenas)
```

Subtarefas têm `assignee_user_id` próprio (nullable), independente do `assignee_user_id` da tarefa pai.

### Comportamento de FK na exclusão de usuário

| FK | Comportamento |
|---|---|
| `Task.creator_user_id`, `Task.owner_user_id` | CASCADE |
| `Task.assignee_user_id`, `Subtask.assignee_user_id` | SET NULL |
| `Group.admin_user_id` | CASCADE (deleta o grupo) |
| `GroupMember.user_id`, `Notification.user_id` | CASCADE |
| `Habit.owner_user_id` | CASCADE (deleta hábitos e seus entries) |

---

## WebSocket e Notificações

`NotificationManager` é singleton global que mantém conexões WebSocket por `user_id`. Quando um evento ocorre (pedido de entrada, tarefa atribuída, membro removido, grupo deletado, etc.), o service chama `notification_manager.push(user_id, payload)` para entregar a mensagem para todas as conexões ativas daquele usuário.

O cliente reconecta automaticamente a cada 5 segundos em caso de desconexão (implementado no frontend).

Tipos de notificação:
- `join_request_created`, `join_request_accepted`, `join_request_rejected`
- `task_assigned`, `subtask_assigned`
- `member_removed`, `group_deleted`

---

## Erros

Todos os erros seguem o formato:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Credenciais invalidas."
  }
}
```

Códigos centralizados em `app/errors/codes.py` (`ErrorCode` enum + `ERROR_CATALOG`).

---

## Redis

Usado para:

- **Códigos de verificação de email** — `email_verify:{user_id}` (sha256 do código, TTL 1h)
- **Códigos de reset de senha** — `pwd_reset:{user_id}` (sha256 do código, TTL 10 min)
- **Denylist de refresh tokens** — `refresh_denylist:{jti}` (TTL 30d)
- **Rate limiting** — `rl:{op}:{email}` e `rl:{verify|reset}_code:{user_id}` (TTLs variados)

Se o Redis estiver indisponível no startup, o sistema continua com `NullRedis` (no-op). Consequências:
- Códigos de verificação/reset não funcionam (mas a sessão sobrevive)
- Rate limit fica aberto
- Logout não revoga refresh imediatamente (mas o `pwd_changed_at` do reset ainda funciona)
