#!/usr/bin/env python3
"""Renderiza un ASSET del XD que el pipeline no saca bien: un grupo entero o todo lo que cae
dentro de un rectángulo de la página. Es la herramienta de "exportar por grupo" del playbook.

Tres modos:

  gen_asset.py <artboard> --grupo "Enmascarar grupo 1119257" salida.png
  gen_asset.py <artboard> --rect X Y W H salida.png        # coords de PÁGINA (con dx/dy)
  gen_asset.py <artboard> --lista [--grupos|--imgs]        # qué hay, con su bbox de página

Reglas que hay que respetar (cada una salió de un fallo real):

- **La pertenencia a un rectángulo se decide con el BBOX del nodo trasladado por la matriz
  acumulada, NUNCA con `transform.tx/ty`**: hay trazados que llevan la posición dentro del
  propio `path` (`M -12436 -9511 …`) y su `tx/ty` apunta a miles de px de distancia.
- **Si un shape no tiene bbox calculable, se usa su posición del `transform`**: los adornos
  `compound` (p. ej. `Sustracción 105`) devuelven `None` en `shape_local_bbox` y cualquier
  filtro que descarte los nodos sin bbox los pierde (el panel queda "pelado").
- Los grupos con máscara se respetan como una unidad (no se entra a sus hijos): el recorte lo
  aplica `xd_patches`.
- `--sin-textos` deja fuera los nodos de texto (para los paneles de color con foto, donde el
  texto lo pone el HTML). Por defecto SÍ van (el mapa de la síntesis es 82 nodos con texto).
- Se rasteriza con **Chrome**, nunca con rsvg. Chrome headless sólo pinta ~(alto − 88) px de
  la ventana, así que se pide la ventana más alta y se recorta con PIL.
- La tipografía se **incrusta** (woff2 de `public/fonts/` en base64) o el texto sale en serif.

Los offsets dx/dy (XD → página) los da `offsets.py`; se pasan por `XD_DX`/`XD_DY` y por
`XD_AB=pasteboard` se lee el pasteboard (que NO tiene el envoltorio `children[0].artboard`).
"""
import base64
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
C.pipeline()
import xd_export as X  # noqa: E402
import xd_patches  # noqa: E402
import xd_patches as P  # noqa: E402

XDDIR = C.XDDIR
RES = C.RES
FUENTES = f'{C.ENTREGABLE}/public/fonts'
DX = float(os.environ.get('XD_DX', 0))
DY = float(os.environ.get('XD_DY', 0))


def cargar(prefijo):
    """Devuelve la lista de hijos raíz. El pasteboard no trae `children[0].artboard`."""
    if prefijo == 'pasteboard':
        agc = f'{XDDIR}/artwork/pasteboard/graphics/graphicContent.agc'
        return json.load(open(agc))['children']
    agc = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')[0]
    return json.load(open(agc))['children'][0]['artboard']['children']


def bbox_mascara(nodo, m):
    """El rect VISIBLE de un grupo enmascarado = el bbox de su máscara, no el del contenido.

    Regla clave: un nodo puede decir `1095x410 @x=252` y lo que se ve es `1040x517 @x=281`.
    La forma del recorte vive en `meta.ux.clipPathResources.children[0]` y está en el espacio
    LOCAL del grupo, así que hay que componerla con la matriz del grupo.
    """
    cp = ((nodo.get('meta') or {}).get('ux') or {}).get('clipPathResources')
    if not (cp and cp.get('children')):
        return None
    forma = cp['children'][0]
    lb = X.shape_local_bbox(forma.get('shape') or {})
    if not lb:
        return None
    mm = X.mat_mul(X.mat_mul(m, X.node_transform(nodo)), X.node_transform(forma))
    return X.transform_bbox(mm, lb)


def bbox_de(nodo, m):
    """Bbox ABSOLUTO (espacio del artboard) o None si no se puede calcular."""
    bm = bbox_mascara(nodo, m)
    if bm:
        return bm
    try:
        info, _, _ = X.analyze(nodo, m)
        if info and info.bbox:
            return info.bbox
    except Exception:
        pass
    shp = nodo.get('shape') or {}
    lb = X.shape_local_bbox(shp)
    mm = X.mat_mul(m, X.node_transform(nodo))
    if lb:
        return X.transform_bbox(mm, lb)
    return None


