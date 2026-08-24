#!/usr/bin/env python3
"""Los 6 parches que `scripts/xd_export.py` NO hace y sin los cuales los assets salen mal.

`xd_export.py` es COMPARTIDO con CF2, así que no se toca: se monkey-patchea desde aquí con
`import xd_patches; xd_patches.apply()` antes de llamar a `render_svg`/`render_svg_multi`.

1. **Máscaras de grupo.** Un grupo `SHAPE_MASK` lleva su recorte en
   `meta.ux.clipPathResources.children[0]` (relativo al origen del grupo) y `node_to_svg` lo
   ignora → las fotos salen sin recortar y con el encuadre equivocado.
   ⚠️ Dentro de un `<clipPath>` un `<g>` se IGNORA: hay que emitir la forma
   (`<path>`/`<rect>`/`<circle>`/`<ellipse>`) con su `transform` como atributo propio.

2. **`flipX`/`flipY` de los patterns.** `cropped_pattern_bytes` sí aplica `flipX` (y ni
   siquiera `flipY`), pero `shape_to_svg` no aplica ninguno → la foto sale espejada al revés.

3. **`meta.ux.scale` MULTIPLICA la escala de `cover`.** Si el pattern trae `scale: s`, la escala
   efectiva es `cover × s`, así que la imagen puede quedar MÁS PEQUEÑA que el nodo (es válido:
   sólo tiene que cubrir la ventana de la máscara, no el nodo). Ignorarlo da un encuadre muy
   ampliado. Junto con `offsetX/offsetY` obliga a colocar el `<image>` a mano en vez de
   dejárselo a `preserveAspectRatio="slice"`, que siempre centra y ajusta al nodo.

4. **`stroke.align: inside/outside`.** SVG sólo tiene trazo CENTRADO: un `circle r=64` con
   `stroke-width=6` pinta 3px FUERA del radio, y si el bbox del asset es justo el círculo esos
   3px se **cortan** (el anillo sale con los cuatro lados planos). Se compensa el radio:
   `inside → r − w/2`, `outside → r + w/2`.

5. **Estilos por SEGMENTO del texto.** `text_to_svg` pinta cada LÍNEA con el estilo del nodo, así
   que se pierden las negritas de los típicos «**Término:** descripción». Se emite un `<tspan>`
   por segmento, sin `x` propio para que fluyan.

6. **`shape.winding: evenodd` en los `path`.** `xd_export` pone `fill-rule="evenodd"` sólo en los
   `compound` (línea 740), y en un `path` no lo pone NUNCA — pero este XD tiene **210 nodos
   `type: "path"` con `"winding": "evenodd"`**. Sin la regla el navegador rellena con `nonzero`:
   **las contraformas del icono se rellenan y sale una mancha sólida**. Así salieron mal los
   cuatro iconos de Tema 3 (`i10`, `i11`, `o3`, `o4`): el triángulo de aviso sin el `!`, los
   checks sin su círculo, el engranaje sin el aro. Correlación de mi PNG contra el SVG bueno de
   Manuel: 0.70–0.82. Lo detectó él a mano (2026-07-30).
"""
import sys

import config as C  # noqa: E402
C.pipeline()
import xd_export as X  # noqa: E402

_orig = {}


def _weight_of(fstyle):
    f = (fstyle or '').lower()
    return 'bold' if ('bold' in f or 'black' in f or 'heavy' in f) else 'normal'


def _mat_attr(node):
    t = node.get('transform') or {}
    return (f'matrix({t.get("a",1)} {t.get("b",0)} {t.get("c",0)} {t.get("d",1)} '
            f'{t.get("tx",0)} {t.get("ty",0)})')


def _shape_element(node):
    """La forma de una máscara como UN elemento con su transform de atributo.
    Dentro de `<clipPath>` no vale envolverla en un `<g>`: el navegador lo ignora."""
    shp = node.get('shape') or {}
    t = shp.get('type')
    tr = f' transform="{_mat_attr(node)}"' if node.get('transform') else ''
    if t == 'rect':
        r = shp.get('r')
        if r and len(set(r)) > 1:
            d = X._rounded_rect_path(shp['x'], shp['y'], shp['width'], shp['height'], r)
            return f'<path d="{d}"{tr}/>'
        rx = r[0] if r else 0
        return (f'<rect x="{shp["x"]}" y="{shp["y"]}" width="{shp["width"]}" '
                f'height="{shp["height"]}" rx="{rx}"{tr}/>')
    if t == 'circle':
        return f'<circle cx="{shp["cx"]}" cy="{shp["cy"]}" r="{shp["r"]}"{tr}/>'
    if t == 'ellipse':
        return (f'<ellipse cx="{shp["cx"]}" cy="{shp["cy"]}" rx="{shp["rx"]}" '
                f'ry="{shp["ry"]}"{tr}/>')
    if t in ('path', 'compound'):
        regla = ' clip-rule="evenodd"' if t == 'compound' else ''
        return f'<path d="{shp.get("path","")}"{regla}{tr}/>'
    return ''


