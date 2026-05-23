# To-Do List — Backend

API REST + WebSocket construída com **FastAPI**, **SQLAlchemy 2 async** e **PostgreSQL** (Neon). Suporta modo individual e modo grupo com autenticação JWT em cookies httpOnly e notificações em tempo real.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | FastAPI 0.115.6 |
| ORM | SQLAlchemy 2.0 (asyncio + asyncpg) |
| Banco de dados | PostgreSQL (Neon free tier) |
| Migrações | Alembic |
| Validação | Pydantic 2 |
| Autenticação | JWT via `python-jose` + cookies httpOnly |
| Cache / filas | Redis 7 (com fallback `NullRedis` se indisponível) |
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
├── alembic.ini
└── .env.example
```

---

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha todos os campos (todos são obrigatórios — não há fallback em produção).

```env
# Aplicação
APP_ENV=development          # development | production
APP_PORT=8000
LOG_LEVEL=INFO               # DEBUG | INFO | WARNING | ERROR

# Banco de dados
DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST/DB?ssl=require
DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASS@HOST/DB?sslmode=require

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET=                  # openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=60
REFRESH_TOKEN_DAYS=30

# CORS / Cookies
FRONTEND_ORIGIN=http://localhost:3000
COOKIE_DOMAIN=               # Deixar vazio em desenvolvimento
COOKIE_SECURE=false          # true em produção (HTTPS)
COOKIE_SAMESITE=lax
```

---

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- PostgreSQL (ou conta Neon)
- Redis (ou Docker)

### 1. Instalar dependências

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# Editar .env com os dados do banco e JWT_SECRET
```

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

Acesse a documentação interativa em `http://localhost:8000/docs`.

---

## Docker (stack completa)

Os dois repositórios precisam estar na mesma pasta pai:

```
projetos/
├── to-do-list/          # frontend
└── to-do-list-backend/  # backend ← docker-compose.yml aqui
```

```bash
# Na pasta do backend
cp .env.example .env
# Editar .env

# Subir tudo
docker compose up -d
```

Serviços:

| Serviço | Porta | Rede |
|---|---|---|
| Redis | 6379 (interno) | internal |
| Backend | 8000 | internal + public |
| Frontend | 3000 | public |

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

O Redis é usado para armazenar pedidos de entrada em grupo (`join_request:{id}`) com TTL de 3 dias. Se o Redis estiver indisponível no startup, o sistema continua funcionando com um `NullRedis` (no-op) — os pedidos continuam gravados no PostgreSQL, só a expiração automática via TTL fica inativa.
