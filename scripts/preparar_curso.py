#!/usr/bin/env python3
"""Paso 0 de un entregable NUEVO, automatizado. Hace todo lo determinista de arrancar un curso, que
en CF1 llevó un buen rato a mano:

  1. MAPA artboard -> pantalla -> página -> XD_DX/XD_DY, leído del `manifest` del XD
     (`uxdesign#bounds`: DX = -x, DY = -y). No hay que medir nada ni usar `offsets.py`.
  2. CACHÉ del PDF a 144 dpi, una página por pantalla, en `/tmp/xd-pdf-144dpi/<ENTREGABLE>/pN.png`
     (va POR CURSO: con una común, las correlaciones de otro curso salen sin sentido).
  3. TEXTO de los DOCX (`_DI` y `_AD`) volcado a `docs/`.
  4. INVENTARIO de cada artboard (`inventario_xd.py`) volcado a `docs/inventario-<tema>.txt`:
     colores+radios por par, máscaras con radio, pestañas de 25x8, señal de tarjeta hover y
     degradados no horizontales.

Uso:  preparar_curso.py
"""
import glob
import json
import os
import re
import subprocess
import sys

import config as C

RAIZ = C.ENTREGABLE
DOCS = os.path.join(RAIZ, 'docs')
os.makedirs(DOCS, exist_ok=True)
C.descomprimir()


def mapa():
    m = json.load(open(os.path.join(C.XDDIR, 'manifest')))
    filas = []

    def walk(n):
        for c in n.get('children', []):
            b = c.get('uxdesign#bounds')
            if b and c.get('path', '').startswith('artboard-'):
                filas.append({'nombre': c['name'], 'id': c['path'][9:17],
                              'dx': round(-b['x']), 'dy': round(-b['y']),
                              'w': round(b['width']), 'h': round(b['height'])})
            walk(c)
    walk(m)
    filas.sort(key=lambda f: (round(f['dy'] / 100), -f['dx']))
    for i, f in enumerate(filas, 1):
        f['pag'] = i

    # El orden por coordenadas ACIERTA POR CASUALIDAD: en CF2 dejaba «Sintesis – PDF» en la página 1
    # y la portada en la 3. El ALTO sí es una huella fiable — el PDF se exporta artboard a artboard,
    # así que cada página mide exactamente lo que su artboard. Si los altos son únicos (±2 pt), el
    # emparejamiento por alto MANDA sobre el de coordenadas.
    try:
        alto_pag = {}
        for ln in subprocess.run(['pdfinfo', '-f', '1', '-l', '999', C.PDF],
                                 capture_output=True, text=True).stdout.splitlines():
            mm = re.match(r'Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+)', ln)
            if mm:
                alto_pag.setdefault(round(float(mm.group(3))), []).append(int(mm.group(1)))
        if alto_pag:
            emparejadas = {}
            for f in filas:
                cand = [p for h, ps in alto_pag.items() if abs(h - f['h']) <= 2 for p in ps]
                if len(cand) == 1:
                    emparejadas[f['nombre']] = cand[0]
            # El emparejamiento por alto NO es todo-o-nada. Un solo artboard cuyo alto se movió
            # después de exportar el PDF (CF1: Tema-3 mide 13487 y su página 13617, 130 pt de
            # diferencia) tiraba a la basura los otros 10 que sí habían casado exacto y único, y
            # se volvía SILENCIOSAMENTE al orden por coordenadas -> Portada en la pág. 4 y
            # Sintesis en la 1. Lo que sobra se resuelve por ELIMINACIÓN: si queda un solo
            # artboard sin página y una sola página sin artboard, esa es su página.
            libres = [f for f in filas if f['nombre'] not in emparejadas]
            usadas = set(emparejadas.values())
            sin_usar = [p for ps in alto_pag.values() for p in ps if p not in usadas]
            if len(libres) == 1 and len(sin_usar) == 1:
                emparejadas[libres[0]['nombre']] = sin_usar[0]
                print(f'  (por ELIMINACIÓN: «{libres[0]["nombre"]}» -> página {sin_usar[0]}; '
                      f'alto {libres[0]["h"]} vs página {sin_usar[0]}, no casaba por ±2 pt)')
            if len(emparejadas) == len(filas) and len(set(emparejadas.values())) == len(filas):
                for f in filas:
                    f['pag'] = emparejadas[f['nombre']]
                filas.sort(key=lambda f: f['pag'])
                print('  (páginas emparejadas por ALTO contra el PDF, no por coordenadas)')
            else:
                print(f'  ⚠️ NO se pudo emparejar por alto: {len(emparejadas)}/{len(filas)} '
                      f'artboards con página única. Se cae al orden por COORDENADAS, que suele '
                      f'estar mal -> confirmar a mano antes de medir nada.')
    except Exception as e:                                        # noqa: BLE001
        print('  (no se pudo emparejar por alto:', e, ')')
    return filas


