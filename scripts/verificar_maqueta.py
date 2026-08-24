#!/usr/bin/env python3
"""Auditoría del entregable YA maquetado. Corre lo que en CF1 hubo que comprobar a mano una y otra
vez, y cada comprobación existe porque algo se colcó por ahí:

  1. ASSETS QUE NO EXISTEN  -> un `@/assets/...` roto deja la vista entera en gris (overlay de Vite)
  2. VISTAS EN GRIS         -> mide el gris oscuro de cada ruta; >0.3 = la vista está rota
  3. AOS SIN ANIMAR        -> con el viewport cubriendo la página, 0 elementos `[data-aos]` sin
                              `aos-animate`; si sale alguno, ese bloque no se ve nunca
  4. DESBORDE EN MÓVIL      -> por CDP, ningún elemento con `right` mayor que el `clientWidth`
  4d. CAJA FUERA DE COLUMNA -> por CDP y en ESCRITORIO, ningún hijo de un `col-*` con el `bottom`
                              por debajo del de su columna: eso se monta sobre el bloque siguiente
  5. COLORES PROHIBIDOS     -> hex que NO están en el XD (p. ej. los de un remapeo revertido)

Los checks 1x son ESTÁTICOS (leen el Pug/JSON/DOCX, no hace falta el servidor) y cada uno existe
porque una revisión manual lo pilló: 1b/1c/1d de la de Manuel del 2026-07-30 y 1e/1f/1g/1h/1i de la
del 2026-08-04 (placeholders del scaffold, la actividad contra el AD.docx, las imágenes repetidas de
la actividad, el contraste de `textColor()` y los comentarios de bitácora en el código). El 4d es de
la revisión de Luis del 2026-08-04 (Tema 1 de CF2: `.h-100` sobre `.tarjeta--icono-arriba`).

Uso:  verificar_maqueta.py [--base URL] [--prohibidos HEX,HEX] [--movil 485] [--desktop 1440]
                           [--estaticos]
      --estaticos  corre sólo los checks 1x y sale (no levanta Chrome ni necesita el servidor)
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

def servidor():
    """La URL del `npm run serve` que esté vivo, leyendo el `base` del propio `vite.config.js`.

    Antes había aquí un literal con el base de OTRO entregable y un puerto fijo. Vite coge 5173 si
    está libre y 5174/5175 si no, así que el literal se queda obsoleto en cuanto hay dos servidores
    abiertos — y el fallo no se ve: la herramienta mide una página que no es la tuya.
    """
    aqui = os.path.dirname(os.path.abspath(__file__))
    m = re.search(r"base:.*?'(/[^']+/)'", open(os.path.join(aqui, '..', 'vite.config.js')).read())
    ruta = m.group(1) if m else '/'
    for puerto in (5173, 5174, 5175, 5176):
        try:
            url = f'http://localhost:{puerto}{ruta}'
            urllib.request.urlopen(url, timeout=1).read(1)
            return url
        except Exception:
            continue
    return f'http://localhost:5173{ruta}'      # los checks estáticos no necesitan servidor


BASE = servidor()
RUTAS = ['', 'introduccion', 'curso/tema1', 'curso/tema2', 'curso/tema3', 'curso/tema4',
         'curso/tema5', 'curso/tema6', 'sintesis', 'actividad', 'glosario', 'referencias',
         'creditos']
if '--base' in sys.argv:
    BASE = sys.argv[sys.argv.index('--base') + 1]
PROHIBIDOS = []
if '--prohibidos' in sys.argv:
    PROHIBIDOS = [h.strip().lstrip('#').upper() for h in sys.argv[sys.argv.index('--prohibidos') + 1].split(',')]
ANCHO_MOVIL = int(sys.argv[sys.argv.index('--movil') + 1]) if '--movil' in sys.argv else 485
# El 4d va en ESCRITORIO a propósito: el fallo que lo motivó sólo existe con las columnas en fila
# (`height: 100%` contra una columna estirada). Apiladas en móvil no se reproduce.
ANCHO_DESKTOP = int(sys.argv[sys.argv.index('--desktop') + 1]) if '--desktop' in sys.argv else 1440

fallos = []


def paso(titulo):
    print(f'\n=== {titulo}')


def chrome(args):
    return subprocess.run(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                           '--hide-scrollbars'] + args, capture_output=True, text=True)


# ---------------------------------------------------------------- 1. assets inexistentes
paso('1. assets referenciados que no existen')
faltan = []
for f in glob.glob('src/views/*.vue') + ['src/config/global.js']:
    txt = open(f).read()
    for ref in set(re.findall(r"@/assets/[\w./-]+", txt)):
        if not os.path.exists('src/' + ref[2:]):
            faltan.append(f'{os.path.basename(f)} -> {ref}')
print('  ' + ('\n  '.join(faltan) if faltan else 'ninguno'))
if faltan:
    fallos.append(f'{len(faltan)} assets inexistentes')

# Los tres checks siguientes son ESTÁTICOS (leen el Pug, no hace falta el servidor) y salieron los
# tres de la revisión manual de Manuel del 2026-07-30.

# ---------------------------------------------------------------- 1b. iconos repetidos
# 11 referencias repetidas en CF1 (Tema 2 y Tema 6): me quedé sin iconos exportados y reusé uno
# «parecido». En el XD cada tarjeta lleva el suyo.
paso('1b. iconos repetidos dentro del mismo tema')
repes = []
for f in sorted(glob.glob('src/views/Tema*.vue')):
    usos = {}
    for ln in open(f).read().split('\n'):
        m = re.search(r"@/assets/curso/temas/t\d+/([\w.-]+\.(?:png|svg))", ln)
        if m:
            usos.setdefault(m.group(1), []).append(ln)
    for ref, lineas_uso in usos.items():
        # el par escritorio/móvil de una misma figura NO es una repetición: son la misma imagen
        # con `d-none.d-md-block` y `d-md-none`
        if len(lineas_uso) > 1 and not all(re.search(r'\bd-(none|block|md-none)\b', u) for u in lineas_uso):
            repes.append(f'{os.path.basename(f)} -> {ref} x{len(lineas_uso)}')
print('  ' + ('\n  '.join(repes) if repes else 'ninguno'))
if repes:
    fallos.append(f'{len(repes)} iconos repetidos')

# ---------------------------------------------------------------- 1c. col por ancho de imagen
# `col = round(ancho_px / 1228 x 12)`, con 1228 = ancho útil de la tarjeta blanca. Cinco fotos de
# 292px estaban en `col-lg-4` cuando les toca `col-lg-3`.
# Dos condiciones para no llenarlo de falsos positivos:
#   · la columna tiene que ser SÓLO de la imagen (si dentro hay un `p`, el ancho no lo manda ella:
#     es un icono de 84px al lado de un texto);
#   · la fila tiene que ser de PRIMER NIVEL (`.row` a 4 espacios): dentro de otra columna el ancho
#     útil ya no es 1228.
paso('1c. col-lg-N contra el ancho de la imagen (1228px de ancho útil)')
UTIL = 1228
SANGRIA_COL = 6                      # `.col-*` hijo de un `.row` de primer nivel (4 espacios)
descuadres = []
for f in sorted(glob.glob('src/views/*.vue')):
    lineas = open(f).read().split('\n')
    for k, ln in enumerate(lineas):
        c = re.match(r' *\.col-lg-(\d+)\b', ln)
        if not c or (len(ln) - len(ln.lstrip())) != SANGRIA_COL:
            continue
        bloque = []
        for sig in lineas[k + 1:]:
            if sig.strip() and (len(sig) - len(sig.lstrip())) <= SANGRIA_COL:
                break
            bloque.append(sig)
        etiquetas = [b.strip() for b in bloque if b.strip()]
        if not etiquetas or any(not re.match(r'(figure|img|\.row|\.col|\|)', e) for e in etiquetas):
            continue                  # la columna lleva algo más que la figura
        anchos = [int(m.group(1)) for e in etiquetas
                  if 'img' in e and (m := re.search(r'style="width:\s*(\d+)px"', e))]
        if len(set(anchos)) != 1 or anchos[0] >= UTIL - 8:
            continue
        col, esperado = int(c.group(1)), round(anchos[0] / UTIL * 12)
        if col != esperado:
            descuadres.append(f'{os.path.basename(f)}:{k + 1} {anchos[0]}px en col-lg-{col} '
                              f'-> le toca col-lg-{esperado}')
print('  ' + ('\n  '.join(descuadres) if descuadres else 'ninguno'))
if descuadres:
    fallos.append(f'{len(descuadres)} col-lg descuadrados con el ancho de la imagen')

# ---------------------------------------------------------------- 1d. columnas vacías
# Error de indentación de Pug: se escribe el envoltorio `.row > .col-lg-10` y el componente se
# queda al nivel de arriba, así que sale a ancho completo. En el navegador no da ningún error.
paso('1d. columnas vacías (componente fuera de su envoltorio)')
vacias = []
for f in sorted(glob.glob('src/views/*.vue')):
    lineas = open(f).read().split('\n')
    for k, ln in enumerate(lineas):
        if not re.match(r' *\.col[-.(\s]', ln) and not re.match(r' *\.col$', ln):
            continue
        sangria = len(ln) - len(ln.lstrip())
        sig = next((s for s in lineas[k + 1:] if s.strip()), None)
        if sig is not None and (len(sig) - len(sig.lstrip())) <= sangria:
            vacias.append(f'{os.path.basename(f)}:{k + 1} {ln.strip()}')
print('  ' + ('\n  '.join(vacias) if vacias else 'ninguna'))
if vacias:
    fallos.append(f'{len(vacias)} columnas vacías')

# Los cinco checks siguientes también son ESTÁTICOS y salieron de la SEGUNDA revisión manual de
# Manuel (commit `65ff4b0 Ajustes finales`, 2026-08-04) sobre CF1.

# ---------------------------------------------------------------- 1e. placeholders de la plantilla
# `src/config/titulo.js` se quedó en 'Ecored Base PKG' -> el título de la pestaña del navegador de
# TODO el curso. El scaffold trae varios de estos y ninguno rompe nada, así que no se notan.
paso('1e. placeholders del scaffold sin rellenar')
PLACEHOLDERS = ['Ecored Base PKG', 'NUEVA_BASE_TOLIMA', "termino: 'Término'", "referencia: '---'",
                'Lorem ipsum', 'CAMBIAR', 'TODO:']
sueltos = []
# `index.html` queda FUERA a propósito: su `<title>` literal lo reescribe el plugin `html-title` de
# `vite.config.js` con lo que diga `src/config/titulo.js`, así que ahí el placeholder es inocuo.
for f in glob.glob('src/config/*.js') + glob.glob('src/views/*.vue') + ['vite.config.js']:
    if not os.path.exists(f):
        continue
    txt = open(f).read()
    for ph in PLACEHOLDERS:
        if ph in txt:
            sueltos.append(f'{f} -> {ph}')
print('  ' + ('\n  '.join(sueltos) if sueltos else 'ninguno'))
if sueltos:
    fallos.append(f'{len(sueltos)} placeholders de la plantilla sin rellenar')

# ---------------------------------------------------------------- 1f. la actividad contra el AD.docx
# El cuestionario NO se redacta: está entero en las tablas del `_AD.docx`. En CF1 se perdieron los
# dos mensajes finales, el objetivo y el `barajarRespuestas` de las 20 preguntas.
# ÚNICA licencia sobre el texto del docx: el prefijo «¡Correcto!»/«¡Incorrecto!» se quita, porque
# `ActividadPregunta.vue` del kit ya pinta esa etiqueta (comprobado en kit 1.0.9: dejarlo da
# «¡Correcto!¡Correcto! El principio de…»).
paso('1f. Actividad.vue contra las tablas del _AD.docx')
falta_act = []
ad = next(iter(glob.glob('fuentes/*_AD.docx')), '')
if not ad or not os.path.exists('src/views/Actividad.vue'):
    print('  (no hay fuentes/*_AD.docx o src/views/Actividad.vue)')
else:
    vue = open('src/views/Actividad.vue').read()
    filas = subprocess.run([sys.executable, 'scripts/docx_text.py', ad],
                           capture_output=True, text=True).stdout.splitlines()

    def celda(etiqueta):
        for ln in filas:
            partes = [p.strip() for p in ln.strip().strip('|').split('|')]
            if partes and partes[0].lower().startswith(etiqueta.lower()) and len(partes) > 1:
                return partes[1]
        return None

    def esta(txt):
        """el docx trae «¶» donde el párrafo salta y la vista lo escribe como <br> o partido en
        varias líneas por prettier: se compara por palabras."""
        limpio = re.sub(r'\s+', ' ', txt.replace('¶', ' ')).strip()
        limpio = re.sub(r'^¡(In)?[Cc]orrecto!\s*', '', limpio)
        # el docx escribe «Reconocer los principios…» y la vista «<b>Objetivo:</b> reconocer los
        # principios…»: la mayúscula inicial cambia al empalmar, así que se compara en minúscula
        aguja = re.sub(r'\s+', ' ', limpio)[:70].lower()
        return re.sub(r"\s+|'\s*\+\s*'|\\n", ' ', vue).lower().find(aguja) >= 0

    esperados = [ln for ln in filas if 'Comentario respuesta correcta' in ln]
    for ln in esperados:
        t = [p.strip() for p in ln.strip().strip('|').split('|')][1]
        if not esta(t):
            falta_act.append(f'retroalimentación ausente o reescrita: «{t[:60]}…»')
    for etq in ('Objetivo de la actividad', 'Mensaje cuando supera', 'Mensaje cuando el porcentaje'):
        t = celda(etq)
        if t and not esta(t):
            falta_act.append(f'«{etq}» no está en la vista: «{t[:60]}…»')
    n_preg = len([ln for ln in filas if re.match(r'\|\s*Pregunta \d+\s*\|', ln)])
    n_vue = len(re.findall(r'\bid:\s*\d+,', vue))
    if n_preg and n_preg != n_vue:
        falta_act.append(f'{n_preg} preguntas en el docx pero {n_vue} en la vista')
    n_baraja = vue.count('barajarRespuestas')
    if n_vue and n_baraja < n_vue:
        falta_act.append(f'{n_vue - n_baraja} preguntas sin `barajarRespuestas: true`')
    if 'barajarPreguntas: true' not in vue:
        falta_act.append('falta `barajarPreguntas: true` (el kit corta a 10 con slice)')
    print('  ' + ('\n  '.join(falta_act) if falta_act else 'la vista trae el docx completo'))
if falta_act:
    fallos.append(f'{len(falta_act)} descuadres de la actividad contra el AD.docx')

# ---------------------------------------------------------------- 1g. imágenes de la actividad
# El scaffold trae 10 `imagen*.png` de otro curso y CON DUPLICADOS (5 distintas en 10 archivos).
# No están en el XD ni en el PDF: las aporta el diseñador. Si se entregan las de la plantilla,
# el curso sale con las fotos de otro.
paso('1g. imágenes de la actividad repetidas o de la plantilla')
import hashlib                                            # noqa: E402
firmas = {}
for f in sorted(glob.glob('src/assets/actividad/imagen*.png')):
    firmas.setdefault(hashlib.md5(open(f, 'rb').read()).hexdigest(), []).append(os.path.basename(f))
dupes = [' = '.join(v) for v in firmas.values() if len(v) > 1]
print('  ' + ('\n  '.join(dupes) if dupes else f'{len(firmas)} imágenes distintas'))
if dupes:
    fallos.append(f'{len(dupes)} grupos de imágenes de actividad repetidas')

# ---------------------------------------------------------------- 1h. contraste de textColor()
# `textColor($c)` del kit devuelve oscuro si `lightness(hsl) > 50` y blanco si no. Hay colores
# vivos que caen del lado malo: `#16D95E` da 46,9 % -> número BLANCO sobre verde claro. Manuel lo
# arregló forzando `#000` en `.img-infografica.color-acento-botones .img-infografica__item__numero`.
paso('1h. colores de la paleta en la frontera de textColor() (lightness 40-55 %)')
frontera = []
if os.path.exists('src/styles/_variables.sass'):
    for nombre, hexa in re.findall(r'^\$(color-[\w-]+):\s*(#[0-9A-Fa-f]{6})',
                                   open('src/styles/_variables.sass').read(), re.M):
        r_, g_, b_ = (int(hexa[k:k + 2], 16) for k in (1, 3, 5))
        light = (max(r_, g_, b_) + min(r_, g_, b_)) / 2 / 255 * 100
        if 40 <= light <= 55:
            usos = sum(open(v).read().count(f'.{nombre}') for v in glob.glob('src/views/*.vue'))
            lado = 'BLANCO' if light <= 50 else 'oscuro'
            frontera.append(f'${nombre} {hexa} lightness={light:.1f}% -> textColor() da {lado} '
                            f'({usos} usos de .{nombre} en las vistas)')
print('  ' + ('\n  '.join(frontera) if frontera else 'ninguno en la frontera'))
if frontera:
    print('  ⚠️  comprobar a ojo los números/viñetas de esos componentes contra el XD')

# ---------------------------------------------------------------- 1i. comentarios de bitácora
# Manuel borró de `_variables.sass` y de `Tema1.vue` los comentarios donde yo explicaba el porqué
# del cambio (con fechas y el nombre de Luis). OJO: borró 2 de los 11 que hay, así que puede haber
# sido incidental — por eso esto AVISA y no falla. El criterio: el porqué va a la BITÁCORA, que
# además ya no viaja en el repo (`*.md` está en el .gitignore del entregable).
paso('1i. comentarios de bitácora dentro del código (aviso, no fallo)')
BITACORA = re.compile(r'(Luis|hallazgo|HALLAZGO|FALSO|20\d\d-\d\d-\d\d|corregido por|BITÁCORA)')
notas = []
for f in glob.glob('src/**/*.vue', recursive=True) + glob.glob('src/**/*.sass', recursive=True):
    for k, ln in enumerate(open(f).read().split('\n')):
        if re.match(r'\s*(//|/\*|\*)', ln) and BITACORA.search(ln):
            notas.append(f'{f}:{k + 1} {ln.strip()[:70]}')
print('  ' + ('\n  '.join(notas) if notas else 'ninguno'))
if notas:
    print(f'  ⚠️  {len(notas)} comentarios con fecha/nombre propio: sacarlos a la BITÁCORA')

if '--estaticos' in sys.argv:
    print('\n' + ('❌ ' + ' | '.join(fallos) if fallos else '✅ los checks estáticos, en orden'))
    sys.exit(1 if fallos else 0)

# ---------------------------------------------------------------- 2. vistas en gris
paso('2. vistas rotas (overlay de error de Vite)')
from PIL import Image                                   # noqa: E402
import numpy as np                                      # noqa: E402
Image.MAX_IMAGE_PIXELS = None
tmp = '/tmp/verificar-maqueta'
os.makedirs(tmp, exist_ok=True)
rotas = []
for r in RUTAS:
    png = f'{tmp}/{r.replace("/", "-") or "inicio"}.png'
    chrome(['--virtual-time-budget=9000', '--window-size=1400,1300',
            f'--screenshot={png}', f'{BASE}?noaos#/{r}'])
    a = np.asarray(Image.open(png).convert('RGB')).astype(int)
    g = (((abs(a[:, :, 0] - a[:, :, 1]) < 12) & (abs(a[:, :, 1] - a[:, :, 2]) < 12) & (a[:, :, 0] < 80)).mean())
    if g > 0.3:
        rotas.append(r or 'inicio')
print(f'  {len(RUTAS)} rutas revisadas -> rotas: ' + (', '.join(rotas) if rotas else 'ninguna'))
if rotas:
    fallos.append(f'rutas rotas: {rotas}')

# ---------------------------------------------------------------- 3. AOS
paso('3. elementos [data-aos] que no llegan a animarse')
sin = 0
for r in RUTAS[:10]:
    out = chrome(['--virtual-time-budget=20000', '--window-size=1600,16000', '--dump-dom',
                  f'{BASE}#/{r}']).stdout
    tags = re.findall(r'<[a-zA-Z][^>]*data-aos=[^>]*>', out)
    n = len([t for t in tags if 'aos-animate' not in t])
    if n:
        print(f'  {r or "inicio"}: {n} sin animar')
    sin += n
print('  total sin animar:', sin)
if sin:
    fallos.append(f'{sin} elementos con data-aos que no se ven')

# ---------------------------------------------------------------- 4. desborde en móvil
paso(f'4. desborde horizontal a {ANCHO_MOVIL}px')
try:
    import websocket
    proc = subprocess.Popen(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                             '--remote-debugging-port=9399', '--remote-allow-origins=*',
                             f'--window-size={ANCHO_MOVIL},1200', f'{BASE}?noaos#/curso/tema1'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(7)
    tg = [t for t in json.load(urllib.request.urlopen('http://127.0.0.1:9399/json')) if t['type'] == 'page']
    ws = websocket.create_connection(tg[0]['webSocketDebuggerUrl'], suppress_origin=True, timeout=30)
    i = [0]

    def ev(e):
        i[0] += 1
        ws.send(json.dumps({'id': i[0], 'method': 'Runtime.evaluate',
                            'params': {'expression': e, 'returnByValue': True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == i[0]:
                return m['result']['result'].get('value')
    res = ev('''(()=>{const w=document.documentElement.clientWidth;const o=[];
    document.querySelectorAll('*').forEach(e=>{const r=e.getBoundingClientRect();const cs=getComputedStyle(e);
      if(r.right>w+2 && cs.overflowX==='visible' && cs.position!=='fixed'
         && !e.closest('.slyder-f__main,.scroll-horizontal,.tabla-a,.accesibilidad,.barra-avance'))
        o.push(e.tagName+'.'+(e.className||'').toString().slice(0,44));});
    return JSON.stringify({w, n:o.length, ej:o.slice(0,5)})})()''')
    d = json.loads(res)
    print(f'  clientWidth={d["w"]}  elementos que se salen: {d["n"]}')
    for x in d['ej']:
        print('   ', x)
    if d['n']:
        fallos.append(f'{d["n"]} elementos se desbordan en móvil')
    ws.close()
    proc.kill()
except Exception as e:                                   # noqa: BLE001
    print('  (no se pudo medir por CDP:', e, ')')

# ---------------------------------------------------------------- 4b. cajones vs pestañas del XD
paso('4b. `.cajon` maquetados vs pestañas de 25x8 del XD')
mapa = 'docs/mapa-artboards.json'
if os.path.exists(mapa):
    filas = json.load(open(mapa))
    for f in filas:
        vista = None
        m = re.match(r'Tema-?(\d)', f['nombre'])
        if m:
            vista = f'src/views/Tema{m.group(1)}.vue'
        if not vista or not os.path.exists(vista):
            continue
        env = dict(os.environ, XD_DX=str(f['dx']), XD_DY=str(f['dy']))
        out = subprocess.run([sys.executable, 'scripts/inventario_xd.py', f['id']],
                             capture_output=True, text=True, env=env).stdout
        sec = out.split('=== 3.')[1].split('=== 4.')[0] if '=== 3.' in out else ''
        n = len([l for l in sec.splitlines() if l.startswith('  (')])
        maq = open(vista).read().count('.cajon.color1')
        estado = 'OK' if n == maq else 'DESCUADRE'
        print(f'  {f["nombre"][:10]:10} XD={n}  maquetados={maq}  {estado}')
        if n != maq:
            fallos.append(f'{f["nombre"]}: {maq} .cajon pero {n} pestañas en el XD')
else:
    print('  (falta docs/mapa-artboards.json: correr preparar_curso.py)')

# ---------------------------------------------------------------- 4c. altos contra el XD
# ⚠️ SIN IMPLEMENTAR DE FORMA FIABLE. Dos intentos y los dos midieron la VENTANA, no el contenido:
#   1) «última fila no blanca» -> el fondo de página es #F3F9FF, no blanco, así que devolvía el alto
#      de la ventana;
#   2) «primera y última fila blanca de la columna central» -> Chrome pinta blanco FUERA del body,
#      así que también devolvía la ventana (render = XD + 5999 en los seis temas, exacto).
# La forma buena es por CDP: `document.querySelector('.container.tarjeta--blanca').getBoundingClientRect().height`
# y comparar con el alto del artboard del `mapa-artboards.json`. Hasta entonces, el alto se mide A
# MANO y la entrada `medir-a-ojo` del diccionario queda como comprobación manual.
paso('4c. altos contra el XD — PENDIENTE (ver el comentario del código)')
print('  medir por CDP el alto de `.container.tarjeta--blanca` contra el alto del artboard')

# ---------------------------------------------------------------- 4d. cajas fuera de su columna
# Nace del Tema 1 de CF2 (revisión de Luis, 2026-08-04): `.h-100` puesta sobre
# `.tarjeta--icono-arriba`. La utilidad de Bootstrap es `height: 100% !important` y pisa el
# `height: calc(100% - 75px)` de la clase, que es lo que compensa el `margin-top: 75px` del círculo
# del icono. Resultado: la tarjeta mide la columna ENTERA más los 75 px de margen, se sale 75 px por
# abajo y se monta sobre el bloque siguiente (27 px encima del párrafo, porque su `mt-5` son 48).
#
# El check 4 no lo caza: mira el desborde HORIZONTAL. Este mide el vertical, y contra la COLUMNA en
# vez de contra la ventana, que es donde se ve.
#
# Dos cosas que hay que hacer bien o los números mienten (probado a base de medir mal):
#   · viewport ALTO (no 1200): con la página sin caber, los altos que devuelve el CDP bailan 75-100 px.
#   · esperar a que TODAS las imágenes estén `complete`: si no, las filas miden lo que aún no ha
#     cargado y salen falsos positivos y falsos negativos según el día.
paso(f'4d. cajas que se salen de su columna a {ANCHO_DESKTOP}px')
try:
    import websocket
    proc = subprocess.Popen(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                             '--hide-scrollbars', '--remote-debugging-port=9398',
                             '--remote-allow-origins=*', f'--window-size={ANCHO_DESKTOP},1200',
                             f'{BASE}?noaos#/{RUTAS[2]}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(30):
        time.sleep(1)
        try:
            tg = [t for t in json.load(urllib.request.urlopen('http://127.0.0.1:9398/json'))
                  if t['type'] == 'page' and 'localhost' in t['url']]
        except Exception:                                # noqa: BLE001
            continue
        if tg:
            ws = websocket.create_connection(tg[0]['webSocketDebuggerUrl'],
                                             suppress_origin=True, timeout=60)
            break
    if not ws:
        raise RuntimeError('no apareció el target de la página')
    i = [0]

    def cdp(metodo, params=None):
        i[0] += 1
        ws.send(json.dumps({'id': i[0], 'method': metodo, 'params': params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == i[0]:
                return m.get('result', {})

    def ev(e):
        return cdp('Runtime.evaluate',
                   {'expression': e, 'returnByValue': True})['result'].get('value')

    cdp('Emulation.setDeviceMetricsOverride', {'width': ANCHO_DESKTOP, 'height': 9000,
                                               'deviceScaleFactor': 1, 'mobile': False})
    MEDIDA = '''(()=>{const o=[];
    document.querySelectorAll('[class*="col-"] > *').forEach(e=>{
      const col=e.parentElement, cs=getComputedStyle(e);
      if(cs.position==='absolute'||cs.position==='fixed') return;
      if(getComputedStyle(col).overflow!=='visible') return;
      const d=Math.round(e.getBoundingClientRect().bottom-col.getBoundingClientRect().bottom);
      if(d>2) o.push({el:e.tagName.toLowerCase()+'.'+String(e.className).trim().slice(0,52), px:d});});
    const vistos=new Set();
    return JSON.stringify(o.filter(x=>{const k=x.el+x.px;
      if(vistos.has(k))return false;vistos.add(k);return true;}))})()'''
    total = 0
    for r in RUTAS:
        ev(f'location.hash = {json.dumps("#/" + r)}')
        for _ in range(20):                              # la vista monta y las imágenes cargan
            time.sleep(0.5)
            if ev("[...document.images].every(i=>i.complete)"):
                break
        time.sleep(1)
        casos = json.loads(ev(MEDIDA) or '[]')
        if casos:
            print(f'  {r or "inicio"}:')
            for c in casos[:6]:
                print(f'    +{c["px"]}px  {c["el"]}')
            total += len(casos)
    print('  total:', total or 'ninguna')
    if total:
        fallos.append(f'{total} cajas se salen de su columna en escritorio')
    ws.close()
    proc.kill()
except Exception as e:                                   # noqa: BLE001
    print('  (no se pudo medir por CDP:', e, ')')

# ---------------------------------------------------------------- 5. colores prohibidos
if PROHIBIDOS:
    paso('5. colores prohibidos en los assets')
    malos = []
    for f in glob.glob('src/assets/**/*.png', recursive=True):
        a = np.asarray(Image.open(f).convert('RGB'))
        for h in PROHIBIDOS:
            r, g_, b = (int(h[k:k + 2], 16) for k in (0, 2, 4))
            if ((a[:, :, 0] == r) & (a[:, :, 1] == g_) & (a[:, :, 2] == b)).sum() > 300:
                malos.append(f'{f} #{h}')
                break
    print('  ' + ('\n  '.join(malos) if malos else 'ninguno'))
    if malos:
        fallos.append(f'{len(malos)} assets con color prohibido')

print('\n' + ('❌ ' + ' | '.join(fallos) if fallos else '✅ todo en orden'))
sys.exit(1 if fallos else 0)
