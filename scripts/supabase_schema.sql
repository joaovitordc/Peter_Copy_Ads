-- ─────────────────────────────────────────────────────────────────────────
-- Schema do Peter dentro do banco Supabase compartilhado com EllO ERP.
-- Rodar UMA vez no SQL Editor do Supabase do projeto EllO ERP
-- (https://supabase.com/dashboard > EllO ERP > SQL Editor > New query >
--  colar abaixo > Run).
--
-- Convencao: todas as tabelas do Peter levam prefixo `peter_` pra coexistir
-- limpa com as tabelas do ERP no mesmo schema public.
-- ─────────────────────────────────────────────────────────────────────────

-- DROP existente (caso esquema antigo com coluna `loja` tenha sido criado).
-- Operador confirmou que a tabela esta vazia em 2026-05-18.
DROP TABLE IF EXISTS peter_skus_em_uso;

-- Tabela principal do Peter: registra SKUs ja "reservados" pra evitar
-- conflito ao gerar produto novo. 1 linha = 1 SKU base (ex: "AnimaisFofos"),
-- com a lista de lojas onde aquele nome ja foi cadastrado.
--
-- Multi-loja: a mesma arte pode estar cadastrada em PPJ + iPaper + AllQuadros
-- (cada loja tem shop_id diferente na Shopee). A coluna `lojas_cadastradas`
-- guarda o conjunto. Quando o Peter cadastra um produto novo, faz MERGE
-- (adiciona a loja ao array sem duplicar). Quando descarta via /api/descartar,
-- remove a loja do array — se ficar vazio, deleta a linha (libera o nome).
--
-- Semantica de conflito: o Peter ainda trata como conflito global. Se o nome
-- `Bailarina` ja esta em uso em qualquer loja, o LLM/sufixo NoN forca um
-- nome diferente pro proximo cadastro. Isso evita reuso acidental sem
-- intencao explicita do operador.
CREATE TABLE peter_skus_em_uso (
    sku_base            TEXT      PRIMARY KEY,                          -- ex: "Salmo4610", "AnimaisFofos"
    lojas_cadastradas   TEXT[]    NOT NULL DEFAULT '{}',                 -- ex: {PPJ, iPaper, AllQuadros}
    tipo                TEXT      NOT NULL,                              -- Q1 | KIT2 | KIT3 | QPERS | FAIXA | MOLD
    display             TEXT,                                            -- nome legivel (ex: "Animais Fofos")
    criado_em           DATE      NOT NULL DEFAULT CURRENT_DATE
);

-- Indices uteis pra queries de relatorio/filtro futuras.
-- Index GIN no array pra suportar consultas tipo `WHERE 'PPJ' = ANY(lojas_cadastradas)`.
CREATE INDEX idx_peter_skus_lojas ON peter_skus_em_uso USING GIN (lojas_cadastradas);
CREATE INDEX idx_peter_skus_tipo  ON peter_skus_em_uso (tipo);

-- RLS: ativada por default no Supabase. Backend Peter usa SERVICE_ROLE_KEY
-- que bypassa RLS, entao podemos manter sem policies definidas.
-- Se um dia quisermos expor leitura pro front via ANON_KEY, criar policies aqui.
ALTER TABLE peter_skus_em_uso ENABLE ROW LEVEL SECURITY;