def hojas(nodos, m, sin_textos=False):
    """Nodos a dibujar: los grupos con máscara NO se abren (son una unidad)."""
    out = []
    for n in nodos:
        mm = X.mat_mul(m, X.node_transform(n))
        enmascarado = bool(((n.get('meta') or {}).get('ux') or {}).get('clipPathResources'))
        if n.get('type') == 'group' and not enmascarado:
            out += hojas(n.get('group', {}).get('children', []), mm, sin_textos)
            continue
        if sin_textos and n.get('type') == 'text':
            continue
        out.append((n, m, mm))
    return out


def posicion_fallback(mm):
    """Cuando no hay bbox: la traslación de la matriz acumulada (un punto, no una caja)."""
    return (mm[4], mm[5], mm[4], mm[5])


def buscar_grupo(nodos, nombre, m=X.IDENTITY, cerca=None):
    """Todos los nodos con ese nombre; si `cerca=(x,y)` (coords de página) devuelve el que
    tenga el bbox más próximo.

    **El MISMO nombre de grupo puede repetirse en un artboard** (`Enmascarar grupo 1119137`
    sale dos veces en el Tema 2, en dos subtemas distintos). Quedarse con el primero hace que
    la segunda foto salga con la imagen de la primera — fallo real, detectado porque la
    correlación cayó a 0.28 mientras las demás daban 0.99.
    """
    hits = []

    def rec(ns, mm):
        for n in ns:
            if n.get('name') == nombre:
                hits.append((n, mm))
            if n.get('type') == 'group':
                rec(n.get('group', {}).get('children', []), X.mat_mul(mm, X.node_transform(n)))

    rec(nodos, m)
    if not hits:
        return None
    if cerca and len(hits) > 1:
        def dist(par):
            bb = bbox_de(par[0], par[1])
            if not bb:
                return 1e9
            return abs(bb[0] + DX - cerca[0]) + abs(bb[1] + DY - cerca[1])
        hits.sort(key=dist)
    return hits[0]


