"""Un cálculo del repo entero se hace una vez por argumentos, no una vez por test."""
import memo


def test_memoizar_calcula_una_vez_por_argumentos():
    llamadas = []

    def caro(strict=False):
        llamadas.append(strict)
        return {"strict": strict}

    cacheado = memo.memoizar(caro)
    assert cacheado() == {"strict": False}
    assert cacheado() is cacheado()                      # misma respuesta, sin recalcular
    assert cacheado(strict=True) == {"strict": True}
    assert cacheado(strict=True) is cacheado(strict=True)
    assert llamadas == [False, True]


def test_memoizar_no_traga_las_excepciones():
    intentos = []

    def falla():
        intentos.append(1)
        raise RuntimeError("no se cachea un fallo")

    cacheado = memo.memoizar(falla)
    for _ in range(2):
        try:
            cacheado()
        except RuntimeError:
            pass
    assert len(intentos) == 2