def _blend(node):
    """`style.blendMode` -> el `mix-blend-mode` de SVG, o '' si no hay que hacer nada.

    Sin esto se pierde el aspecto de los fondos compuestos: el hero de CF1_63720048 es un
    degradado CLARO (lila -> azul) con dos texturas encima en `multiply` (op 0.6) y `soft-light`
    (op 0.7); si se ignoran los modos de fusión, el panel sale pálido y sin las líneas
    diagonales, en vez del azul profundo con magenta del diseño.
    """
    bm = (node.get('style') or {}).get('blendMode')
    if not bm or bm in ('normal', 'passThrough'):
        return ''
    return f' style="mix-blend-mode:{bm}"'


# ── 1. máscaras de grupo ────────────────────────────────────────────────────────────
def node_to_svg(node, defs, resources_dir=None):
    if node.get('type') == 'group':
        cp = ((node.get('meta') or {}).get('ux') or {}).get('clipPathResources')
        if cp and cp.get('children'):
            el = _shape_element(cp['children'][0])
            if el:
                cid = X._next_gid()
                defs.append(f'<clipPath id="{cid}">{el}</clipPath>')
                gattr = (f' transform="{_mat_attr(node)}"' if node.get('transform') else '')
                inner = ''.join(node_to_svg(c, defs, resources_dir)
                                for c in node.get('group', {}).get('children', []))
                return (f'<g{gattr}{X._group_opacity_attr(node)}{_blend(node)}>'
                        f'<g clip-path="url(#{cid})">{inner}</g></g>')
    salida = _orig['node_to_svg'](node, defs, resources_dir)
    bl = _blend(node)
    return f'<g{bl}>{salida}</g>' if bl else salida


# ── 2 + 3 + 4. patterns (flip, scale, offset) y stroke.align ────────────────────────
def shape_to_svg(node, defs, resources_dir=None):
    shp = dict(node.get('shape') or {})
    style = node.get('style') or {}
    fill = style.get('fill') or {}
    t = shp.get('type')

    # --- patterns: colocar el <image> a mano ---
    if fill.get('type') == 'pattern' and resources_dir:
        pat = fill.get('pattern') or {}
        ux = (pat.get('meta') or {}).get('ux') or {}
        uid = ux.get('uid')
        bbox = X.shape_local_bbox(shp)
        pw, ph = pat.get('width'), pat.get('height')
        href = None
        if uid:
            try:
                href = X._image_data_uri(resources_dir, uid)
            except OSError:
                href = None
        if href and bbox and pw and ph:
            x0, y0, x1, y1 = bbox
            w, h = x1 - x0, y1 - y0
            escala = max(w / pw, h / ph) * (ux.get('scale') or 1)
            sw, sh = pw * escala, ph * escala
            # misma convención que `cropped_pattern_bytes`: el offset es fracción de la
            # dimensión ESCALADA y corre la ventana de recorte respecto al centro.
            ix = x0 - (sw - w) / 2 + (ux.get('offsetX') or 0) * sw
            iy = y0 - (sh - h) / 2 + (ux.get('offsetY') or 0) * sh
            cid = X._next_gid()
            defs.append(f'<clipPath id="{cid}">{_shape_element({"shape": shp})}</clipPath>')
            flip = ''
            if ux.get('flipX') or ux.get('flipY'):
                cx, cy = ix + sw / 2, iy + sh / 2
                sx = -1 if ux.get('flipX') else 1
                sy = -1 if ux.get('flipY') else 1
                flip = f' transform="translate({cx} {cy}) scale({sx} {sy}) translate({-cx} {-cy})"'
            op = style.get('opacity', 1.0)
            extra = f' opacity="{op}"' if op < 0.999 else ''
            return (f'<g clip-path="url(#{cid})"{extra}>'
                    f'<image x="{ix}" y="{iy}" width="{sw}" height="{sh}" href="{href}" '
                    f'preserveAspectRatio="none"{flip}/></g>')

    # --- stroke.align: compensar el radio para que el trazo quepa en el bbox ---
    stroke = style.get('stroke') or {}
    align = stroke.get('align')
    if align in ('inside', 'outside') and stroke.get('type') not in (None, 'none'):
        d = (stroke.get('width', 1) or 1) / 2
        d = -d if align == 'inside' else d
        if t == 'circle':
            shp['r'] = shp['r'] + d
        elif t == 'ellipse':
            shp['rx'], shp['ry'] = shp['rx'] + d, shp['ry'] + d
        elif t == 'rect':
            shp['x'], shp['y'] = shp['x'] - d, shp['y'] - d
            shp['width'], shp['height'] = shp['width'] + 2 * d, shp['height'] + 2 * d
        node = dict(node)
        node['shape'] = shp
    svg = _orig['shape_to_svg'](node, defs, resources_dir)

    # --- winding: el `fill-rule` que xd_export sólo pone en los `compound` (ver el punto 6) ---
    if t == 'path' and shp.get('winding') == 'evenodd' and 'fill-rule' not in svg:
        svg = svg.replace('<path ', '<path fill-rule="evenodd" ', 1)
    return svg