def fuentes_css():
    css = []
    # Los woff2 del kit no se llaman igual en todos los entregables: en CF01 son
    # `Roboto-Regular.woff2` y aquí `roboto-400.woff2`. Si no se encuentra ninguno el texto sale
    # en SERIF (y la correlación se hunde por el fantasma del texto, no por las formas).
    for w, arch, alt in (('400', 'Roboto-Regular', 'roboto-400'),
                         ('500', 'Roboto-Medium', 'roboto-500'),
                         ('700', 'Roboto-Bold', 'roboto-700'),
                         ('900', 'Roboto-Black', 'roboto-900')):
        hits = ([h for h in glob.glob(f'{FUENTES}/**/{arch}*.woff2', recursive=True)]
                or [h for h in glob.glob(f'{FUENTES}/**/{alt}.woff2', recursive=True)])
        if not hits:
            continue
        b64 = base64.b64encode(open(hits[0], 'rb').read()).decode()
        # Roboto-Medium (500) se mapea a 700: el kit sólo carga 100/400/700/900 y el PDF
        # imprime esas líneas en negrita.
        peso = '700' if w == '500' else w
        css.append(f"@font-face{{font-family:Roboto;font-weight:{peso};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return ''.join(css)


def rasterizar(svg, salida, w, h, escala=1):
    """SVG -> PNG con Chrome. La ventana se pide 200px más alta y se recorta (bug de headless).

    Si `salida` acaba en `.svg` NO se rasteriza: se escribe el SVG tal cual. Un nodo vectorial
    (icono, infografía de línea) entregado en SVG se salta de golpe los tres sitios donde el
    rasterizado pierde información —`fill-rule`, la tipografía incrustada y los `blendMode`— y
    además escala sin pixelar. Es lo que hizo Manuel a mano con los 22 assets de la revisión del
    2026-07-30: sólo las FOTOS se quedan en PNG.
    """
    from PIL import Image
    tmp = tempfile.mkdtemp()
    svg = P.remapear_paleta(svg)   # identidad: el color del nodo se respeta tal cual
    # `--swap-color VIEJO NUEVO` (repetible): cambia UN color concreto en el SVG. Se usa SÓLO para
    # generar el estado «con over» de una tarjeta Over cuando el diseño no lo dibuja aparte: el XD
    # define el efecto como el intercambio del color del contenedor del icono
    # (#16D95E <-> #DBC2FA). No es un remapeo de paleta: es reproducir el estado que define el XD.
    for k, arg in enumerate(sys.argv):
        if arg == '--swap-color':
            a, b = sys.argv[k + 1], sys.argv[k + 2]
            ra, ga, ba = (int(a[i:i + 2], 16) for i in (0, 2, 4))
            rb, gb, bb = (int(b[i:i + 2], 16) for i in (0, 2, 4))
            svg = svg.replace(f'rgb({ra},{ga},{ba})', f'rgb({rb},{gb},{bb})')
    # las fuentes en base64 sólo hacen falta si hay texto: sin esto un icono entregado en SVG
    # cargaría ~300 KB de woff2 incrustado para nada.
    if '<text' in svg or not salida.endswith('.svg'):
        svg = svg.replace('>', '>' + f'<style>{fuentes_css()}</style>', 1)
    open(f'{tmp}/a.svg', 'w').write(svg)
    if salida.endswith('.svg'):
        open(salida, 'w').write(svg)
        return round(w * escala), round(h * escala)
    W, H = round(w * escala), round(h * escala)
    html = (f'<html><body style="margin:0;background:transparent">'
            f'<img src="a.svg" style="width:{W}px;height:{H}px"></body></html>')
    open(f'{tmp}/a.html', 'w').write(html)
    subprocess.run(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--hide-scrollbars', '--default-background-color=00000000',
                    '--virtual-time-budget=6000',
                    f'--window-size={W},{H + 200}',
                    f'--screenshot={tmp}/a.png', f'{tmp}/a.html'],
                   check=True, capture_output=True)
    im = Image.open(f'{tmp}/a.png').convert('RGBA').crop((0, 0, W, H))
    im.save(salida)
    return im.size


def verificar(pagina, x, y, w, h, salida, fondo=None):
    """Compara lo generado contra el mismo rectángulo del PDF y avisa si no cuadra.

    Está aquí para que sea IMPOSIBLE dar un asset por bueno sin comprobarlo: en CF1 la foto de
    la portada salió con su fondo de estudio (el diseño usa un recorte sobre una forma crema) y
    se colcó porque no se comparó. Ojo: si el rectángulo del PDF lleva ENCIMA texto u otros
    elementos que pone el HTML, la correlación baja aunque el asset sea correcto -> mirarlo.
    """
    cmd = ['python3', f'{os.path.dirname(os.path.abspath(__file__))}/comparar.py',
           str(pagina), str(x), str(y), str(w), str(h), salida]
    if fondo:
        cmd += ['--fondo', fondo]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r'correlacion ([\d.]+|nan)', r.stdout)
    if not m:
        print('   (no se pudo verificar:', r.stderr.strip()[:120], ')')
        return
    if m.group(1) == 'nan':
        print('   ⚠️  correlación nan: el render es de un solo color, revísalo')
        return
    c = float(m.group(1))
    print(f'   {"OK " if c >= 0.9 else "⚠️ "} correlación {c:.4f} contra la pág {pagina}'
          + ('' if c >= 0.9 else '  <- MIRARLO: o el asset está mal, o el PDF lleva encima algo del HTML'))


