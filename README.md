# To-Do List — Backend

API REST + WebSocket construída com **FastAPI**, **SQLAlchemy 2 async** e **PostgreSQL** (Neon). Suporta modo individual e modo grupo com autenticação JWT em cookies httpOnly e notificações em tempo real.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | FastAPI 0.115.6 |
| ORM | SQLAlchemy 2.0 (asyncio + asyncpg) |
| Banco de dados | PostgreSQL |
| Migrações | Alembic |
| Validação | Pydantic 2 |
| Autenticação | JWT via `python-jose` + cookies httpOnly |
| Cache | Redis 8 (com fallback `NullRedis` se indisponível) |
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
│   │   ├── redis_client.py     # NullRedis fallback + init_redis()
│   │   └── settings.py         # Pydantic Settings (@lru_cache, campos obrigatórios)
│   ├── errors/
│   │   ├── codes.py            # Enum ErrorCode + ERROR_CATALOG
│   │   ├── exceptions.py       # AppException
│   │   └── handlers.py         # Exception handlers FastAPI
│   ├── models/                 # ORM SQLAlchemy
│   │   ├── base.py             # Base + TimestampMixin
│   │   ├── user.py
│   │   ├── refresh_token.py
│   │   ├── category.py
│   │   ├── task.py             # enum TaskStatus
│   │   ├── subtask.py
│   │   ├── tag.py
│   │   ├── group.py
│   │   ├── group_member.py     # enum GroupRole
│   │   ├── join_request.py     # enum JoinRequestStatus
│   │   └── notification.py     # enum NotificationType
│   ├── repositories/           # Queries SQLAlchemy
│   ├── routes/                 # APIRouter (sem lógica)
│   ├── schemas/                # Pydantic input/output
│   ├── services/               # Regras de negócio
│   ├── utils/
│   │   ├── cookies.py          # set_access_cookie, set_refresh_cookie, clear_auth_cookies
│   │   ├── dependencies.py     # get_current_user, get_current_user_ws
│   │   └── security.py         # JWT, hash de senha, chave de grupo
│   └── ws/
│       ├── manager.py          # NotificationManager singleton
│       └── routes.py           # /ws/notifications
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── alembic.ini
```

---

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do backend. Todos os campos são obrigatórios — não há fallback em produção.

### Desenvolvimento local

```env
APP_ENV=development
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@ep-xxx-pooler.sa-east-1.aws.neon.tech/neondb?ssl=require
DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASSWORD@ep-xxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

REDIS_URL=redis://localhost:6379/0

JWT_SECRET=<saída do openssl rand -hex 32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=60
REFRESH_TOKEN_DAYS=30

FRONTEND_ORIGIN=http://localhost:3000
COOKIE_DOMAIN=
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

### Produção (Docker)

```env
APP_ENV=production
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@ep-xxx-pooler.sa-east-1.aws.neon.tech/neondb?ssl=require
DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASSWORD@ep-xxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

REDIS_URL=redis://redis:6379/0

JWT_SECRET=<saída do openssl rand -hex 32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=60
REFRESH_TOKEN_DAYS=30

FRONTEND_ORIGIN=https://seu-dominio.com
COOKIE_DOMAIN=seu-dominio.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

### Sobre as duas `DATABASE_URL`

O Neon fornece dois endpoints distintos:

| Variável | Host | Driver | Uso |
|---|---|---|---|
| `DATABASE_URL` | `ep-xxx-pooler…` (com `-pooler`) | `+asyncpg` | Runtime (FastAPI async) |
| `DATABASE_URL_SYNC` | `ep-xxx…` (sem `-pooler`) | `+psycopg2` | Alembic migrations (sync) |

A URL base vem do painel do Neon em **Connection string**. Para obter a URL direta (sem pooler), remova `-pooler` do hostname.

### Como gerar o `JWT_SECRET`

```bash
openssl rand -hex 32
```

Nunca reutilize o segredo entre ambientes e nunca commite o `.env`.

---

## Desenvolvimento local

### Pré-requisitos

- Python 3.11+
- PostgreSQL (Neon ou local)
- Redis acessível na `REDIS_URL` configurada

### 1. Instalar dependências

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Criar `.env`

Crie o arquivo `.env` na raiz do backend com os valores da seção **Variáveis de ambiente — Desenvolvimento local** acima.

### 3. Rodar migrações

```bash
alembic upgrade head
```

> Para criar uma nova migration após alterar models:
> ```bash
> alembic revision --autogenerate -m "descricao"
> alembic upgrade head
> ```

### 4. Iniciar servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa em `http://localhost:8000/docs`.

