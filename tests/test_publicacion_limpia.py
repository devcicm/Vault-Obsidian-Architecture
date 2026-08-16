"""Lo que se publica es solo el estándar. Nada ajeno, nada local, nada sensible.

Este repositorio es **público**, y a su lado en el disco viven copias de vaults
reales de otros proyectos (`_datasets/`, `_datasets-reports/`,
`_backups-builderx/`): notas privadas, runbooks con credenciales, datos de
clientes. Se copian aquí para estudiar cómo se degradan los vaults en uso real
y volcar esas conclusiones en normas — nunca para versionarlas.

Hoy eso lo sostiene el `.gitignore`, y **un `.gitignore` es advisory**: no
protege de un `git add -f`, no protege de un directorio hermano nuevo que nadie
añada al fichero, y no protege de que alguien reordene las reglas y rompa la
cadena de des-ignorados de `vault-sandbox/`. Un fallo ahí no da error: da un
commit que se publica. Y publicado es publicado, aunque se borre después.

Es el mismo defecto que el resto del repo persigue —la promesa vive en prosa y
nadie la ejerce— aplicado al momento en que más caro sale. Por eso la promesa
se mide contra el índice de git, que es lo que de verdad se sube.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Directorios cuyo contenido NUNCA puede versionarse, con el motivo escrito.
#: Si aparece uno nuevo, va aquí y al `.gitignore` — los dos, y este test
#: comprueba que están los dos.
PROHIBIDOS = {
    "_datasets": "copias de vaults reales de otros proyectos",
    "_datasets-reports": "informes derivados de esas copias",
    "_backups-builderx": "backups de un repo ajeno, en solo lectura",
    "vault-backups": "backups de runtime de vaults del usuario",
    ".history": "historial local del editor",
}


#: Ruta absoluta que apunta al directorio personal de alguien.
RUTA_PERSONAL = re.compile(
    r"[Cc]:[\\/]+Users[\\/]+[^\s\"'`)\]]+|/(?:home|Users)/[A-Za-z][^\s\"'`)\]]*"
)

#: Nombres de usuario que delatan un ejemplo documentado, no una máquina real.
GENERICOS = {"...", "user", "usuario", "tu-usuario", "username", "nombre"}


def _segmento_de_usuario(ruta: str) -> str:
    """Lo que va justo detrás de `Users/` o `home/`, normalizado.

    Es el único trozo que distingue un ejemplo de una filtración, y por eso se
    extrae en vez de buscar palabras sueltas en la ruta entera.
    """
    partes = [p for p in re.split(r"[\\/]+", ruta) if p]
    for i, parte in enumerate(partes):
        if parte.lower() in ("users", "home") and i + 1 < len(partes):
            siguiente = partes[i + 1]
            if siguiente.startswith("<") and siguiente.endswith(">"):
                return "..."  # `<tu-usuario>` es un hueco, no un nombre
            return siguiente.lower()
    return ""


def _trackeados():
    salida = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")
    return [p for p in salida.split("\0") if p]


def test_ningun_directorio_prohibido_esta_versionado():
    """La comprobación que de verdad importa: contra el índice, no contra el disco."""
    culpables = []
    for ruta in _trackeados():
        cabeza = ruta.split("/", 1)[0]
        if cabeza in PROHIBIDOS:
            culpables.append(f"{ruta}  ({PROHIBIDOS[cabeza]})")
    assert not culpables, (
        "hay material ajeno o sensible en el índice de git, y este repo es "
        "público. Sácalo con `git rm --cached` ANTES de cualquier push:\n  "
        + "\n  ".join(culpables[:20])
    )


def test_todo_prohibido_esta_declarado_en_gitignore():
    """El test de arriba mide el presente; este impide que el futuro se cuele.

    Un directorio que solo está en esta lista y no en `.gitignore` sale como
    untracked en cada `git status` y acaba añadido por un `git add .`.
    """
    texto = (ROOT / ".gitignore").read_text(encoding="utf-8")
    reglas = {l.strip().rstrip("/") for l in texto.splitlines() if l.strip()}
    faltan = [d for d in PROHIBIDOS if d not in reglas]
    assert not faltan, (
        f"declarados prohibidos pero ausentes del .gitignore: {faltan}. "
        "Un `git add .` los añadiría sin que nada avisara."
    )


def test_ninguna_ruta_local_del_autor_esta_publicada():
    """Una ruta de la máquina del autor en un doc público es ruido y es huella.

    `LICENSE` queda fuera: el copyright es una afirmación deliberada, no una
    filtración. Y un **placeholder** —`C:/Users/.../mi-vault`, `/home/user/`—
    tampoco lo es: es la forma correcta de documentar una ruta de ejemplo, y
    marcarla convertiría este test en el guard con falsos positivos que acaba
    desactivado. Se distinguen por el segmento de usuario: si es `...`, `user`,
    `usuario`, `tu-usuario` o va entre `<>`, nadie está publicando su máquina.
    """
    patron = RUTA_PERSONAL
    #: Nombres de usuario que delatan un ejemplo, no una máquina real. Se
    #: comparan contra el **segmento de usuario** —lo que va justo detrás de
    #: `Users/` o `home/`—, no contra la ruta entera: la primera versión
    #: buscaba `users` en cualquier posición y casaba con el propio `Users\`
    #: del prefijo, o sea eximía TODA ruta de Windows. Verde y ciega a la vez,
    #: que es justo el defecto que este fichero existe para no cometer. Lo
    #: destapó su propio test de autocomprobación, no una revisión.
    culpables = []
    for ruta in _trackeados():
        if ruta in ("LICENSE", "tests/test_publicacion_limpia.py"):
            continue
        f = ROOT / ruta
        if not f.is_file() or f.suffix in (".png", ".jpg", ".ico"):
            continue
        texto = f.read_text(encoding="utf-8", errors="replace")
        for m in patron.finditer(texto):
            if _segmento_de_usuario(m.group(0)) in GENERICOS:
                continue
            linea = texto[: m.start()].count("\n") + 1
            culpables.append(f"{ruta}:{linea}: {m.group(0)[:60]}")
    assert not culpables, (
        "ruta absoluta de la máquina del autor en material publicado. Usa una "
        "ruta relativa o un marcador genérico:\n  " + "\n  ".join(culpables[:20])
    )


def test_no_hay_credenciales_con_forma_de_credencial():
    """Red de seguridad de última línea, no un escáner de secretos.

    Solo caza la forma `clave = "valor largo"`. Lo que no ve —un secreto en una
    variable con nombre inocente, un `.env` versionado por error— lo declara
    así en vez de dar el repo por limpio: `cli/safety.py` y
    `vault_secret_scan` cubren el contenido de los vaults; esto cubre el
    momento de publicar el toolkit.

    `tests/test_vault_secret_scan.py` queda exento **por ser el dueño**: sus
    cadenas son los fixtures que ejercitan `cli/safety.py`, y un escáner de
    secretos sin secretos de prueba no prueba nada. Es la única exención, y va
    escrita aquí en vez de aflojar el patrón — aflojarlo habría dejado de ver
    también los secretos de verdad.
    """
    patron = re.compile(
        r"(?i)(api[_-]?key|secret|password|passwd|access[_-]?token)"
        r"\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{16,}[\"']"
    )
    prefijos = re.compile(r"ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
    culpables = []
    for ruta in _trackeados():
        if ruta in ("tests/test_publicacion_limpia.py",
                    "tests/test_vault_secret_scan.py"):
            continue  # el que escribe los patrones, y el dueño de los fixtures
        f = ROOT / ruta
        if not f.is_file() or f.suffix in (".png", ".jpg", ".ico"):
            continue
        texto = f.read_text(encoding="utf-8", errors="replace")
        for m in list(patron.finditer(texto)) + list(prefijos.finditer(texto)):
            linea = texto[: m.start()].count("\n") + 1
            culpables.append(f"{ruta}:{linea}")
    assert not culpables, (
        "algo con forma de credencial está versionado:\n  " + "\n  ".join(culpables[:20])
    )


def test_el_barrido_caza_lo_que_dice_cazar():
    """Un barrido verde puede estarlo por no mirar bien (AP-44).

    Las tres cadenas de abajo son las tres formas que los tests de arriba
    prometen ver. Si alguna deja de casar, el test correspondiente está ciego
    y verde a la vez, que es la peor combinación posible en el guard que mira
    lo que se publica.
    """
    real = r"ver C:\Users\alguien\Documents\repo\x.md"
    m = RUTA_PERSONAL.search(real)
    assert m, "el patrón no ve una ruta personal de Windows"
    assert _segmento_de_usuario(m.group(0)) not in GENERICOS, (
        "la exención de placeholders se tragó una ruta real: entonces el test "
        "de arriba está verde por no mirar, no por estar limpio"
    )

    for ejemplo in ("C:/Users/.../mi-vault", "/home/user/proyecto",
                    "C:\\Users\\<tu-usuario>\\v"):
        m = RUTA_PERSONAL.search(ejemplo)
        assert m, f"el patrón no ve {ejemplo!r}"
        assert _segmento_de_usuario(m.group(0)) in GENERICOS, (
            f"placeholder no exento: {ejemplo} → "
            f"{_segmento_de_usuario(m.group(0))!r}"
        )

    cred = re.compile(
        r"(?i)(api[_-]?key|secret|password|passwd|access[_-]?token)"
        r"\s*[:=]\s*[\"'][A-Za-z0-9_\-/+]{16,}[\"']"
    )
    assert cred.search('api_key = "' + "A" * 24 + '"')
    assert not cred.search('password = "..."'), "un placeholder no es un secreto"


def test_el_contrato_del_sandbox_sigue_versionado():
    """La otra mitad: excluir de más también rompe.

    `vault-sandbox/` está ignorado entero salvo `00_System/tool-spec.json`, que
    es fuente de verdad de los contratos de tools y del catálogo MCP. La cadena
    de des-ignorados que lo consigue es frágil —git no re-incluye un fichero si
    un directorio padre está excluido— y una reordenación del `.gitignore` lo
    dejaría fuera del repo sin que nada fallara.
    """
    assert "vault-sandbox/00_System/tool-spec.json" in _trackeados(), (
        "el contrato de tools dejó de estar versionado: la cadena de "
        "des-ignorados de vault-sandbox/ en .gitignore se rompió"
    )


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-v"]))