def main():
    prefijo = sys.argv[1]
    nodos = cargar(prefijo)
    xd_patches.apply()

    if '--lista' in sys.argv:
        solo_g = '--grupos' in sys.argv
        solo_i = '--imgs' in sys.argv

        def rec(ns, m, prof=0):
            for n in ns:
                mm = X.mat_mul(m, X.node_transform(n))
                bb = bbox_de(n, m)
                pos = (f'{bb[0] + DX:8.0f} {bb[1] + DY:8.0f} {bb[2] - bb[0]:6.0f}x{bb[3] - bb[1]:<6.0f}'
                       if bb else '                 sin bbox     ')
                tipo = n.get('type')
                mask = ' [MASK]' if ((n.get('meta') or {}).get('ux') or {}).get('clipPathResources') else ''
                patron = ((n.get('style') or {}).get('fill') or {}).get('type') == 'pattern'
                if (not solo_g and not solo_i) or (solo_g and tipo == 'group') or (solo_i and patron):
                    print(f'{"  " * prof}{tipo:6}{mask:7} {pos} {n.get("name", "")}')
                if tipo == 'group':
                    rec(n.get('group', {}).get('children', []), mm, prof + 1)
        rec(nodos, X.IDENTITY)
        return

    salida = sys.argv[-1]
    sin_textos = '--sin-textos' in sys.argv
    escala = float(sys.argv[sys.argv.index('--escala') + 1]) if '--escala' in sys.argv else 1

    if '--grupo' in sys.argv:
        nombre = sys.argv[sys.argv.index('--grupo') + 1]
        cerca = None
        if '--en' in sys.argv:
            i = sys.argv.index('--en')
            cerca = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))
        r = buscar_grupo(nodos, nombre, cerca=cerca)
        if not r:
            raise SystemExit(f'no encontré el grupo {nombre!r} en {prefijo}')
        nodo, m = r
        bb = bbox_de(nodo, m)
        if '--bbox' in sys.argv:      # bbox de página forzado: X Y W H
            i = sys.argv.index('--bbox')
            px, py, pw, ph = (float(v) for v in sys.argv[i + 1:i + 5])
            bb = (px - DX, py - DY, px - DX + pw, py - DY + ph)
        svg = X.render_svg(nodo, bb, X.mat_mul(m, X.node_transform(nodo)), resources_dir=RES)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        print(f'grupo {nombre!r} bbox pagina x={bb[0] + DX:.0f} y={bb[1] + DY:.0f} {w:.0f}x{h:.0f}')
        print(rasterizar(svg, salida, w, h, escala), '->', salida)
        if '--pag' in sys.argv:
            i = sys.argv.index('--pag')
            verificar(sys.argv[i + 1], round(bb[0] + DX), round(bb[1] + DY), round(w), round(h),
                      salida, sys.argv[sys.argv.index('--fondo') + 1] if '--fondo' in sys.argv else None)
        return

    if '--rect' in sys.argv:
        i = sys.argv.index('--rect')
        px, py, pw, ph = (float(v) for v in sys.argv[i + 1:i + 5])
        x0, y0, x1, y1 = px - DX, py - DY, px - DX + pw, py - DY + ph
        # `--excluir-rect X Y W H` (repetible): descarta lo que caiga dentro de ese rectángulo.
        # Hace falta porque una composición suele llevar DENTRO piezas que el HTML pone aparte:
        # en la portada de CF1 las dos fichas flotantes quedaban incrustadas en la imagen y el
        # CSS las volvía a pintar encima -> aparecían DUPLICADAS.
        fuera = []
        for i, arg in enumerate(sys.argv):
            if arg == '--excluir-rect':
                ex, ey, ew, eh = (float(v) for v in sys.argv[i + 1:i + 5])
                fuera.append((ex - DX, ey - DY, ex - DX + ew, ey - DY + eh))

        items = []
        for n, m, mm in hojas(nodos, X.IDENTITY, sin_textos):
            bb = bbox_de(n, m) or posicion_fallback(mm)
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            if any(fx0 <= cx <= fx1 and fy0 <= cy <= fy1 for fx0, fy0, fx1, fy1 in fuera):
                continue
            items.append((n, mm))
        print(f'{len(items)} nodos dentro del rect')
        svg = X.render_svg_multi(items, (x0, y0, x1, y1), resources_dir=RES)
        print(rasterizar(svg, salida, pw, ph, escala), '->', salida)
        if '--pag' in sys.argv:
            i = sys.argv.index('--pag')
            verificar(sys.argv[i + 1], round(px), round(py), round(pw), round(ph), salida,
                      sys.argv[sys.argv.index('--fondo') + 1] if '--fondo' in sys.argv else None)
        return

    raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
