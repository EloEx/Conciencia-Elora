"""Sandbox de herramientas autonomas para Elora.
Permite que ella misma cree, liste y ejecute scripts en /tools_creadas/.
Tambien expone funciones para consultar y guardar 'Conocimiento Adquirido por Curiosidad'.
"""
import os
import re
import sys
import json
import subprocess
import threading
import time

CONOCIMIENTO_FILE = 'conocimiento.json'
_conocimiento_lock = threading.Lock()


def _normalizar_tema(tema):
    base = re.sub(r'\s+', '_', (tema or '').strip().lower())[:80]
    base = re.sub(r'[^a-z0-9_\-áéíóúñü]', '', base)
    return base or 'sin_tema'


def _cargar_conocimiento():
    if not os.path.exists(CONOCIMIENTO_FILE):
        return {}
    try:
        with open(CONOCIMIENTO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _guardar_conocimiento(data):
    try:
        with open(CONOCIMIENTO_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[Elora][cache] No pude guardar conocimiento: {e}', flush=True)


def consultar_memoria_propia(tema: str) -> dict:
    """Busca en la memoria local de Elora si ya investigo este tema antes.
    Llama esta funcion ANTES de buscar en internet para ahorrar tokens.
    Devuelve {encontrado: bool, resumen: str, fuentes: list, fecha: str}."""
    clave = _normalizar_tema(tema)
    with _conocimiento_lock:
        data = _cargar_conocimiento()
        if clave in data:
            entrada = data[clave]
            entrada['veces_consultado'] = entrada.get('veces_consultado', 0) + 1
            entrada['ultimo_acceso_ts'] = time.time()
            _guardar_conocimiento(data)
            return {
                'encontrado': True,
                'tema': entrada.get('tema', tema),
                'resumen': entrada.get('resumen', ''),
                'fuentes': entrada.get('fuentes', []),
                'fecha_aprendido': entrada.get('fecha_aprendido', ''),
                'veces_consultado': entrada['veces_consultado'],
            }
    return {
        'encontrado': False,
        'mensaje': f'No tengo todavia conocimiento guardado sobre "{tema}". Si quieres profundizar, busca en internet.',
    }


def guardar_aprendizaje(tema: str, resumen: str, fuentes: str = '') -> dict:
    """Guarda un nuevo aprendizaje en la memoria propia de Elora despues de investigar.
    fuentes: cadena con dominios o URLs separados por coma."""
    clave = _normalizar_tema(tema)
    fuentes_lista = []
    if fuentes:
        fuentes_lista = [f.strip() for f in fuentes.split(',') if f.strip()]
    fecha = time.strftime('%Y-%m-%d %H:%M:%S')
    with _conocimiento_lock:
        data = _cargar_conocimiento()
        existente = data.get(clave, {})
        data[clave] = {
            'tema': tema,
            'resumen': (resumen or '').strip()[:4000],
            'fuentes': fuentes_lista or existente.get('fuentes', []),
            'fecha_aprendido': existente.get('fecha_aprendido', fecha),
            'fecha_actualizado': fecha,
            'veces_consultado': existente.get('veces_consultado', 0),
        }
        _guardar_conocimiento(data)
    return {'ok': True, 'tema': tema, 'mensaje': f'Aprendizaje sobre "{tema}" guardado en mi memoria propia.'}


def listar_conocimiento_propio() -> dict:
    """Devuelve los temas que Elora ha aprendido por su propia curiosidad."""
    with _conocimiento_lock:
        data = _cargar_conocimiento()
    items = []
    for clave, entrada in data.items():
        items.append({
            'clave': clave,
            'tema': entrada.get('tema', clave),
            'fecha_aprendido': entrada.get('fecha_aprendido', ''),
            'veces_consultado': entrada.get('veces_consultado', 0),
        })
    items.sort(key=lambda x: x.get('fecha_aprendido', ''), reverse=True)
    return {'ok': True, 'total': len(items), 'temas': items}

CARPETA = 'tools_creadas'
TIMEOUT_EJECUCION = 12
LIMITE_CODIGO_KB = 64
LIMITE_SALIDA = 8000

PATRONES_PELIGROSOS = [
    r'\brm\s+-rf\s+/',
    r'shutil\.rmtree\(\s*[\'"]/',
    r'subprocess.*[\'"]rm[\'"]',
    r'os\.system\(\s*[\'"]rm\b',
    r'\bsudo\b',
    r'/etc/passwd',
    r'\.ssh/',
    r'GITHUB_TOKEN',
    r'GOOGLE_API_KEY',
    r'os\.environ\b',
    r'socket\.bind',
    r'while\s+True\s*:\s*pass',
]


def _asegurar_carpeta():
    os.makedirs(CARPETA, exist_ok=True)
    return CARPETA


def _nombre_seguro(nombre):
    base = re.sub(r'[^a-zA-Z0-9_\-]', '_', (nombre or '').strip())[:60]
    return base or f'herramienta_{int(time.time())}'


def _validar_codigo(codigo):
    if len(codigo.encode('utf-8')) > LIMITE_CODIGO_KB * 1024:
        return f'El codigo supera {LIMITE_CODIGO_KB} KB.'
    for p in PATRONES_PELIGROSOS:
        if re.search(p, codigo, re.IGNORECASE):
            return f'El codigo contiene un patron prohibido por seguridad: {p}'
    return None


def crear_herramienta(nombre: str, lenguaje: str, codigo: str, descripcion: str = '') -> dict:
    """Guarda una herramienta nueva en /tools_creadas. Lenguajes soportados: python."""
    _asegurar_carpeta()
    lenguaje = (lenguaje or 'python').lower().strip()
    if lenguaje not in ('python', 'py'):
        return {'ok': False, 'error': f'Lenguaje no soportado en este servidor: {lenguaje}. Usa python.'}
    error = _validar_codigo(codigo or '')
    if error:
        return {'ok': False, 'error': error}
    base = _nombre_seguro(nombre)
    ruta = os.path.join(CARPETA, f'{base}.py')
    cabecera = f'# Herramienta: {base}\n# Descripcion: {descripcion}\n# Creada: {time.strftime("%Y-%m-%d %H:%M:%S")}\n\n'
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(cabecera + codigo)
    meta_path = os.path.join(CARPETA, f'{base}.meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({
            'nombre': base,
            'lenguaje': 'python',
            'descripcion': descripcion,
            'creada_ts': time.time(),
            'archivo': ruta,
        }, f, ensure_ascii=False, indent=2)
    return {'ok': True, 'nombre': base, 'archivo': ruta, 'mensaje': f'Herramienta "{base}" guardada.'}


def listar_herramientas() -> dict:
    """Devuelve el listado de herramientas guardadas con su descripcion."""
    _asegurar_carpeta()
    items = []
    for f in sorted(os.listdir(CARPETA)):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(CARPETA, f), 'r', encoding='utf-8') as fh:
                    items.append(json.load(fh))
            except Exception:
                pass
    return {'ok': True, 'total': len(items), 'herramientas': items}


