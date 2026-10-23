"""AP-53 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {'code': 'AP-53',
 'distinguido_de': {'AP-13': 'AP-13 mide el timestamp del frontmatter '
                             'contra su propio formato: inválido o '
                             'incompleto. AP-53 mide la afirmación '
                             'histórica contra git: la fecha es valida y '
                             'no coincide con el commit. El discriminador '
                             'es si hay una fuente externa contra la que '
                             'contrastar.',
                    'AP-68': 'AP-53 obliga a contrastar el historial '
                             'afirmado contra git, y su guard es '
                             '`vault_changelog_check`; AP-68 vigila **cómo '
                             'se pide** ese git: el changelog lee, valida '
                             'el hash con `asegurar_hash` y no muta nada, '
                             'porque la llamada pasa por el dueño. Se '
                             'tocan en la misma función y por eso se '
                             'declaran distintas: contrastar el historial '
                             'con un git que cualquiera puede mutar desde '
                             'otra línea no contrasta nada.'},
 'name': 'El historial se afirma a mano y nadie lo contrasta con git',
 'type': 'antipattern',
 'category': 'quality',
 'severity': 'medium',
 'enforcement': 'guard',
 'description': 'La documentacion afirma un hecho del historial —que la '
                'version v39.0 la introdujo el commit `00731c6` el '
                '2026-07-25— y ese hecho vive tambien en git, que es donde '
                'de verdad existe. Una de las dos copias se escribe a mano '
                'y ninguna se contrasta con la otra, asi que la de mano se '
                'queda atras sin que nada lo note.\n'
                '\n'
                'Es AP-05 aplicada al **historial**, y AP-47 en su forma '
                'menos visible: AP-47 persigue cifras escritas a mano '
                '—cuantas tools, cuantas normas— y una fecha o un hash de '
                'commit son la misma clase de dato derivable, solo que '
                'nadie los lee como una cifra.\n'
                '\n'
                'Medido en v40.7 sobre el changelog del manifiesto: **55 '
                'entradas, 31 con hash real, los 31 existen** —ninguno '
                'inventado— y **5 fechas contradecian al commit que '
                'citaban**. Cuatro por un dia; la de v39.0 por once. Esa '
                'entrada arrastra ademas un commit de fijado que corrigio '
                'el hash (`13bf9ca -> 00731c6`) y no toco la fecha: la '
                'correccion parcial es el modo de fallo tipico, porque '
                'quien corrige mira el dato que le fallo y no el que viaja '
                'con el.\n'
                '\n'
                'Detras hay un huevo y una gallina que conviene nombrar, '
                'porque es lo que empuja a escribir el dato a mano: la '
                'entrada tiene que citar el hash del commit que la '
                'contiene, y ese hash no existe hasta que el commit esta '
                'hecho. La salida fue un ritual de dos commits —`feat: vX` '
                'con `git: pending`, luego `docs: fijar hash`— que aparece '
                'ocho veces en las ultimas veinte entradas del historial y '
                'cuyo segundo paso depende de que alguien se acuerde. Una '
                'norma que solo prohibe no sirve aqui: hay que dar el '
                'comando que hace el paso, o se seguira haciendo a mano.',
 'signal': 'Un hash de commit, una fecha de release o un nombre de rama '
           'escritos en documentacion sin que ninguna tool los verifique '
           'contra el repositorio; un `pending` publicado en una version '
           'ya cerrada; una fecha que no coincide con la del commit que '
           'cita.',
 'prevention': 'Derivar el dato del repositorio y comprobarlo en una '
               'puerta. `vault_changelog_check --check --strict` contrasta '
               'hash, fecha —de autoria, `%as`, que un rebase no '
               'reescribe—, `pending` y orden. Y `--fijar-hash` convierte '
               'en comando el paso manual que originaba la divergencia.',
 'tools_enforcing': ['vault_changelog_check'],
 'tools_detecting': ['vault_changelog_check'],
 'introduced_version': 'v40.7',
 'revisado_en': '2026-10-09'}
