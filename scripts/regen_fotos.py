#!/usr/bin/env python3
"""Regenera de una pasada TODAS las fotos enmascaradas de un tema y las verifica contra el PDF.

Por qué: el pipeline compartido **no aplica las máscaras de grupo**, así que cada foto sale sin
recortar y con el encuadre equivocado. El rect que se ve es el **bbox de la máscara**, no el del
nodo (una foto puede decir `645x428 @113` y verse `500x423 @186`).

Qué hace, por cada grupo `SHAPE_MASK` que contenga un relleno `pattern`:
  1. calcula el rect visible (bbox de la máscara) en coordenadas de página,
  2. lo renderiza con `gen_asset.py` (que aplica máscara, flip, scale y offset),
  3. lo compara por correlación contra el mismo rectángulo de la página del PDF,
  4. lo instala como `fN.png` (numeración propia, en orden visual) **sin sobreescribir** los
     assets del pipeline, y anota la correspondencia en `manifest.txt`.

Regla de la numeración: NO se reutiliza el número del pipeline. Emparejar por correlación con
los assets ya existentes da colisiones y ya provocó un incidente de sobreescritura.

Uso: regen_fotos.py <artboard> <pagina_pdf> <carpeta_destino> [--min 0.88] [--desde N]
"""
import glob
import json
import os
import re
import subprocess
import sys

import config as C  # noqa: E402
C.pipeline()
import xd_export as X  # noqa: E402

XDDIR = C.XDDIR
SCRIPTS = C.SCRIPTS


def bbox_mascara(nodo, m):
    cp = ((nodo.get('meta') or {}).get('ux') or {}).get('clipPathResources')
    if not (cp and cp.get('children')):
        return None
    forma = cp['children'][0]
    lb = X.shape_local_bbox(forma.get('shape') or {})
    if not lb:
        return None
    mm = X.mat_mul(X.mat_mul(m, X.node_transform(nodo)), X.node_transform(forma))
    return X.transform_bbox(mm, lb)


def tiene_pattern(nodo):
    if ((nodo.get('style') or {}).get('fill') or {}).get('type') == 'pattern':
        return True
    for c in (nodo.get('group') or {}).get('children', []):
        if tiene_pattern(c):
            return True
    return False


def main():
    prefijo, pagina, destino = sys.argv[1], sys.argv[2], sys.argv[3]
    minimo = float(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 0.88
    desde = int(sys.argv[sys.argv.index('--desde') + 1]) if '--desde' in sys.argv else 1
    dx = float(os.environ['XD_DX'])
    dy = float(os.environ['XD_DY'])

    agc = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')[0]
    nodos = json.load(open(agc))['children'][0]['artboard']['children']

    fotos = []

    def walk(ns, m):
        for n in ns:
            mm = X.mat_mul(m, X.node_transform(n))
            bb = bbox_mascara(n, m)
            if bb and tiene_pattern(n):
                fotos.append((round(bb[1] + dy), round(bb[0] + dx),
                              round(bb[2] - bb[0]), round(bb[3] - bb[1]), n.get('name')))
                continue          # una foto enmascarada es una unidad: no se entra
            if n.get('type') == 'group':
                walk((n.get('group') or {}).get('children', []), mm)

    walk(nodos, X.IDENTITY)
    fotos.sort()
    print(f'{len(fotos)} fotos enmascaradas en {prefijo}')

    lineas = []
    for i, (y, x, w, h, nombre) in enumerate(fotos, desde):
        salida = os.path.join(destino, f'f{i}.png')
        subprocess.run(['python3', f'{SCRIPTS}/gen_asset.py', prefijo, '--grupo', nombre,
                        '--en', str(x), str(y), salida],
                       check=True, capture_output=True, env={**os.environ})
        r = subprocess.run(['python3', f'{SCRIPTS}/comparar.py', pagina,
                            str(x), str(y), str(w), str(h), salida],
                           capture_output=True, text=True)
        m = re.search(r'correlacion ([\d.]+)', r.stdout)
        corr = float(m.group(1)) if m else 0
        # Si el render del grupo no da el encuadre, se AJUSTA NUMÉRICAMENTE con `fit_foto.py`
        # (búsqueda de escala/offset por correlación sobre el raster crudo). La escala real
        # suele ser 1.00-1.06x el `cover` sobre el rect de la máscara.
        if corr < minimo:
            f = subprocess.run(['python3', f'{SCRIPTS}/fit_foto.py', prefijo, pagina,
                                str(x), str(y), str(w), str(h), salida, '--grupo', nombre],
                               capture_output=True, text=True)
            fm = re.search(r'corr=([\d.]+)', f.stdout)
            if fm and float(fm.group(1)) > corr:
                r = subprocess.run(['python3', f'{SCRIPTS}/comparar.py', pagina,
                                    str(x), str(y), str(w), str(h), salida],
                                   capture_output=True, text=True)
                m2 = re.search(r'correlacion ([\d.]+)', r.stdout)
                nueva = float(m2.group(1)) if m2 else 0
                esc = re.search(r'escala=[\d.]+ \(([\d.]+)x\)', f.stdout)
                print(f'    · ajustada por correlación: {corr:.3f} -> {nueva:.3f}'
                      + (f'  (escala {esc.group(1)}x el cover)' if esc else ''))
                corr = nueva
        marca = 'OK ' if corr >= minimo else '⚠️ '
        print(f'{marca} f{i}.png  ({x},{y}) {w}x{h}  corr={corr:.3f}  {nombre}')
        lineas.append(f'f{i}.png\tPNG (regenerado)\t{nombre} - rect visible {w}x{h} en ({x},{y}), corr={corr:.3f}')

    with open(os.path.join(destino, 'manifest.txt'), 'a') as f:
        f.write('\n'.join(lineas) + '\n')


main()
