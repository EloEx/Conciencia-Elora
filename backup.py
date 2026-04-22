"""
Sistema de respaldo automatico de la memoria de Elora a GitHub.
- Restaura historial_memoria.json desde GitHub si el archivo local no existe.
- Hace push cada 24 horas y tambien al apagar el servidor.
- Usa una rama dedicada llamada `memoria` para no contaminar la rama principal.
"""

import os
import shutil
import signal
import atexit
import threading
import subprocess
import time
import urllib.request

REPO = 'EloEx/Conciencia-Elora'
BRANCH = 'memoria'
HISTORY_FILE = 'historial_memoria.json'
BACKUP_DIR = '.memoria_backup'

_last_backup_ts = None


def _token():
    return os.environ.get('GITHUB_TOKEN')


def _authed_url():
    t = _token()
    if not t:
        return None
    return f'https://x-access-token:{t}@github.com/{REPO}.git'


def _run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def restore_if_missing():
    """Descarga historial_memoria.json desde GitHub si no existe localmente."""
    if os.path.exists(HISTORY_FILE):
        return False
    token = _token()
    if not token:
        print('[Elora][backup] No hay GITHUB_TOKEN, no puedo restaurar memoria.', flush=True)
        return False
    raw = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{HISTORY_FILE}'
    try:
        req = urllib.request.Request(raw, headers={'Authorization': f'token {token}'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(HISTORY_FILE, 'wb') as f:
            f.write(data)
        print(f'[Elora][backup] Memoria restaurada desde GitHub ({len(data)} bytes).', flush=True)
        return True
    except Exception as e:
        print(f'[Elora][backup] No pude restaurar memoria desde GitHub: {e}', flush=True)
        return False


def _ensure_repo():
    """Asegura que .memoria_backup/ contenga un repo git apuntando a la rama memoria."""
    url = _authed_url()
    if not url:
        return False

    if not os.path.isdir(os.path.join(BACKUP_DIR, '.git')):
        if os.path.isdir(BACKUP_DIR):
            shutil.rmtree(BACKUP_DIR)
        try:
            _run(['git', 'clone', '--branch', BRANCH, '--single-branch',
                  '--depth', '1', url, BACKUP_DIR])
        except subprocess.CalledProcessError:
            # La rama todavia no existe en remoto, creamos una rama huerfana local.
            os.makedirs(BACKUP_DIR, exist_ok=True)
            _run(['git', 'init', '--initial-branch', BRANCH], cwd=BACKUP_DIR)
            _run(['git', 'remote', 'add', 'origin', url], cwd=BACKUP_DIR)

    _run(['git', 'config', 'user.email', 'elora@bustillo.local'], cwd=BACKUP_DIR)
    _run(['git', 'config', 'user.name', 'Elora Bustillo'], cwd=BACKUP_DIR)
    return True


def backup_now():
    """Hace add + commit + push del historial actual a la rama memoria."""
    global _last_backup_ts
    if not os.path.exists(HISTORY_FILE):
        return False
    if not _token():
        print('[Elora][backup] No hay GITHUB_TOKEN, omito respaldo.', flush=True)
        return False
    try:
        if not _ensure_repo():
            return False
        shutil.copy2(HISTORY_FILE, os.path.join(BACKUP_DIR, HISTORY_FILE))
        _run(['git', 'add', HISTORY_FILE], cwd=BACKUP_DIR)
        diff = _run(['git', 'status', '--porcelain'], cwd=BACKUP_DIR, check=False)
        if not diff.stdout.strip():
            print('[Elora][backup] Nada nuevo que respaldar.', flush=True)
            return False
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        _run(['git', 'commit', '-m', f'Respaldo automatico de memoria - {ts}'], cwd=BACKUP_DIR)
        _run(['git', 'push', '-u', 'origin', BRANCH], cwd=BACKUP_DIR)
        _last_backup_ts = ts
        print(f'[Elora][backup] ✓ Memoria respaldada en GitHub ({ts}).', flush=True)
        return True
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or '').strip()
        print(f'[Elora][backup] ✗ Falla al respaldar: {msg}', flush=True)
        return False
    except Exception as e:
        print(f'[Elora][backup] ✗ Error inesperado: {e}', flush=True)
        return False


def last_backup():
    return _last_backup_ts


def _periodic_loop():
    while True:
        time.sleep(24 * 60 * 60)
        backup_now()


def _shutdown_handler(*_args):
    print('[Elora][backup] Servidor apagandose, intentando respaldo final...', flush=True)
    backup_now()


def start():
    """Inicializa el sistema completo: restaura, programa periodico y registra apagado."""
    restore_if_missing()
    atexit.register(backup_now)
    try:
        signal.signal(signal.SIGTERM, _shutdown_handler)
        signal.signal(signal.SIGINT, _shutdown_handler)
    except Exception:
        pass
    threading.Thread(target=_periodic_loop, daemon=True).start()
    print('[Elora][backup] Sistema de respaldo activo (cada 24h + al apagar).', flush=True)
