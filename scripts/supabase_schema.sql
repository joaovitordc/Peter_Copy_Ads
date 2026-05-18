-- ─────────────────────────────────────────────────────────────────────────
-- Schema do banco Supabase do Peter (uso inicial: SKUs em uso).
-- Rodar UMA vez no SQL Editor do Supabase (https://supabase.com/dashboard
-- > projeto > SQL Editor > New query > colar abaixo > Run).
-- ─────────────────────────────────────────────────────────────────────────

-- Tabela principal: registra SKUs ja "reservados" pra evitar conflito ao
-- gerar produto novo. 1 linha = 1 SKU base (ex: "AnimaisFofos"). O prefixo
-- de tipo (Q1_, KIT2_, KIT3_) fica IMPLICITO na coluna tipo — multiplos
-- prefixos sobre o mesmo nome_base ainda contam como 1 entrada (design
-- global atual).
CREATE TABLE IF NOT EXISTS skus_em_uso (
    sku_base   TEXT        PRIMARY KEY,            -- ex: "Salmo4610", "AnimaisFofos"
    loja       TEXT        NOT NULL,               -- PPJ | iPaper | AllQuadros | DecorKids
    tipo       TEXT        NOT NULL,               -- Q1 | KIT2 | KIT3 | QPERS | FAIXA | MOLD
    display    TEXT,                                -- nome legivel (ex: "Animais Fofos")
    criado_em  DATE        NOT NULL DEFAULT CURRENT_DATE
);

-- Indices uteis pra queries de relatorio/filtro futuras:
CREATE INDEX IF NOT EXISTS idx_skus_loja ON skus_em_uso (loja);
CREATE INDEX IF NOT EXISTS idx_skus_tipo ON skus_em_uso (tipo);

-- RLS: ativada por default no Supabase. Backend Peter usa SERVICE_ROLE_KEY
-- que bypassa RLS, entao podemos manter sem policies definidas.
-- Se um dia quisermos expor leitura pro front via ANON_KEY, criar policies aqui.
ALTER TABLE skus_em_uso ENABLE ROW LEVEL SECURITY;