# ── 5. estilos por segmento del texto ───────────────────────────────────────────────
def text_to_svg(node):
    style = node.get('style', {})
    font = style.get('font', {})
    familia = font.get('family', 'sans-serif')
    peso_base = _weight_of(font.get('style') or font.get('postscriptName'))
    size = font.get('size', 14)
    color, _ = X.color_str(style.get('fill', {}).get('color', {}))
    td = node.get('text', {})
    raw = td.get('rawText', '')
    align = style.get('textAttributes', {}).get('paragraphAlign', 'left')
    fw = (td.get('frame') or {}).get('width')
    partes = []
    for p in td.get('paragraphs', []):
        for linea in p.get('lines', []):
            if not linea:
                continue
            if not raw[linea[0].get('from', 0):linea[-1].get('to', 0)].strip():
                continue
            x, y = linea[0].get('x', 0), linea[0].get('y', 0)
            attr = f'font-family="{familia}" font-size="{size}" fill="{color}"'
            if 'italic' in (font.get('style') or '').lower():
                attr += ' font-style="italic"'
            if align == 'center' and fw:
                attr += ' text-anchor="middle"'
                x = fw / 2
            elif align == 'right' and fw:
                attr += ' text-anchor="end"'
                x = fw
            spans = ''
            for seg in linea:
                trozo = raw[seg.get('from', 0):seg.get('to', 0)]
                if not trozo:
                    continue
                sf = (seg.get('style') or {}).get('font')
                w = _weight_of(sf.get('style') or sf.get('postscriptName')) if sf else peso_base
                # sin `x` propio: los tspan tienen que FLUIR uno tras otro
                spans += f'<tspan font-weight="{w}">{X._esc(trozo)}</tspan>'
            if spans:
                partes.append(f'<text x="{x}" y="{y}" {attr}>{spans}</text>')
    return ''.join(partes)


# ── 3bis. meta.ux.scale también en el recorte raster ────────────────────────────────
def cropped_pattern_bytes(node, local_bbox, src_path):
    """Como el original, pero aplicando `meta.ux.scale` (que multiplica la escala de cover)
    y `flipY`, que el original tampoco aplica."""
    try:
        from PIL import Image
    except ImportError:
        return None
    import io
    style = node.get('style', {})
    pat = style.get('fill', {}).get('pattern', {})
    ux = (pat.get('meta') or {}).get('ux') or {}
    pw, ph = pat.get('width'), pat.get('height')
    if not pw or not ph or not local_bbox:
        return None
    x0, y0, x1, y1 = local_bbox
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return None
    try:
        img = Image.open(src_path)
        img.load()
    except OSError:
        return None
    if ux.get('flipX'):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if ux.get('flipY'):
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    escala = max(w / pw, h / ph) * (ux.get('scale') or 1)
    sw, sh = pw * escala, ph * escala
    red = img.resize((max(1, round(sw)), max(1, round(sh))), Image.LANCZOS)
    ox, oy = sw - w, sh - h
    cx = ox / 2 - (ux.get('offsetX') or 0) * sw
    cy = oy / 2 - (ux.get('offsetY') or 0) * sh
    # con scale<1 la imagen escalada puede ser MENOR que el nodo: entonces no hay overflow
    # que recortar y se pega centrada sobre un lienzo transparente del tamaño del nodo.
    if sw < w or sh < h:
        lienzo = Image.new('RGBA', (round(w), round(h)), (0, 0, 0, 0))
        lienzo.paste(red, (round(-cx), round(-cy)),
                     red if red.mode == 'RGBA' else None)
        rec = lienzo
    else:
        cx = max(0, min(ox, cx))
        cy = max(0, min(oy, cy))
        rec = red.crop((round(cx), round(cy), round(cx) + round(w), round(cy) + round(h)))
    buf = io.BytesIO()
    rec.save(buf, format='PNG')
    return buf.getvalue()


