#!/usr/bin/env python3
"""Renderiza un fondo compuesto respetando los MODOS DE FUSIÓN, capa por capa.

Por qué existe: el panel del hero de este curso es un degradado CLARO (lila → azul) con dos
texturas encima, una en `multiply` (opacidad 0.6) y otra en `soft-light` (0.7). Eso es lo que le
da el azul profundo con magenta y las líneas diagonales del diseño. Dos intentos fallaron:

1. Ignorar los `blendMode` (lo que hace `xd_export.py`): el panel sale pálido y sin líneas.
2. Emitir `mix-blend-mode` en el SVG: al rasterizar el SVG dentro de un `<img>` sobre fondo
   transparente, Chrome funde contra la transparencia y la textura desaparece.

Lo que sí funciona: renderizar **cada hijo directo del grupo por separado** con el mismo bbox y
componerlos en PIL, que aplica `multiply` y `soft-light` de verdad. El resultado se verifica
contra el PDF con `comparar.py`.

Uso: gen_fondo.py <artboard> <grupo> <X> <Y> <W> <H> <salida.png> [--pag N] [--escala 2]
"""
import json
import os
import sys

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import gen_asset as G  # noqa: E402

C.pipeline()
import xd_export as X  # noqa: E402


def soft_light(base, capa):
    """`soft-light` de CSS/SVG (fórmula del W3C), en flotante 0..1."""
    import numpy as np
    b = np.asarray(base).astype(float) / 255
    s = np.asarray(capa).astype(float) / 255
    d = np.where(b <= 0.25, ((16 * b - 12) * b + 4) * b, np.sqrt(b))
    out = np.where(s <= 0.5,
                   b - (1 - 2 * s) * b * (1 - b),
                   b + (2 * s - 1) * (d - b))
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype('uint8'))


def main():
    prefijo, nombre = sys.argv[1], sys.argv[2]
    px, py, pw, ph = (float(v) for v in sys.argv[3:7])
    salida = sys.argv[7]
    escala = float(sys.argv[sys.argv.index('--escala') + 1]) if '--escala' in sys.argv else 1

    nodos = G.cargar(prefijo)
    import xd_patches
    xd_patches.apply()

    r = G.buscar_grupo(nodos, nombre)
    if not r:
        raise SystemExit(f'no encontré el grupo {nombre!r}')
    grupo, m = r
    mg = X.mat_mul(m, X.node_transform(grupo))
    bbox = (px - G.DX, py - G.DY, px - G.DX + pw, py - G.DY + ph)
    W, H = round(pw * escala), round(ph * escala)

    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for hijo in grupo.get('group', {}).get('children', []):
        st = hijo.get('style') or {}
        bm = st.get('blendMode') or 'normal'
        # `--como nombre=modo` fuerza el modo de una capa. Hace falta porque el `soft-light` que
        # declara el XD no reproduce el resultado del PDF: la ilustración oscura del fondo se ve
        # como si fuera `normal`, y con soft-light sale lavada.
        for i, arg in enumerate(sys.argv):
            if arg == '--como' and sys.argv[i + 1].split('=')[0] in (hijo.get('name') or ''):
                bm = sys.argv[i + 1].split('=')[1]
        op = st.get('opacity', 1.0)
        # cada hijo, solo, con el MISMO bbox -> queda ya en su sitio
        hijo_sin_estilo = dict(hijo)
        hijo_sin_estilo['style'] = {k: v for k, v in st.items()
                                    if k not in ('blendMode', 'opacity')}
        svg = X.render_svg(hijo_sin_estilo, bbox, X.mat_mul(mg, X.node_transform(hijo)),
                           resources_dir=C.RES)
        tmp = salida + f'.capa.png'
        G.rasterizar(svg, tmp, pw, ph, escala)
        capa = Image.open(tmp).convert('RGBA')
        os.remove(tmp)

        if bm == 'normal':
            if op < 0.999:
                a = capa.getchannel('A').point(lambda v: round(v * op))
                capa.putalpha(a)
            base.alpha_composite(capa)
        else:
            # los modos de fusión se aplican SOBRE lo que ya hay, sólo donde la capa pinta
            fondo = base.convert('RGB')
            arriba = Image.alpha_composite(base, capa).convert('RGB')
            mezcla = (ImageChops.multiply(fondo, arriba) if bm == 'multiply'
                      else soft_light(fondo, arriba) if bm == 'soft-light'
                      else ImageChops.screen(fondo, arriba) if bm == 'screen'
                      else arriba)
            if op < 0.999:
                mezcla = Image.blend(fondo, mezcla, op)
            base = Image.merge('RGBA', (*mezcla.split(), base.getchannel('A')))
        print(f'  capa {hijo.get("name","")[:28]:30} blend={bm:11} op={op}')

    base.save(salida)
    print(f'{base.size} -> {salida}')
    if '--pag' in sys.argv:
        G.verificar(sys.argv[sys.argv.index('--pag') + 1], round(px), round(py),
                    round(pw), round(ph), salida)


main()
