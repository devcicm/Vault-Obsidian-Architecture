"""Tests de paquete de la ID norma AP-82 (Dispose LIFO idempotente y LeaseHeartbeat)."""

import pytest

from vault.kernel.ciclo_ejecucion import GestorDispose, LeaseHeartbeat


def test_ap82_dispose_lifo_idempotente_y_preserva_excepcion_raiz():
    orden = []
    gestor = GestorDispose()
    with pytest.raises(ValueError, match="fallo_raiz"):
        with gestor:
            gestor.register("lock", lambda: orden.append("lock"))
            gestor.register("temp", lambda: (_ for _ in ()).throw(RuntimeError("error_cleanup")))
            gestor.register("subproceso", lambda: orden.append("subproceso"))
            raise ValueError("fallo_raiz")

    assert orden == ["subproceso", "lock"]
    assert gestor.disposed is True
    assert len(gestor.dispose_errors) == 1
    assert gestor.dispose_errors[0]["resource"] == "temp"
    # Idempotencia: segunda llamada a dispose() es no-op
    gestor.dispose()
    assert orden == ["subproceso", "lock"]


def test_ap82_lease_heartbeat_expiracion_y_renovacion():
    reloj = [100.0]
    lease = LeaseHeartbeat("worker-1", ttl_seconds=10.0, clock=lambda: reloj[0])
    assert lease.is_expired() is True
    lease.acquire_lease()
    assert lease.is_expired() is False
    reloj[0] = 109.0
    lease.renew_lease()
    reloj[0] = 115.0
    assert lease.is_expired() is False
    reloj[0] = 125.0
    assert lease.is_expired() is True
