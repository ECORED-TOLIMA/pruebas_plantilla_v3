#!/usr/bin/env python3
"""Mapa de bloques de un artboard, ordenado por `y` de PÁGINA: es el documento de trabajo para
maquetar una pantalla larga (los temas de 7.000-10.000 px no se pueden leer de otra forma).

Por qué existe: ninguna de las dos herramientas que ya había sirve sola.

  · `xd_read.py` sabe el **fill y el radio** de cada rect, pero acumula mal el `transform` de los
    grupos anidados: en el Tema 1 de CF2 colocaba los tres paneles de una fila en (186,4180),
    (1010,4641) y (1414,4641) cuando los tres están en y=4180 y el último ni cabe en la tarjeta.
  · `gen_asset.py --lista` calcula el **bbox bueno** (matriz acumulada, y con el apaño para los
    trazados que llevan la posición dentro del `path`), pero no dice de qué color es nada.

Así que se cruzan por NOMBRE de nodo: posición y tamaño de `--lista`, color y radio de `xd_read`.
Y se marcan las tres cosas que deciden qué componente toca:

  [CAJON]  el rect lleva encima una pestaña de 25x8  -> es un `.cajon`, y sólo ésos
  [HOVER]  fila de rects del mismo tamaño donde UNO es de otro color -> es el estado `:hover`
  [GRUPO]  grupos con nombre y bbox: son los que se exportan enteros con `gen_asset.py --grupo`

Y con `--fotos` lista los `Enmascarar grupo`, que son las FOTOS de verdad: **el rect visible de una
foto es el bbox de su máscara, no el del nodo de imagen**. Exportando por el bbox de la máscara las
fotos del Tema 1 de CF2 salieron a 0,99 de correlación; por el bbox del nodo de imagen, la misma
foto daba 0,70. Ojo: **los nombres de los `Enmascarar grupo` se REPITEN dentro del artboard**
(`1119279` aparece dos veces), así que se exporta con `--rect <bbox de la máscara>`, no con
`--grupo <nombre>`.

Uso:  mapa_bloques.py <prefijo_artboard> [--desde Y] [--hasta Y] [--grupos] [--min-ancho N] [--todo]
      XD_DX / XD_DY del `mapa-artboards.json` (los pone `preparar_curso.py`).
"""
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def arg(nombre, defecto, tipo):
    return tipo(sys.argv[sys.argv.index(nombre) + 1]) if nombre in sys.argv else defecto


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    ab = sys.argv[1]
    desde, hasta = arg('--desde', -10**9, int), arg('--hasta', 10**9, int)
    minw = arg('--min-ancho', 0, int)

    def corre(script, extra):
        return subprocess.run([sys.executable, os.path.join(AQUI, script), ab] + extra,
                              capture_output=True, text=True, env=os.environ).stdout

    # 1. posición y tamaño buenos, y los grupos exportables
    #
    # ⚠️ `pos` es una LISTA, no un dict por nombre. El XD reutiliza el mismo nodo en varios sitios
    # —en el Tema 5 el `Rectángulo 456428` de la caja del badge sale TRES veces— y un
    # `setdefault(nombre, …)` se queda con la primera y **tira las demás sin avisar**: la ficha
    # daba un bloque donde el diseño tiene tres. Es la misma trampa del nombre repetido que ya
    # costaba una foto al exportar por `--grupo`. Se deduplica por (nombre, x, y), nunca por nombre.
    pos, grupos, vistos = [], [], set()
    for ln in corre('gen_asset.py', ['--lista']).splitlines():
        m = re.match(r'\s*(group|shape)\s+(\[MASK\]\s+)?(-?\d+)\s+(-?\d+)\s+(\d+)x(\d+)\s+(.+)', ln)
        if not m:
            continue
        tipo, mask, x, y, w, h, nom = m.groups()
        nom = nom.strip()
        if tipo == 'group':
            grupos.append((int(y), int(x), int(w), int(h), nom, bool(mask)))
        else:
            clave = (nom, int(x), int(y))
            if clave in vistos:
                continue
            vistos.add(clave)
            pos.append((nom, (int(x), int(y), int(w), int(h))))

    # 2. fill y radio por nombre de nodo
    #
    # ⚠️ `--con-tamano` DESCARTA los `Trazado …`: su bbox vive dentro del `path` y xd_read no lo
    # sabe calcular. Pero una caja de color dibujada como `path` es un BLOQUE, no decoración — en el
    # Tema 4 los dos avisos de trauma (1020x150 #DDEEFE y #F4EDFE) son `Trazado` y desaparecían de
    # la ficha, que es justo la que tiene que ser completa. Las posiciones ya las da
    # `gen_asset.py --lista`, así que el pase SIN el flag sólo aporta el fill y el radio que faltan.
    estilo = {}
    for extra in (['--con-tamano'], []):
        for ln in corre('xd_read.py', extra).splitlines():
            m = re.match(r'\[(\w+)\].*?·\s*(.+)$', ln)
            if m:
                estilo.setdefault(
                    m.group(2).strip(),
                    re.sub(r'^\[\w+\].*?(rect|path|circle|ellipse|line)\b', r'\1', ln)
                    .split('·')[0].strip())
            elif ln.startswith('[IMG]'):
                u = re.search(r'uid=(\w+)', ln)
                if u:
                    estilo.setdefault('uid=' + u.group(1), 'FOTO ' + u.group(1)[:10])

    # 3. pestañas de 25x8: el rect que empieza justo debajo es un `.cajon`
    pestanas = [(x, y) for nom, (x, y, w, h) in pos if (w, h) == (25, 8)]

    # Los `Trazado …` sin fill son la decoración del fondo (las ondas del hero, los degradados
    # concéntricos del pasteboard): con `--todo` se ven, pero estorban para leer la pantalla.
    filas = sorted(((y, x, w, h, nom) for nom, (x, y, w, h) in pos
                    if desde <= y <= hasta and w >= minw
                    and ('--todo' in sys.argv or estilo.get(nom))))

    # 3b. colapsar las PILAS DE SOMBRA. Una sombra difusa del XD no es un blur: son 15-20 copias de
    # la misma forma, del mismo fill, encogiéndose unos pocos px cada una. Contarlas como bloques
    # (lo que pasó al dejar entrar los `path`) llena la ficha de ruido y esconde los bloques reales.
    # Se reconocen por eso mismo: mismo fill y bbox a menos de 14 px del anterior. Se deja el mayor.
    if '--todo' not in sys.argv:
        limpias, pila = [], []

        def cierra():
            if pila:
                mayor = max(pila, key=lambda f: f[2] * f[3])
                limpias.append(mayor if len(pila) < 3 else (*mayor[:4], f'{mayor[4]} (x{len(pila)})'))

        for f in filas:
            if pila:
                p = pila[-1]
                pegada = (abs(f[0] - p[0]) <= 14 and abs(f[1] - p[1]) <= 14
                          and estilo.get(f[4]) == estilo.get(p[4]))
                if pegada:
                    pila.append(f)
                    continue
            cierra()
            pila = [f]
        cierra()
        filas = limpias

    # 4. filas de rects iguales con uno de otro color -> hover
    porfila = {}
    for y, x, w, h, nom in filas:
        porfila.setdefault((round(y / 12), w, h), []).append(nom)

    print(f'=== BLOQUES de {ab} (y de página {desde}..{hasta}) — {len(filas)} nodos')
    for y, x, w, h, nom in filas:
        marcas = []
        if any(abs(px - x) < 40 and 0 <= y - py <= 24 for px, py in pestanas):
            marcas.append('[CAJON]')
        hermanos = porfila.get((round(y / 12), w, h), [])  # misma fila, mismo tamaño
        if len(hermanos) >= 3:
            colores = {estilo.get(n, '') for n in hermanos}
            if len({c for c in colores if '#' in c}) > 1:
                marcas.append('[HOVER?]')
        print(f'  ({x:>5},{y:>6}) {w:>5}x{h:<5} {estilo.get(nom, ""):<58} {nom[:28]:<28} '
              f'{" ".join(marcas)}')

    if '--decoracion' in sys.argv:
        # Los nodos SIN fill indexado son los trazados decorativos: las ondas y bandas que se salen
        # del padding de la tarjeta. Filtrarlos del mapa (lo hacía `--todo`) escondía justo la
        # categoría de error más repetida — el bloque maquetado 40 px estrecho y sin su fondo.
        print('\n=== DECORACIÓN (trazados sin fill indexado) que SE SALE del contenido (x<186 o'
              ' derecha>1414)')
        for y, x, w, h, nom in sorted((y, x, w, h, nom) for nom, (x, y, w, h) in pos
                                      if not estilo.get(nom) and desde <= y <= hasta
                                      and w >= 200 and (x < 186 or x + w > 1414)):
            print(f'  ({x:>5},{y:>6}) {w:>5}x{h:<5} sobresale '
                  f'{"izq " + str(186 - x) if x < 186 else ""} '
                  f'{"der " + str(x + w - 1414) if x + w > 1414 else ""}   {nom}')

    if '--fotos' in sys.argv:
        print('\n=== FOTOS (bbox de la MÁSCARA: es el rect visible) — exportar con'
              ' `gen_asset.py <ab> --rect X Y W H --escala 2 --pag N salida.png`')
        vistas = set()
        for y, x, w, h, nom, mask in sorted(grupos):
            if not nom.startswith('Enmascarar grupo') or (x, y) in vistas:
                continue
            vistas.add((x, y))
            if desde <= y <= hasta:
                col = round(w / 1228 * 12)
                print(f'  --rect {x} {y} {w} {h}   ({w}x{h})  ->  col-lg-{col}'
                      f'{"  [banda/fondo]" if w > 1200 else ""}   {nom}')

    if '--grupos' in sys.argv:
        print(f'\n=== GRUPOS exportables (gen_asset.py --grupo "NOMBRE")')
        vistos = set()
        for y, x, w, h, nom, mask in sorted(grupos):
            if not (desde <= y <= hasta) or w < max(minw, 120) or nom in vistos:
                continue
            vistos.add(nom)
            print(f'  ({x:>5},{y:>6}) {w:>5}x{h:<5} {"MASK " if mask else "     "}{nom}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