---

## Produção com Docker

A stack completa (backend + frontend) sobe a partir do `docker-compose.yml` deste repositório. Os dois projetos precisam estar na mesma pasta pai:

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

> `DATABASE_URL`, `REDIS_URL` e `JWT_SECRET` devem vir do gestor de segredos da sua infraestrutura (Vault, AWS Secrets Manager, GitHub Actions secrets, etc.) — nunca commitar.

### 2. Rodar migrações uma vez

```bash
docker compose run --rm backend alembic upgrade head
```

### 3. Subir a stack

```bash
docker compose up -d --build
docker compose logs -f
```

### 4. Atualizar deploy

```bash
git pull
docker compose build
docker compose up -d
```

Serviços:

| Serviço | Porta exposta | Rede |
|---|---|---|
| `redis` | — (interno) | `internal` |
| `backend` | `8000:8000` | `internal` + `public` |
| `frontend` | `3000:3000` | `public` |

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
| `POST` | `/auth/register` | — | Registrar usuário. Retorna `SessionInfo` + cookies |
| `POST` | `/auth/login` | — | Login. Retorna `SessionInfo` + cookies |
| `POST` | `/auth/refresh` | cookie `tdl_refresh` | Renovar access token |
| `POST` | `/auth/logout` | — | Logout. Limpa cookies |
| `GET` | `/auth/session` | cookie `tdl_access` | Sessão atual (`SessionInfo`) |
| `POST` | `/auth/forgot-password` | — | Solicita token de redefinição (TTL 1h no Redis) |
| `POST` | `/auth/reset-password` | — | Redefine senha com token + revoga sessões |

### Usuário — `/users`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `GET` | `/users/me` | ✓ | Perfil do usuário |
| `PATCH` | `/users/me` | ✓ | Atualizar perfil |

### Tarefas — `/tasks`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/tasks` | ✓ | Criar tarefa |
| `GET` | `/tasks` | ✓ | Listar tarefas do usuário |
| `GET` | `/tasks/group/{group_id}` | ✓ membro | Listar tarefas do grupo |
| `PATCH` | `/tasks/{task_id}` | ✓ | Atualizar tarefa |
| `DELETE` | `/tasks/{task_id}` | ✓ | Deletar tarefa |

### Categorias — `/categories`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/categories` | ✓ | Criar categoria |
| `GET` | `/categories` | ✓ | Listar categorias do usuário |
| `GET` | `/categories/group/{group_id}` | ✓ membro | Listar categorias do grupo |
| `PATCH` | `/categories/{category_id}` | ✓ | Atualizar categoria |
| `DELETE` | `/categories/{category_id}` | ✓ | Deletar categoria |

### Subtarefas — `/subtasks`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/subtasks` | ✓ | Criar subtarefa |
| `GET` | `/subtasks/task/{task_id}` | ✓ | Listar subtarefas de uma tarefa |
| `PATCH` | `/subtasks/{subtask_id}` | ✓ | Atualizar subtarefa |
| `DELETE` | `/subtasks/{subtask_id}` | ✓ | Deletar subtarefa |

### Grupos — `/groups`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `POST` | `/groups` | ✓ | Criar grupo. Retorna chave única (exibida só 1×) |
| `POST` | `/groups/join` | ✓ | Solicitar entrada com chave |
| `GET` | `/groups/{group_id}/members` | ✓ membro | Listar membros |
| `GET` | `/groups/{group_id}/join-requests` | ✓ admin | Listar pedidos pendentes |
| `POST` | `/groups/{group_id}/join-requests/{id}/accept` | ✓ admin | Aceitar pedido |
| `POST` | `/groups/{group_id}/join-requests/{id}/reject` | ✓ admin | Rejeitar pedido |
| `DELETE` | `/groups/{group_id}/members/{user_id}` | ✓ admin | Remover membro |
| `DELETE` | `/groups/{group_id}/leave` | ✓ membro | Sair do grupo |
| `DELETE` | `/groups/{group_id}` | ✓ admin | Deletar grupo |

