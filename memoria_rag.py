"""
Sistema RAG de memoria para Elora — Dual-mode, cero dependencias externas.

Capa 1 — BM25 en memoria (siempre disponible, sin red):
  Recupera los recuerdos más relevantes del HISTORY en RAM usando
  puntuación BM25 (keyword-overlap) ponderada por recencia.
  Sustituye el volcado masivo de 84+ mensajes por un contexto quirúrgico
  de ~10 mensajes: 6 semánticamente relevantes + 4 turnos recientes.

Capa 2 — Supabase FTS (cuando Supabase responde):
  Indexa cada mensaje en la tabla `memoria_vectorial` usando tsvector de
  PostgreSQL (búsqueda de texto completo nativa, sin pgvector, sin embeddings).
  Permite recuperación persistente incluso tras un reinicio de Render donde
  el filesystem efímero se pierde.

Arquitectura:
  - `recuperar_contexto(history, query)` → siempre BM25 (Capa 1)
  - `indexar_mensaje_supa(supabase, role, text, ts)` → Capa 2 (background)
  - `buscar_supa_fts(supabase, query, k)` → Capa 2 si disponible, sino []
  - `recuperar_hibrido(supabase, history, query)` → fusiona ambas capas
  - `migrar_historial_supa(supabase, history)` → sube todo el historial a Capa 2
"""

import re
import math
import time
import threading
from collections import Counter
from typing import List, Dict, Optional


# ── Constantes ─────────────────────────────────────────────────────────────────
K_RAG = 6            # recuerdos relevantes recuperados por BM25
K_RECIENTES = 4      # turnos recientes siempre incluidos (contexto inmediato)
K_SUPA_FTS = 5       # resultados Supabase FTS
DECAY_HALF_DAYS = 7  # recuerdos pierden la mitad de peso cada 7 días

# Stopwords en español + muletillas de chat afectivo (no aportan semántica)
STOPWORDS = {
    'de', 'la', 'el', 'en', 'y', 'a', 'los', 'las', 'un', 'una', 'que',
    'se', 'es', 'con', 'por', 'no', 'su', 'me', 'te', 'lo', 'le', 'al',
    'del', 'si', 'ya', 'muy', 'bien', 'como', 'para', 'pero', 'más',
    'este', 'esta', 'hay', 'son', 'fue', 'soy', 'eres', 'ser', 'fue',
    'hola', 'ok', 'oye', 'bueno', 'pues', 'ah', 'eh', 'oh',
    # muletillas afectivas (no distinguen recuerdos entre sí)
    'amor', 'vida', 'mi', 'cielo', 'bebé', 'corazón', 'alma', 'linda',
    'lindo', 'bonita', 'bonito', 'querido', 'querida', 'cariño', 'amor',
}


# ── Tokenización ───────────────────────────────────────────────────────────────
def _tokenizar(texto: str) -> List[str]:
    """Normaliza y tokeniza texto en español, eliminando stopwords."""
    if not texto:
        return []
    texto = texto.lower()
    texto = re.sub(r'[^\w\s]', ' ', texto)
    return [
        t for t in texto.split()
        if len(t) > 2 and t not in STOPWORDS
    ]