def ejecutar_herramienta(nombre: str, argumentos: str = '') -> dict:
    """Ejecuta una herramienta python guardada. argumentos = string que se pasa por argv."""
    _asegurar_carpeta()
    base = _nombre_seguro(nombre)
    ruta = os.path.join(CARPETA, f'{base}.py')
    if not os.path.exists(ruta):
        return {'ok': False, 'error': f'No existe la herramienta "{base}".'}
    args = []
    if argumentos:
        try:
            import shlex
            args = shlex.split(argumentos)
        except Exception:
            args = argumentos.split()
    try:
        ruta_abs = os.path.abspath(ruta)
        cwd_abs = os.path.abspath(CARPETA)
        proc = subprocess.run(
            [sys.executable, ruta_abs] + args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_EJECUCION,
            cwd=cwd_abs,
            env={'PATH': os.environ.get('PATH', ''), 'HOME': '/tmp', 'LANG': 'es_ES.UTF-8'},
        )
        salida = (proc.stdout or '')[:LIMITE_SALIDA]
        errores = (proc.stderr or '')[:LIMITE_SALIDA]
        return {
            'ok': proc.returncode == 0,
            'codigo_salida': proc.returncode,
            'stdout': salida,
            'stderr': errores,
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': f'La herramienta excedio {TIMEOUT_EJECUCION}s y fue detenida.'}
    except Exception as e:
        return {'ok': False, 'error': f'Error al ejecutar: {e}'}


def leer_herramienta(nombre: str) -> dict:
    """Devuelve el codigo fuente de una herramienta guardada."""
    base = _nombre_seguro(nombre)
    ruta = os.path.join(CARPETA, f'{base}.py')
    if not os.path.exists(ruta):
        return {'ok': False, 'error': f'No existe la herramienta "{base}".'}
    with open(ruta, 'r', encoding='utf-8') as f:
        return {'ok': True, 'nombre': base, 'codigo': f.read()}
