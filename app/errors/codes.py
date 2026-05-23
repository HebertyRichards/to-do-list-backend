from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    http_status: int
    message: str


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BAD_REQUEST = "BAD_REQUEST"

    UNAUTHENTICATED = "UNAUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    REFRESH_REUSE_DETECTED = "REFRESH_REUSE_DETECTED"

    FORBIDDEN = "FORBIDDEN"
    NOT_GROUP_ADMIN = "NOT_GROUP_ADMIN"
    NOT_GROUP_MEMBER = "NOT_GROUP_MEMBER"
    NOT_TASK_OWNER = "NOT_TASK_OWNER"

    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    GROUP_NOT_FOUND = "GROUP_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    SUBTASK_NOT_FOUND = "SUBTASK_NOT_FOUND"
    CATEGORY_NOT_FOUND = "CATEGORY_NOT_FOUND"
    JOIN_REQUEST_NOT_FOUND = "JOIN_REQUEST_NOT_FOUND"

    CONFLICT = "CONFLICT"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    ALREADY_GROUP_MEMBER = "ALREADY_GROUP_MEMBER"
    JOIN_REQUEST_ALREADY_PENDING = "JOIN_REQUEST_ALREADY_PENDING"

    INVALID_GROUP_KEY = "INVALID_GROUP_KEY"
    JOIN_REQUEST_EXPIRED = "JOIN_REQUEST_EXPIRED"

    DATE_RANGE_INVALID = "DATE_RANGE_INVALID"
    ASSIGNEE_NOT_IN_GROUP = "ASSIGNEE_NOT_IN_GROUP"

    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"

    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


ERROR_CATALOG: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.VALIDATION_ERROR: ErrorSpec("VALIDATION_ERROR", 400, "Dados invalidos."),
    ErrorCode.BAD_REQUEST: ErrorSpec("BAD_REQUEST", 400, "Requisicao invalida."),

    ErrorCode.UNAUTHENTICATED: ErrorSpec("UNAUTHENTICATED", 401, "Nao autenticado."),
    ErrorCode.INVALID_CREDENTIALS: ErrorSpec("INVALID_CREDENTIALS", 401, "Credenciais invalidas."),
    ErrorCode.TOKEN_EXPIRED: ErrorSpec("TOKEN_EXPIRED", 401, "Token expirado."),
    ErrorCode.TOKEN_INVALID: ErrorSpec("TOKEN_INVALID", 401, "Token invalido."),
    ErrorCode.SESSION_EXPIRED: ErrorSpec("SESSION_EXPIRED", 401, "Sessao expirada. Faca login novamente."),
    ErrorCode.REFRESH_REUSE_DETECTED: ErrorSpec("REFRESH_REUSE_DETECTED", 401, "Sessao revogada por seguranca."),

    ErrorCode.FORBIDDEN: ErrorSpec("FORBIDDEN", 403, "Acesso negado."),
    ErrorCode.NOT_GROUP_ADMIN: ErrorSpec("NOT_GROUP_ADMIN", 403, "Apenas o administrador do grupo pode executar esta acao."),
    ErrorCode.NOT_GROUP_MEMBER: ErrorSpec("NOT_GROUP_MEMBER", 403, "Voce nao pertence a este grupo."),
    ErrorCode.NOT_TASK_OWNER: ErrorSpec("NOT_TASK_OWNER", 403, "Voce nao pode editar esta tarefa."),

    ErrorCode.NOT_FOUND: ErrorSpec("NOT_FOUND", 404, "Recurso nao encontrado."),
    ErrorCode.USER_NOT_FOUND: ErrorSpec("USER_NOT_FOUND", 404, "Usuario nao encontrado."),
    ErrorCode.GROUP_NOT_FOUND: ErrorSpec("GROUP_NOT_FOUND", 404, "Grupo nao encontrado."),
    ErrorCode.TASK_NOT_FOUND: ErrorSpec("TASK_NOT_FOUND", 404, "Tarefa nao encontrada."),
    ErrorCode.SUBTASK_NOT_FOUND: ErrorSpec("SUBTASK_NOT_FOUND", 404, "Subtarefa nao encontrada."),
    ErrorCode.CATEGORY_NOT_FOUND: ErrorSpec("CATEGORY_NOT_FOUND", 404, "Categoria nao encontrada."),
    ErrorCode.JOIN_REQUEST_NOT_FOUND: ErrorSpec("JOIN_REQUEST_NOT_FOUND", 404, "Solicitacao nao encontrada."),

    ErrorCode.CONFLICT: ErrorSpec("CONFLICT", 409, "Conflito de estado."),
    ErrorCode.EMAIL_ALREADY_REGISTERED: ErrorSpec("EMAIL_ALREADY_REGISTERED", 409, "Email ja cadastrado."),
    ErrorCode.USERNAME_TAKEN: ErrorSpec("USERNAME_TAKEN", 409, "Nome de usuario indisponivel."),
    ErrorCode.ALREADY_GROUP_MEMBER: ErrorSpec("ALREADY_GROUP_MEMBER", 409, "Voce ja faz parte deste grupo."),
    ErrorCode.JOIN_REQUEST_ALREADY_PENDING: ErrorSpec("JOIN_REQUEST_ALREADY_PENDING", 409, "Ja existe uma solicitacao pendente para este grupo."),

    ErrorCode.INVALID_GROUP_KEY: ErrorSpec("INVALID_GROUP_KEY", 400, "Chave de grupo invalida."),
    ErrorCode.JOIN_REQUEST_EXPIRED: ErrorSpec("JOIN_REQUEST_EXPIRED", 410, "Solicitacao expirada. Tente novamente."),

    ErrorCode.DATE_RANGE_INVALID: ErrorSpec("DATE_RANGE_INVALID", 400, "Data de inicio deve ser anterior a data limite."),
    ErrorCode.ASSIGNEE_NOT_IN_GROUP: ErrorSpec("ASSIGNEE_NOT_IN_GROUP", 400, "Usuario atribuido nao faz parte do grupo."),

    ErrorCode.TOO_MANY_REQUESTS: ErrorSpec("TOO_MANY_REQUESTS", 429, "Muitas requisicoes. Tente mais tarde."),

    ErrorCode.DATABASE_ERROR: ErrorSpec("DATABASE_ERROR", 500, "Erro ao acessar dados."),
    ErrorCode.INTERNAL_SERVER_ERROR: ErrorSpec("INTERNAL_SERVER_ERROR", 500, "Erro interno do servidor."),
}
