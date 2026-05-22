-- ============================================================
-- SQL para el sistema RAG de Elora — ejecutar en Supabase SQL Editor
-- Una sola vez. Seguro de re-ejecutar (IF NOT EXISTS en todo).
-- ============================================================

-- 1. Tabla de memoria vectorial (texto plano, sin pgvector)
CREATE TABLE IF NOT EXISTS memoria_vectorial (
    id          BIGSERIAL PRIMARY KEY,
    role        TEXT NOT NULL CHECK (role IN ('user', 'model')),
    text        TEXT NOT NULL,
    ts          DOUBLE PRECISION NOT NULL DEFAULT 0,
    creado_en   TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Índice de texto completo en español (tsvector generado)
ALTER TABLE memoria_vectorial
    ADD COLUMN IF NOT EXISTS fts_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('spanish', text)) STORED;

CREATE INDEX IF NOT EXISTS idx_mv_fts
    ON memoria_vectorial USING GIN (fts_vector);

-- 3. Índice por timestamp para ordenación rápida
CREATE INDEX IF NOT EXISTS idx_mv_ts
    ON memoria_vectorial (ts DESC);

-- 4. Función RPC de búsqueda FTS (llamada desde Python via supabase.rpc)
CREATE OR REPLACE FUNCTION buscar_fts(
    q      TEXT,
    limite INT DEFAULT 6
)
RETURNS TABLE (role TEXT, text TEXT, ts FLOAT)
LANGUAGE sql STABLE
SECURITY DEFINER
AS $$
    SELECT
        role,
        text,
        ts::float
    FROM memoria_vectorial
    WHERE fts_vector @@ plainto_tsquery('spanish', q)
    ORDER BY ts_rank(fts_vector, plainto_tsquery('spanish', q)) DESC,
             ts DESC
    LIMIT limite;
$$;

-- 5. (Opcional) Si en el futuro activas pgvector, añade la columna de embedding:
-- ALTER TABLE memoria_vectorial ADD COLUMN IF NOT EXISTS embedding vector(384);
-- CREATE INDEX IF NOT EXISTS idx_mv_emb
--     ON memoria_vectorial USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- (Y luego cambia buscar_fts por buscar_similar con cosine distance)

-- Verificación rápida:
SELECT 'Setup RAG completado' AS status,
       (SELECT COUNT(*) FROM memoria_vectorial) AS mensajes_indexados;