def main():
    filas = mapa()
    print('=== 1. MAPA artboard -> pantalla -> página -> offsets (del manifest del XD)')
    print(f'{"pág":>4} {"artboard":10} {"nombre":22} {"XD_DX":>7} {"XD_DY":>7}  alto')
    for f in filas:
        print(f'{f["pag"]:>4} {f["id"]:10} {f["nombre"][:22]:22} {f["dx"]:>7} {f["dy"]:>7}  {f["h"]}')
    json.dump(filas, open(f'{DOCS}/mapa-artboards.json', 'w'), indent=1, ensure_ascii=False)
    print(f'  -> {DOCS}/mapa-artboards.json')
    print('  ⚠️ si arriba NO dice «emparejadas por ALTO», el orden página↔artboard sale de las '
          'coordenadas y hay que confirmarlo leyendo el h1 de cada artboard antes de fiarse.')

    print('\n=== 2. caché del PDF a 144 dpi')
    os.makedirs(C.CACHE_PDF, exist_ok=True)
    for f in filas:
        dst = f'{C.CACHE_PDF}/p{f["pag"]}.png'
        if os.path.exists(dst):
            continue
        subprocess.run(['pdftoppm', '-png', '-r', '144', '-f', str(f['pag']), '-l', str(f['pag']),
                        C.PDF, f'{C.CACHE_PDF}/x'], check=True)
        hit = sorted(glob.glob(f'{C.CACHE_PDF}/x-*.png'))
        if hit:
            os.rename(hit[0], dst)
    print(f'  {len(glob.glob(C.CACHE_PDF + "/p*.png"))} páginas en {C.CACHE_PDF}')

    print('\n=== 3. texto de los DOCX')
    for suf in ('_DI.docx', '_AD.docx'):
        try:
            d = C.uno_docx(suf)
        except SystemExit:
            print(f'  (no hay {suf})')
            continue
        dst = f'{DOCS}/{suf[1:3].lower()}.txt'
        out = subprocess.run([sys.executable, f'{C.SCRIPTS}/docx_text.py', d],
                             capture_output=True, text=True).stdout
        open(dst, 'w').write(out)
        print(f'  {os.path.basename(d)} -> {dst} ({len(out.splitlines())} líneas)')

    print('\n=== 4. inventario de cada artboard')
    for f in filas:
        if re.search(r'tablet|m[oó]vil', f['nombre'], re.I):
            continue
        env = dict(os.environ, XD_DX=str(f['dx']), XD_DY=str(f['dy']))
        out = subprocess.run([sys.executable, f'{C.SCRIPTS}/inventario_xd.py', f['id']],
                             capture_output=True, text=True, env=env).stdout
        dst = f'{DOCS}/inventario-{f["nombre"].replace(" ", "-").replace("/", "-")}.txt'
        open(dst, 'w').write(out)
        # contar SÓLO dentro de la sección 3, no en todo el volcado
        sec3 = out.split('=== 3.')[1].split('=== 4')[0] if '=== 3.' in out else ''
        pest = len([l for l in sec3.splitlines() if l.startswith('  (')])
        hover = 'SÍ' if 'ESTADO HOVER' in out else 'no'
        print(f'  {f["nombre"][:22]:22} -> {os.path.basename(dst):42} pestañas 25x8={pest:2} hover={hover}')

    diccionario()

    print('\n=== SIGUIENTE PASO')
    print('  Maquetar pantalla por pantalla con el inventario delante: el color Y el radio de cada')
    print('  bloque salen de la sección 1, las fotos redondeadas de la 2, los `.cajon` de la 3 y las')
    print('  tarjetas hover de la 4. Al cerrar cada tema: verificar_maqueta.py + los dos pushes.')


def diccionario():
    """Imprime el diccionario GLOBAL de errores recurrentes: se repasa entero en cada curso nuevo."""
    import json as _json
    ruta = os.path.join(C.SCRIPTS, 'errores_recurrentes.json')
    if not os.path.exists(ruta):
        return
    d = _json.load(open(ruta))
    print('\n=== 5. DICCIONARIO GLOBAL DE ERRORES RECURRENTES '
          f'({len(d["errores"])} entradas) — se repasa ENTERO, no por curso')
    for e in d['errores']:
        auto = '  [check automático]' if e.get('check') else ''
        print(f'\n  ── {e["veces"]}x  {e["id"]}{auto}')
        print(f'     síntoma: {e["sintoma"]}')
        print(f'     regla:   {e["regla"]}')
        print(f'     detecta: {e["detecta"]}')


if __name__ == '__main__':
    main()