def apply():
    """Instala los parches (idempotente)."""
    if _orig:
        return
    for nombre, nuevo in (('node_to_svg', node_to_svg),
                          ('shape_to_svg', shape_to_svg),
                          ('text_to_svg', text_to_svg),
                          ('cropped_pattern_bytes', cropped_pattern_bytes),
                          ('paint_to_svg', paint_to_svg)):
        _orig[nombre] = getattr(X, nombre)
        setattr(X, nombre, nuevo)


# ---------------------------------------------------------------------------
# ⛔ NO SE REMAPEA NADA: el color de cada elemento es EXACTAMENTE el del nodo del XD
# ---------------------------------------------------------------------------
# Intenté traducir la «paleta vieja» del arte (#FFC0AC, #DBC2FA, #16D95E, #FFE6DE, #F4EDFE,
# #B8F4CE) a los hex ESCRITOS en la hoja de especificación. **ERROR, corregido por Luis el
# 2026-07-30**: «los colores de los elementos background deben ser exactamente el color propuesto
# en el XD». La hoja de spec sólo manda en las VARIABLES de la plantilla (p. ej. el acento-botones
# `#85E336`); el color de un rect, de un círculo o de una banda es el `fill` de ese nodo y nada más.
# Se deja la función como identidad para no tocar las llamadas.
PALETA_VIEJA_A_NUEVA = {}


def remapear_paleta(svg):
    """Identidad: el color de cada nodo del XD se respeta tal cual (regla de Luis, 2026-07-30)."""
    return svg


# ---------------------------------------------------------------------------
# Parche 6: la DIRECCIÓN del degradado lineal (hallazgo de Luis: «BANNER: SE INVIRTIERON
# LOS COLORES», 2026-07-30)
# ---------------------------------------------------------------------------
# `xd_export.paint_to_svg` busca `x1/y1/x2/y2` dentro de `gradient.meta.ux.gradientResources`,
# pero el XD los guarda un nivel más arriba, en el propio `gradient`. Al no encontrarlos usaba
# los defaults `0,0 -> 1,0`, o sea **siempre un degradado horizontal izquierda→derecha**, y en el
# hero del banner eso invierte los colores: el XD va de lila (abajo-centro) a azul (arriba-izq)
# y salía azul→lila.
#   `"x1": 0.4752, "y1": 0.9500, "x2": -0.0401, "y2": 0, "units": "objectBoundingBox"`
# El rect además va rotado 180° (`a=-1, d=-1`), y como el degradado es `objectBoundingBox` la
# rotación se le aplica sola en cuanto los valores son los buenos.
def paint_to_svg(paint, defs, opacity=1.0):
    if paint and paint.get('type') == 'gradient':
        grad = paint.get('gradient', {}) or {}
        ux = ((grad.get('meta') or {}).get('ux') or {}).get('gradientResources') or {}
        if ux.get('type', 'linear') != 'radial':
            faltan = not any(k in ux for k in ('x1', 'y1', 'x2', 'y2'))
            if faltan and any(k in grad for k in ('x1', 'y1', 'x2', 'y2')):
                ux = dict(ux)
                for k in ('x1', 'y1', 'x2', 'y2'):
                    if k in grad:
                        ux[k] = grad[k]
                grad = dict(grad)
                meta = dict(grad.get('meta') or {})
                mux = dict(meta.get('ux') or {})
                mux['gradientResources'] = ux
                meta['ux'] = mux
                grad['meta'] = meta
                paint = dict(paint)
                paint['gradient'] = grad
    return _orig['paint_to_svg'](paint, defs, opacity)
