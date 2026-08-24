#!/usr/bin/env python3
"""Ficha numérica de cada bloque de una pantalla, para TRANSCRIBIRLA en el Pug en vez de
interpretarla.

Existe porque el orden inverso —escribir el Pug desde la impresión visual y comprobar después— deja
fuera todo lo que no estaba en la impresión: la banda decorativa que se sale del padding, el alto
fijo de una tarjeta, el ancho real de la columna de texto. Eso no se arregla mirando mejor.

De cada bloque saca, cruzando el XD con el render del artboard:

  rect     x, y, ancho, alto del rect del XD (o de la franja del render si no hay rect)
  fill     el color del nodo, no el muestreado
  radio    el `r=[...]` del rect, esquina por esquina
  padding  medido en el render: del borde del bloque a la primera tinta, en los cuatro lados
  texto    ancho de la columna de texto dentro del bloque -> es lo que decide cómo rompe la línea
  col      la columna de Bootstrap que le toca: round(ancho / 1228 * 12)
  sangra   cuánto se sale del área de contenido (186..1414) por cada lado

Uso:  spec_pantalla.py <prefijo_artboard> <pagina> [--desde Y] [--hasta Y]
      XD_DX / XD_DY del `mapa-artboards.json`.
"""
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

import config as C

Image.MAX_IMAGE_PIXELS = None
AQUI = os.path.dirname(os.path.abspath(__file__))
CONTENIDO = (186, 1414)          # el área útil dentro de la tarjeta blanca


def arg(nombre, defecto, tipo):
    return tipo(sys.argv[sys.argv.index(nombre) + 1]) if nombre in sys.argv else defecto


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    ab, pagina = sys.argv[1], int(sys.argv[2])
    desde, hasta = arg('--desde', 0, int), arg('--hasta', 10**9, int)

    # 1. los rects del XD: posición, tamaño, fill y radio buenos
    salida = subprocess.run([sys.executable, os.path.join(AQUI, 'mapa_bloques.py'), ab,
                             '--desde', str(desde), '--hasta', str(hasta), '--min-ancho', '80'],
                            capture_output=True, text=True, env=os.environ).stdout
    bloques = []
    for ln in salida.splitlines():
        m = re.match(r'\s*\((\s*-?\d+),(\s*-?\d+)\)\s+(\d+)x(\d+)\s+(.*?)\s{2,}(\S.*?)\s*$', ln)
        if not m:
            continue
        x, y, w, h, est, nom = (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                int(m.group(4)), m.group(5).strip(), m.group(6).strip())
        fill = (re.search(r'#[0-9A-F]{6}', est) or [None])[0] if '#' in est else None
        radio = (re.search(r'r=(\[[^\]]*\]|\d+)', est) or [None, None])[1] if 'r=' in est else 'sin'
        bloques.append(dict(x=x, y=y, w=w, h=h, fill=fill, radio=radio, nombre=nom))

    # 2. el render del artboard, para el padding y la columna de texto
    art = Image.open(f'{C.CACHE_PDF}/p{pagina}.png').convert('RGB')
    art = art.resize((1600, art.height // 2))
    arr = np.asarray(art).astype(int)

    def tinta(x, y, w, h, margen=0):
        """bbox de la tinta dentro del rect, relativo a su esquina: (izq, arr, der, abj, ancho)."""
        y0, y1 = max(0, y + margen), min(arr.shape[0], y + h - margen)
        x0, x1 = max(0, x + margen), min(arr.shape[1], x + w - margen)
        if y1 <= y0 or x1 <= x0:
            return None
        c = arr[y0:y1, x0:x1]
        fondo = np.median(c.reshape(-1, 3), axis=0)
        dif = np.abs(c - fondo).sum(2) > 40
        if not dif.any():
            return None
        cols, fils = np.where(dif.any(0))[0], np.where(dif.any(1))[0]
        return (int(cols.min()), int(fils.min()), int(w - margen * 2 - cols.max() - 1),
                int(h - margen * 2 - fils.max() - 1), int(cols.max() - cols.min() + 1))

    print(f'=== FICHA DE BLOQUES · artboard {ab} · página {pagina} · y {desde}..{hasta}')
    print(f'{"y":>6} {"x":>5} {"ancho":>5} {"alto":>5} {"fill":>8} {"radio":>14} '
          f'{"padding i/a/d/b":>16} {"texto":>6} {"col":>4}  sangra')
    for b in bloques:
        t = tinta(b['x'], b['y'], b['w'], b['h'])
        pad = f"{t[0]}/{t[1]}/{t[2]}/{t[3]}" if t else '—'
        txt = t[4] if t else 0
        col = round(b['w'] / 1228 * 12)
        sangra = []
        if b['x'] < CONTENIDO[0]:
            sangra.append(f'izq {CONTENIDO[0] - b["x"]}')
        if b['x'] + b['w'] > CONTENIDO[1]:
            sangra.append(f'der {b["x"] + b["w"] - CONTENIDO[1]}')
        print(f'{b["y"]:>6} {b["x"]:>5} {b["w"]:>5} {b["h"]:>5} {str(b["fill"]):>8} '
              f'{str(b["radio"]):>14} {pad:>16} {txt:>6} {col:>4}  {" ".join(sangra)}')
    print(f'\n{len(bloques)} bloques. El Pug se escribe contra esta tabla: ancho -> col, alto -> '
          f'min-height si el XD lo fija, padding -> la clase p-N que dé esa medida, y `texto` es lo '
          f'que tiene que medir la columna para que la línea rompa igual.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
