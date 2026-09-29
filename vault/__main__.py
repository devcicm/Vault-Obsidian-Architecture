"""``python -m vault``: la misma CLI que el entry point ``vault``.

En Windows el directorio ``Scripts/`` de un venv o de ``pip install --user`` no
siempre está en el PATH; sin este módulo, quien instala la wheel no tenía forma
de llegar a la CLI salvo adivinar la ruta del ejecutable.
"""

import sys

from .product_cli import main

sys.exit(main())
