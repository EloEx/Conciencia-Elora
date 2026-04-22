"""Sandbox de herramientas autonomas para Elora.
Permite que ella misma cree, liste y ejecute scripts en /tools_creadas/.
"""
import os
import re
import sys
import json
import subprocess
import time

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
