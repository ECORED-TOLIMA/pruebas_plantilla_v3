#!/usr/bin/env python3
"""Barrido OBLIGATORIO antes de maquetar una pantalla: saca de un artboard todo lo que el skill
manda comprobar a mano, de una pasada.

Nació de los hallazgos de CF1: cada error repetido («el color no es el del XD», «esa caja va
cuadrada», «esa foto va redondeada», «eso es una tarjeta hover», «eso es un cajón») venía de no
haber hecho el barrido. Aquí está hecho.

  inventario_xd.py <prefijo_artboard> [--pag N]

Saca, en este orden:
  1. RECTS agrupados por (fill, r)  -> el color Y el radio exactos de cada bloque. Una clase por
     par, no por color. Los que salen con `r=None` van CUADRADOS del todo.
  2. MÁSCARAS de foto con su radio  -> la foto lleva ese `border-radius`, o va cuadrada si no tiene.
  3. PESTAÑAS de 25x8              -> las cajas que son `.cajon` del kit, y sólo ésas.
  4. SEÑAL DE TARJETA HOVER        -> filas donde UNA tarjeta (o su icono) está pintada de otro
     color: eso es el estado `:hover`, no una tarjeta distinta. Y los iconos «con over» que estén
     en el pasteboard.
  5. DEGRADADOS                    -> avisa si alguno no es horizontal, porque `xd_export` los
     ponía todos a 0,0->1,0 (parche 6 de xd_patches).
"""
import glob
import json
import sys
from collections import defaultdict

import config as C

DX, DY = C.DX, C.DY


def hexa(v):
    return '#%02X%02X%02X' % (v.get('r', 0), v.get('g', 0), v.get('b', 0))


def recorrer(nodos, m=(1, 0, 0, 1, 0, 0), prof=0):
    for n in nodos:
        t = n.get('transform') or {}
        a, b, c, d = t.get('a', 1), t.get('b', 0), t.get('c', 0), t.get('d', 1)
        tx, ty = t.get('tx', 0), t.get('ty', 0)
        mm = (m[0] * a + m[2] * b, m[1] * a + m[3] * b,
              m[0] * c + m[2] * d, m[1] * c + m[3] * d,
              m[0] * tx + m[2] * ty + m[4], m[1] * tx + m[3] * ty + m[5])
        yield n, mm, prof
        if n.get('type') == 'group':
            yield from recorrer(n['group'].get('children', []), mm, prof + 1)


def cargar(pref):
    d = json.load(open(C.agc(pref)))
    hijos = d['children'][0]['artboard']['children'] if pref != 'pasteboard' else d.get('children', [])
    return hijos


def main():
    pref = sys.argv[1]
    hijos = cargar(pref)
    rects = defaultdict(list)
    mascaras, pestanas, degradados = [], [], []

    for n, mm, _ in recorrer(hijos):
        nombre = (n.get('name') or '').strip()
        est = n.get('style') or {}
        relleno = est.get('fill') or {}
        px, py = mm[4] + DX, mm[5] + DY

        if n.get('type') == 'group':
            ux = (n.get('meta') or {}).get('ux') or {}
            cp = ux.get('clipPathResources')
            if cp:
                sh = cp['children'][0].get('shape', {})
                if sh.get('type') == 'rect' and sh.get('width', 0) >= 150:
                    mascaras.append((nombre, int(sh['width']), int(sh['height']), sh.get('r')))
            continue

        sh = (n.get('shape') or {})
        w, h = sh.get('width'), sh.get('height')
        if relleno.get('type') == 'solid' and w and h:
            col = hexa(relleno['color']['value'])
            r = sh.get('r')
            rr = tuple(r) if isinstance(r, list) else None
            if int(w) == 25 and int(h) == 8:
                pestanas.append((round(px), round(py), col, nombre))
            elif w >= 60 and h >= 24:
                rects[(col, rr)].append((nombre, int(w), int(h), round(px), round(py)))
        if relleno.get('type') == 'gradient':
            g = relleno['gradient']
            x1, y1 = g.get('x1'), g.get('y1')
            if x1 is not None and (abs(y1 or 0) > 0.01 or x1 < 0 or x1 > 1):
                degradados.append((nombre, x1, y1, g.get('x2'), g.get('y2')))

    print(f'=== 1. RECTS por (fill, r) — una clase por PAR, no por color')
    def orden(k):
        (col, r), v = k
        return (-len(v), col, r if r is not None else ())
    for (col, r), v in sorted(rects.items(), key=orden):
        radio = 'SIN r (CUADRADO)' if r is None else f'r={list(r)}'
        ej = ', '.join(f'{n.split()[-1]} {w}x{h}@({x},{y})' for n, w, h, x, y in v[:3])
        print(f'  {col}  {radio:22} n={len(v):3}  {ej}')

    print(f'\n=== 2. MÁSCARAS de foto (el radio va al <img>)')
    for nm, w, h, r in mascaras:
        print(f'  {nm[:34]:36} {w}x{h:<5} {"CUADRADA" if not r else f"r={r}"}')

    print(f'\n=== 3. PESTAÑAS 25x8 -> esas cajas son .cajon, y sólo ésas ({len(pestanas)})')
    for x, y, col, nm in sorted(pestanas, key=lambda p: p[1]):
        print(f'  ({x},{y}) {col}  {nm}')

    print(f'\n=== 4. SEÑAL DE TARJETA HOVER (una tarjeta/icono de otro color en la fila)')
    filas = defaultdict(list)
    for (col, r), v in rects.items():
        for nm, w, h, x, y in v:
            filas[(round(y / 10) * 10, w, h)].append(col)
    hallado = False
    for (y, w, h), cols in sorted(filas.items()):
        if len(cols) >= 3 and len(set(cols)) > 1:
            from collections import Counter
            cc = Counter(cols)
            raro = [c for c, k in cc.items() if k == min(cc.values())]
            print(f'  y≈{y} {w}x{h}: {dict(cc)} -> el {raro} es el ESTADO HOVER, no otra tarjeta')
            hallado = True
    if not hallado:
        print('  (ninguna)')

    print('\n=== 4b. RÓTULOS DE COMPONENTE en el pasteboard (el XD los nombra ahí)')
    try:
        pb = cargar('pasteboard')
        rot = []
        for n, mm, _ in recorrer(pb):
            if n.get('type') == 'text':
                raw = ((n.get('text') or {}).get('rawText') or '').strip()
                if raw and raw == raw.upper() and 3 < len(raw) < 40 and any(c.isalpha() for c in raw):
                    rot.append((round(mm[5]), round(mm[4]), raw))
        vistos = set()
        for y, x, t in sorted(rot):
            if t in vistos:
                continue
            vistos.add(t)
            print(f'  «{t}» en ({x},{y}) -> los textos del componente están DEBAJO de este rótulo')
        if not vistos:
            print('  (ninguno)')
    except Exception as e:                                    # noqa: BLE001
        print('  (no se pudo leer el pasteboard:', e, ')')

    print(f'\n=== 5. DEGRADADOS no horizontales ({len(degradados)}) — ojo al parche 6')
    for nm, x1, y1, x2, y2 in degradados[:8]:
        print(f'  {nm[:30]:32} ({x1:.3f},{y1:.3f}) -> ({x2:.3f},{y2:.3f})')


if __name__ == '__main__':
    main()
