#!/usr/bin/env python3
"""Lee un artboard del XD y emite sus nodos hoja con posición y tamaño, ordenados por (y, x).

Los nodos cuelgan de `children[0].artboard.children`; hay que recorrer también
`group.children` acumulando `transform.tx/ty` (las coordenadas son negativas: lo que
importa son las DIFERENCIAS de x para deducir columnas, y el orden por y).

Emite:
  [T  ]  nodos de texto (`text.rawText`, con los saltos de línea como ' / ')
  [IMG]  nodos con relleno `pattern` (el raster está en `resources/<uid>`)
  [SHP]  el resto de formas, con tipo, tipo de relleno y color si es sólido

Uso: xd_read.py <prefijo_artboard> [--solo T|IMG|SHP] [--con-tamano] [--xd DIR]
"""
import glob
import json
import sys
import config as C

XDDIR = C.XDDIR


def find_agc(prefijo, xddir):
    hits = glob.glob(f'{xddir}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')
    if not hits:
        hits = glob.glob(f'{xddir}/artwork/*{prefijo}*/graphics/graphicContent.agc')
    return hits[0] if hits else None


def hexcolor(fill):
    c = (fill.get('color') or {}).get('value')
    if isinstance(c, dict):
        return '#%02X%02X%02X' % (c.get('r', 0), c.get('g', 0), c.get('b', 0))
    if isinstance(c, int):
        return f'#{c:06X}'
    return ''


def main():
    prefijo = sys.argv[1]
    xddir = sys.argv[sys.argv.index('--xd') + 1] if '--xd' in sys.argv else XDDIR
    solo = sys.argv[sys.argv.index('--solo') + 1].split(',') if '--solo' in sys.argv else None
    agc = find_agc(prefijo, xddir)
    if not agc:
        print('no existe el artboard', prefijo)
        sys.exit(1)

    nodos = []

    def walk(n, ox, oy, grupo=''):
        t = n.get('transform') or {}
        x, y = ox + t.get('tx', 0), oy + t.get('ty', 0)
        if 'group' in n:
            nom = n.get('name') or ''
            mask = 'MASK' if ((n.get('meta') or {}).get('ux') or {}).get('clipPathResources') else ''
            for c in n['group'].get('children', []):
                walk(c, x, y, f'{grupo}/{nom}{"[" + mask + "]" if mask else ""}')
            return
        shape = n.get('shape') or {}
        w, h = shape.get('width'), shape.get('height')
        style = n.get('style') or {}
        fill = style.get('fill') or {}
        texto = n.get('text')
        if texto and texto.get('rawText'):
            f = style.get('font') or {}
            fr = texto.get('frame') or {}
            info = (f'{f.get("postscriptName", "?")} {f.get("size", "?")}px '
                    f'frameW={fr.get("width")} :: {texto["rawText"].replace(chr(10), " / ")}')
            nodos.append(('T', x, y, w, h, info, grupo))
        elif fill.get('type') == 'pattern':
            ux = (((fill.get('pattern') or {}).get('meta') or {}).get('ux') or {})
            info = (f'uid={ux.get("uid")} scale={ux.get("scale")} '
                    f'flipX={ux.get("flipX")} flipY={ux.get("flipY")} '
                    f'offset=({ux.get("offsetX")},{ux.get("offsetY")})')
            nodos.append(('IMG', x, y, w, h, info, grupo))
        elif 'shape' in n:
            st = style.get('stroke') or {}
            extra = ''
            if st.get('type') and st.get('type') != 'none':
                extra = f' stroke={hexcolor(st)}/{st.get("width")}/{st.get("align", "center")}'
            r = shape.get('r')
            info = (f'{shape.get("type", "")} fill={fill.get("type")}'
                    f'{" " + hexcolor(fill) if fill.get("type") == "solid" else ""}'
                    f'{f" r={r}" if r else ""}{extra} · {n.get("name", "")}')
            nodos.append(('SHP', x, y, w, h, info, grupo))

    d = json.load(open(agc))
    # El `.agc` del PASTEBOARD no lleva el envoltorio `children[0].artboard`: los nodos cuelgan de
    # `children` directamente. Ahí viven los estados ocultos de sliders y acordeones (y sus fotos),
    # que son la mitad del contenido de una pantalla con carrusel.
    hijos = d.get('children') or []
    if hijos and 'artboard' in hijos[0]:
        hijos = hijos[0]['artboard'].get('children', [])
    for c in hijos:
        walk(c, 0, 0)

    nodos.sort(key=lambda n: (round(n[2]), round(n[1])))
    con_tam = '--con-tamano' in sys.argv
    for tipo, x, y, w, h, info, grupo in nodos:
        if solo and tipo not in solo:
            continue
        if con_tam and w is None:
            continue
        ws = f'{w:.0f}' if w is not None else '-'
        hs = f'{h:.0f}' if h is not None else '-'
        print(f'[{tipo:3}] x={x:8.0f} y={y:8.0f} {ws:>5}x{hs:<5} {info[:150]}')
    print(f'--- {len(nodos)} nodos hoja en {agc.split("/")[-3]}', file=sys.stderr)


main()
