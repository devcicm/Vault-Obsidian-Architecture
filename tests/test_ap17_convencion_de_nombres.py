"""AP-17 no puede confundir un contrato con su implementación.

Síntoma real: `vault_onboard` contra un proyecto .NET ajeno al estándar dio
`canonicalShadow: 8`, y los ocho pares eran interfaz/implementación
(`IRateLimitService` / `RateLimitService`). AP-17 compara títulos en minúsculas;
bajar la `I` borra el único carácter que los distingue y la similitud sale ~0.98
siempre. No es un umbral mal puesto —bajarlo esconde el síntoma y deja la norma
ciega a los duplicados de verdad—: es medir con la normalización propia en vez
de con la del dominio (AP-44).

Un vault de .NET, Java o TypeScript dispara esto en proporción a su número de
servicios, así que la norma se volvía ruido justo en los vaults más grandes.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_audit import (  # noqa: E402
    _MARCADORES_DE_CONVENCION,
    _distintos_por_convencion,
)


@pytest.mark.parametrize(
    "a,b",
    [
        ("IRateLimitService", "RateLimitService"),
        ("IHttpRouter", "HttpRouter"),
        ("AbstractTokenStore", "TokenStore"),
        ("BaseController", "Controller"),
        ("DefaultSerializer", "Serializer"),
        ("TokenStoreImpl", "TokenStore"),
        ("PaymentGatewayInterface", "PaymentGateway"),
        ("MockClock", "Clock"),
        ("FakeClock", "Clock"),
        ("StubClock", "Clock"),
        ("NullRateLimitService", "RateLimitService"),
        ("NoopMailer", "Mailer"),
        # El marcador puede estar en los DOS lados: ninguno es prefijo del otro
        ("ILoggerService", "MockLoggerService"),
        ("AbstractTokenStore", "TokenStoreImpl"),
        # y en el orden inverso: el par no tiene lado
        ("RateLimitService", "IRateLimitService"),
    ],
)
def test_contrato_e_implementacion_son_dos_notas(a, b):
    assert _distintos_por_convencion(a, b), f"{a} / {b} reportados como sombra"


@pytest.mark.parametrize(
    "a,b",
    [
        # Duplicados reales: la norma tiene que seguir viéndolos.
        ("Rate Limit Service", "rate-limit-service"),
        ("RateLimitService", "RateLimitServices"),
        ("TokenStore", "TokenStorage"),
        ("HttpRouter", "HttpRouters"),
        # Un marcador NO justifica cualquier diferencia: aquí sobra 'Cache'
        ("IRateLimitService", "RateLimitCacheService"),
    ],
)
def test_los_duplicados_de_verdad_siguen_saliendo(a, b):
    assert _distintos_por_convencion(a, b) is None, f"{a} / {b} silenciados de más"


def test_el_mismo_nombre_nunca_se_justifica():
    """La igualdad no es una convención: es una sombra."""
    assert _distintos_por_convencion("TokenStore", "token-store") is None
    assert _distintos_por_convencion("TokenStore", "TokenStore") is None


@pytest.mark.parametrize(
    "a,b",
    [
        # `Async` y `Secure` describen una variante, no un rol en el mismo
        # contrato. Se dejan fuera a propósito: silenciarlos también sería
        # apagar la norma para los duplicados que sí lo son.
        ("AsyncLoggerService", "LoggerService"),
        ("SecureApiKeyService", "IApiKeyService"),
        ("CachedTokenStore", "TokenStore"),
    ],
)
def test_las_variantes_no_son_marcadores_de_rol(a, b):
    assert _distintos_por_convencion(a, b) is None, f"{a} / {b}: la norma se apagó de más"


def test_los_marcadores_declaran_prefijo_o_sufijo_pero_no_ambos():
    """Un marcador con las dos casillas llenas casaría de más sin que se note."""
    for prefijo, sufijo in _MARCADORES_DE_CONVENCION:
        assert bool(prefijo) != bool(sufijo), (prefijo, sufijo)
        assert (prefijo or sufijo).islower(), "el marcador se compara normalizado"


def test_el_detector_completo_no_reporta_el_par_de_interfaz(tmp_path, monkeypatch):
    """Con el criterio del consumidor: el detector real sobre ficheros reales."""
    import vault_audit

    vault = tmp_path / "vault"
    (vault / "11_Code").mkdir(parents=True)
    for nombre, titulo in [
        ("irate-limit-service.md", "IRateLimitService"),
        ("rate-limit-service.md", "RateLimitService"),
        ("token-store.md", "TokenStore"),
        ("token-storage.md", "TokenStorage"),
    ]:
        (vault / "11_Code" / nombre).write_text(
            f"---\ntitle: {titulo}\ntype: code\nstatus: draft\n---\n\nCuerpo.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(vault_audit, "VAULT_ROOT", vault)
    notas = sorted((vault / "11_Code").glob("*.md"))
    pares = vault_audit._detect_canonical_shadow(notas)

    titulos = {tuple(sorted((p["titleA"], p["titleB"]))) for p in pares}
    assert ("iratelimitservice", "ratelimitservice") not in titulos
    # TokenStore/TokenStorage sí es una sombra y tiene que seguir apareciendo.
    assert ("tokenstorage", "tokenstore") in titulos, pares