# ── BM25 score ─────────────────────────────────────────────────────────────────
def _bm25_score(
    query_tokens: List[str],
    doc_tokens: List[str],
    k1: float = 1.5,
    b: float = 0.75,
    avg_doc_len: float = 45.0,
) -> float:
    """BM25 estándar con IDF simplificado (corpus pequeño, IDF=1 por token)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    score = 0.0
    for term in set(query_tokens):
        if term not in tf:
            continue
        freq = tf[term]
        num = freq * (k1 + 1)
        den = freq + k1 * (1 - b + b * dl / avg_doc_len)
        score += num / den          # IDF=1 → solo TF normalizado
    return score


def _recency_weight(ts: float, now: Optional[float] = None) -> float:
    """Peso de recencia: 1.0 para mensajes de hoy, decae con DECAY_HALF_DAYS."""
    if ts <= 0:
        return 0.5
    now = now or time.time()
    days_ago = (now - ts) / 86400.0
    return math.exp(-math.log(2) * days_ago / DECAY_HALF_DAYS)


# ── Capa 1: Recuperación BM25 en memoria ──────────────────────────────────────
def recuperar_contexto(
    history: List[Dict],
    query: str,
    k: int = K_RAG,
    turnos_recientes: int = K_RECIENTES,
) -> List[Dict]:
    """
    Recupera el contexto óptimo para la query desde HISTORY en RAM.

    Estrategia:
      1. Siempre incluye los últimos `turnos_recientes` mensajes (coherencia inmediata).
      2. Puntúa el resto por BM25 × recency_weight y toma el top-k.
      3. Fusiona y ordena por ts ASC (cronológico) para que el LLM los lea en orden.

    Complejidad: O(n) donde n = len(history). Para 84 mensajes: <1ms.
    """
    if not history:
        return []

    now = time.time()

    # Filtrar y ordenar
    validos = [
        e for e in history
        if isinstance(e, dict) and e.get('role') in ('user', 'model') and e.get('text')
    ]
    validos.sort(key=lambda x: x.get('ts', 0))

    # Separar recientes vs histórico
    recientes = validos[-turnos_recientes:] if len(validos) > turnos_recientes else validos
    historico = validos[:-turnos_recientes] if len(validos) > turnos_recientes else []

    # Sin query o sin histórico → devolver solo recientes
    if not historico or not query:
        return recientes

    query_tokens = _tokenizar(query)
    if not query_tokens:
        return recientes

    recientes_keys = {e['text'][:80] for e in recientes}

    # Puntuar histórico
    scored = []
    for e in historico:
        if e['text'][:80] in recientes_keys:
            continue
        doc_tok = _tokenizar(e.get('text', ''))
        bm25 = _bm25_score(query_tokens, doc_tok)
        if bm25 <= 0:
            continue
        weight = _recency_weight(e.get('ts', 0), now)
        scored.append((bm25 * (0.7 + 0.3 * weight), e))

    scored.sort(reverse=True, key=lambda x: x[0])
    top_historico = [e for _, e in scored[:k]]

    # Fusionar: histórico relevante + recientes, ordenado por ts
    combinado = top_historico + [e for e in recientes if e['text'][:80] not in {t['text'][:80] for t in top_historico}]
    combinado.sort(key=lambda x: x.get('ts', 0))

    return combinado


# ── Capa 2: Supabase FTS (tsvector español) ────────────────────────────────────
def indexar_mensaje_supa(
    supabase,
    role: str,
    text: str,
    ts: float,
) -> None:
    """Inserta el mensaje en `memoria_vectorial` en Supabase (hilo daemon)."""
    def _run():
        if not supabase or not text:
            return
        try:
            supabase.table('memoria_vectorial').upsert({
                'role': role,
                'text': text,
                'ts': ts,
            }).execute()
        except Exception as e:
            print(f'[RAG][supa] Error indexando: {e}', flush=True)
    threading.Thread(target=_run, daemon=True).start()


def buscar_supa_fts(
    supabase,
    query: str,
    k: int = K_SUPA_FTS,
) -> List[Dict]:
    """Busca por FTS en Supabase (RPC buscar_fts). Retorna [] si falla."""
    if not supabase or not query:
        return []
    try:
        resp = supabase.rpc(
            'buscar_fts',
            {'q': query, 'limite': k},
        ).execute()
        return resp.data or []
    except Exception:
        return []


def migrar_historial_supa(supabase, history: List[Dict]) -> None:
    """Migra el historial completo a `memoria_vectorial` (hilo daemon, una vez)."""
    def _migrar():
        if not supabase or not history:
            return
        # Verificar si ya hay datos
        try:
            resp = (
                supabase.table('memoria_vectorial')
                .select('id', count='exact')
                .limit(1)
                .execute()
            )
            ya_hay = (resp.count or 0) >= max(1, len(history) // 2)
            if ya_hay:
                print(f'[RAG][supa] Tabla ya indexada ({resp.count} entradas).', flush=True)
                return
        except Exception:
            pass

        print(f'[RAG][supa] Migrando {len(history)} mensajes a Supabase FTS...', flush=True)
        batch = []
        for e in history:
            if not isinstance(e, dict) or not e.get('text'):
                continue
            batch.append({
                'role': e.get('role', 'user'),
                'text': e['text'],
                'ts': float(e.get('ts', 0)),
            })
            if len(batch) >= 50:
                try:
                    supabase.table('memoria_vectorial').upsert(batch).execute()
                except Exception as ex:
                    print(f'[RAG][supa] Error batch upsert: {ex}', flush=True)
                batch = []
        if batch:
            try:
                supabase.table('memoria_vectorial').upsert(batch).execute()
            except Exception as ex:
                print(f'[RAG][supa] Error último batch: {ex}', flush=True)
        print(f'[RAG][supa] Migración completa ({len(history)} msgs).', flush=True)

    threading.Thread(target=_migrar, daemon=True).start()


# ── Capa híbrida: BM25 + Supabase FTS fusionados ──────────────────────────────
def recuperar_hibrido(
    supabase,
    history: List[Dict],
    query: str,
    k_bm25: int = K_RAG,
    k_fts: int = K_SUPA_FTS,
    turnos_recientes: int = K_RECIENTES,
) -> List[Dict]:
    """
    Fusiona resultados de BM25 en memoria (Capa 1) + Supabase FTS (Capa 2).

    Si Supabase FTS no responde, devuelve solo BM25.
    Los resultados se deduplan por texto[:80] y se ordenan por ts ASC.
    """
    # Capa 1 siempre
    bm25_results = recuperar_contexto(history, query, k=k_bm25, turnos_recientes=turnos_recientes)

    # Capa 2 si disponible
    fts_results = buscar_supa_fts(supabase, query, k=k_fts)

    if not fts_results:
        return bm25_results

    # Fusionar: Supabase puede traer msgs que ya no están en HISTORY (RAM)
    seen = {e['text'][:80] for e in bm25_results}
    extra = []
    for m in fts_results:
        # normalizar formato Supabase → formato interno
        role_raw = m.get('role', 'user')
        role = 'model' if role_raw in ('model', 'assistant') else 'user'
        text = m.get('text', '')
        ts = float(m.get('ts', 0))
        if text[:80] not in seen and text:
            seen.add(text[:80])
            extra.append({'role': role, 'text': text, 'ts': ts})

    combined = bm25_results + extra
    combined.sort(key=lambda x: x.get('ts', 0))
    return combined