### Notificações — `/notifications`

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `GET` | `/notifications` | ✓ | Listar notificações |
| `PATCH` | `/notifications/{id}/read` | ✓ | Marcar como lida |
| `PATCH` | `/notifications/read-all` | ✓ | Marcar todas como lidas |

### WebSocket

| Path | Auth | Descrição |
|---|---|---|
| `WS /ws/notifications` | cookie `tdl_access` ou `?token=` | Notificações em tempo real |

### Health

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/health` | Status da aplicação |

---

## Autenticação

### Tokens

- **Access token** (`tdl_access`): JWT HS256, duração configurável (padrão 60 min), httpOnly
- **Refresh token** (`tdl_refresh`): JWT HS256, duração absoluta de 30 dias desde o login original (não deslizante), httpOnly

### Sessão absoluta de 30 dias

O refresh token **rotaciona** o valor a cada renovação, mas a sessão nunca ultrapassa `session_started_at + 30d`. Isso é garantido pelo campo `session_expires_at` armazenado na tabela `refresh_tokens`.

### Detecção de reuso de refresh token

Se um refresh token já revogado for usado, **todos os refresh tokens do usuário são revogados** e os cookies são limpos. Isso mitiga ataques de roubo de token.

### Chave de grupo

A chave de acesso ao grupo é gerada com `secrets.token_urlsafe(32)`, exibida uma única vez para o admin e armazenada apenas como `SHA-256`. A comparação usa `secrets.compare_digest` para evitar timing attacks.

### Recuperação de senha

`POST /auth/forgot-password` gera um token aleatório (`secrets.token_urlsafe(32)`) e armazena no Redis em `pwd_reset:{token}` com TTL de 1 hora, mapeando para o `user_id`. A resposta é sempre `200 OK` mesmo se o email não existir (anti-enumeração).

`POST /auth/reset-password` valida o token, atualiza a senha, **revoga todos os refresh tokens do usuário** (logout em todos os dispositivos), limpa cookies e remove o token do Redis. Token usado é descartado e não pode ser reutilizado.

Como o plano free não tem serviço de email, o token é devolvido inline no campo `reset_token` da resposta de `/auth/forgot-password` para fins de desenvolvimento. Em produção real esse campo deve ser removido e o token enviado por email.

---

## Banco de dados

### Modelos principais

```
User ──< RefreshToken
User ──< GroupMember >── Group
User ──< JoinRequest  >── Group
User ──< Notification

Category ──< Task ──< Subtask
Task >──< Tag  (many-to-many via task_tags)
```

### Regra XOR (modo individual vs. grupo)

`Category`, `Task` e `Tag` têm uma constraint `CHECK` que garante que **ou** `owner_user_id` **ou** `group_id` está preenchido, nunca os dois:

```sql
CHECK (
  (owner_user_id IS NOT NULL AND group_id IS NULL) OR
  (owner_user_id IS NULL     AND group_id IS NOT NULL)
)
```

### Hierarquia de tarefas

```
Category → Task → Subtask   (1 nível apenas)
```

Subtarefas têm `assignee_user_id` próprio (nullable), independente do `assignee_user_id` da tarefa pai.

---

## WebSocket e Notificações

O `NotificationManager` é um singleton global que mantém as conexões WebSocket abertas por usuário. Quando um evento ocorre (pedido de entrada, tarefa atribuída, membro removido, etc.), o service correspondente chama `notification_manager.push(user_id, payload)`, que entrega a mensagem para todas as conexões ativas daquele usuário.

O cliente reconecta automaticamente a cada 5 segundos em caso de desconexão (implementado no frontend).

---

## Erros

Todos os erros seguem o formato:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email ou senha incorretos."
  }
}
```

Os códigos estão centralizados em `app/errors/codes.py` (`ErrorCode` enum + `ERROR_CATALOG`). Nenhum erro é persistido no banco (limitação do plano free Neon).

---

## Redis

Usado para:

- **Pedidos de entrada em grupo** — `join_request:{id}` com TTL de 3 dias
- **Tokens de redefinição de senha** — `pwd_reset:{token}` com TTL de 1 hora

Se o Redis estiver indisponível no startup, o sistema continua funcionando com um `NullRedis` (no-op) — dados que precisam expirar automaticamente via TTL deixam de expirar, mas o restante (pedidos em DB, senhas) continua íntegro.
