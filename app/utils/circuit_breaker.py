import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    closed = "closed"  # tudo normal: chamadas passam
    open = "open"  # dependencia caida: chamadas sao curto-circuitadas
    half_open = "half_open"  # periodo de teste: deixa passar uma sonda


class CircuitBreaker:
    """
    Estados:
      - closed: chamadas passam normalmente; falhas consecutivas sao contadas.
      - open: apos `failure_threshold` falhas, o circuito abre por
        `recovery_timeout` segundos e as chamadas sao curto-circuitadas
        (sem nem tentar tocar na dependencia, evitando martelar algo que ja caiu).
      - half_open: passado o cooldown, uma sonda e liberada. Se ela tem sucesso,
        o circuito fecha; se falha, reabre por mais um cooldown.

    Como o app roda em event loop unico (asyncio), as transicoes nao precisam
    de lock: nao ha await entre ler e escrever o estado.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "circuit",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._name = name
        self._state = CircuitState.closed
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    def is_tripped(self) -> bool:
        """True quando o circuito esta aberto E ainda dentro do cooldown.

        Checagem sem efeito colateral: nao consome a sonda do half-open. Usada
        por quem so quer saber se vale a pena tentar (ex.: is_redis_available).
        """
        if self._state is CircuitState.open:
            return (time.monotonic() - self._opened_at) < self._recovery_timeout
        return False

    def allow(self) -> bool:
        """Decide se uma chamada pode prosseguir, transicionando o estado.

        Deve ser chamada uma vez por tentativa de uso da dependencia.
        """
        if self._state is CircuitState.open:
            if (time.monotonic() - self._opened_at) >= self._recovery_timeout:
                self._state = CircuitState.half_open
                logger.info("Circuit '%s' -> half_open (liberando sonda)", self._name)
                return True
            return False
        return True

    def record_success(self) -> None:
        if self._state is not CircuitState.closed:
            logger.info("Circuit '%s' -> closed (recuperado)", self._name)
        self._state = CircuitState.closed
        self._failures = 0

    def record_failure(self) -> None:
        if self._state is CircuitState.half_open:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._trip()

    def reset(self) -> None:
        self._state = CircuitState.closed
        self._failures = 0
        self._opened_at = 0.0

    def _trip(self) -> None:
        self._state = CircuitState.open
        self._opened_at = time.monotonic()
        self._failures = 0
        logger.warning(
            "Circuit '%s' -> open por %.0fs (dependencia indisponivel)",
            self._name,
            self._recovery_timeout,
        )
