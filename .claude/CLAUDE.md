# Peter_Copy_Ads

Automacao de cadastro de produtos copiados da Etsy para a Shopee Brasil e ERP (Tiny).

## Objetivo
Dado um arquivo Excel com links de anuncios da Etsy pre-selecionados, o fluxo:
1. Extrai os dados de cada anuncio (titulo, 3 primeiras imagens)
2. Hospeda as imagens no ImgBB (URLs publicas .jpg/.png)
3. Gera planilha pronta para upload em massa na **Shopee** (`planilhas_geradas_shopee/`)
4. Gera planilha para importacao no **ERP Tiny** (`planilhas_geradas_erp/`)
5. Gera planilha enxuta para o **Kakashi** (sistema externo de geracao de PDFs)

## Integracao Kakashi
O Kakashi e um sistema externo que gera PDFs prontos para impressao a partir do mockup
principal de cada anuncio. A cada lote, o pipeline gera automaticamente uma 3a planilha
no mesmo `output_dir` do job:

- **Arquivo:** `kakashi_<loja>_<YYYY-MM-DD>.xlsx`
- **Template base:** `planilhas_padrao/kakashi_art_generator.xlsx`
- **Estrutura:** 3 colunas — `Código (SKU)`, `Descrição`, `URL imagem 1`
- **Granularidade:** 1 linha por anuncio (nao por variacao). Se o anuncio tem 8 variacoes
  na Shopee, ele aparece como 1 linha unica aqui.
- **`Código (SKU)`:** SKU base no formato `<TIPO>_<NomeCurto>` (ex: `Q1_OliveiraGetsemani`)
- **`URL imagem 1`:** URL direta do `imagem_capa` ImgBB (.jpg/.png/.webp)
- **Validacao:** linhas com `imagem_capa` invalida sao omitidas e reportadas em avisos.

Uso: o usuario clica em "Planilha Kakashi" no card de resultado do frontend, baixa o XLSX
e faz upload no sistema Kakashi.

### Sincronizacao de descricao com ERP

A descricao gerada para o Kakashi (coluna B) usa o **mesmo formato** da
descricao do produto pai no ERP (`build_erp_template.py`):

| Tipo | Descricao (igual no ERP e Kakashi) |
|------|-------------------------------------|
| Q1   | `Quadro - {nome_display}`           |
| KIT2 | `Kit 2 Quadros - {nome_display}`    |
| KIT3 | `Kit 3 Quadros - {nome_display}`    |
| KIT5 | `Kit 5 Quadros - {nome_display}`    |
| KIT6 | `Kit 6 Quadros - {nome_display}`    |
| KIT8 | `Kit 8 Quadros - {nome_display}`    |

Resultado: o PDF gerado pelo Kakashi terá nome identico a descricao do
produto pai no ERP, permitindo auditoria visual rapida e busca direta na
pasta do Drive. O mapping `TIPO_NOME` esta centralizado em
`scripts/build_erp_template.py:50-57` e e reutilizado por
`scripts/export_kakashi.py` via import.

## Como Rodar

### Configuracao inicial (uma vez)
```bash
python scripts/setup.py
```
Instala dependencias e valida o `.env` com a chave ImgBB.

### Executar o fluxo
Diga ao Claude:
```
processar planilhas_links_artes/links_artes_PPJ_090426.xlsx para loja PPJ
```
Ou invoque `/etsy-to-shopee`.

## Dependencias Python
- `openpyxl` - ler/escrever .xlsx
- `xlrd` - ler .xls (template ERP)
- `requests` - chamadas HTTP (ImgBB API)
- `python-dotenv` - ler .env

## Configuracao
- `.env` → `IMGBB_API_KEY=sua_chave_aqui`
  Obter chave gratuita em: https://api.imgbb.com/
- `.env.example` → modelo das chaves opcionais (Firecrawl, Etsy)
- `config.json` → defaults por loja (categoria Shopee, peso, dimensoes, etc.)

## Modos de planilha de entrada

**1. "Links + Imagens"** (sempre disponivel)
Planilha com URL Etsy + 4 URLs de imagens ja escolhidas pelo usuario. Nao precisa
de chave alem do ImgBB.

**2. "So Links"** (precisa de uma das chaves abaixo)
Planilha apenas com URLs Etsy. Sistema busca titulo + 4 imagens automaticamente.

  - **Firecrawl** (`FIRECRAWL_API_KEY` no .env, recomendado)
    - Scraping autonomo via agent (~3 min/produto, paralelizado em ondas de 5)
    - Free tier: 5 calls/dia (suficiente para testes; produção precisa upgrade)
    - https://www.firecrawl.dev/
  - **Etsy Open API** (`ETSY_API_KEY` no .env, alternativa)
    - Mais rapido (segundos por produto) e mais estavel quando aprovado
    - Requer aprovacao manual da Etsy (pode demorar ou ser rejeitada)
    - https://www.etsy.com/developers/register

Se ambas as chaves estiverem configuradas, **Firecrawl tem prioridade**. Para alternar
para a Etsy API, basta remover `FIRECRAWL_API_KEY` do `.env`.

Falhas parciais no scrape Firecrawl viram avisos no card de resultado — pipeline
nao aborta. Produtos que falharem podem ser completados manualmente no modo
"Links + Imagens" depois.

### Traducao EN→PT e Resolucao de Conflitos de SKU

As Etapas 2.6 (traducao GPT-4o-mini) e 2.7 (resolucao de conflitos de SKU)
rodam em **AMBOS os modos** sempre que `OPENAI_API_KEY` estiver configurada
no `.env`. Isso garante:

- Descricoes limpas e em portugues (ex: "Conjunto de 3 Posteres Cristaos"
  em vez de "De 3 Posteres Cristaos" truncado pelo filtro SEO da
  `gerar_nome_arte`)
- **Tipo (Q1/KITN) retornado pelo LLM** explicitamente. Substitui
  `determinar_tipo()` quando tradução tem sucesso. `determinar_tipo()`
  permanece como fallback (com padrões PT adicionados em 28/04/2026).
- SKUs unicos: se a IA gerar um nome ja em uso, o resolver pede outro
  nome ate 3x via LLM, depois adiciona sufixo `No2`, `No3`, etc.

**Custo:** ~US$0.0001 por chamada (~3x mais barato que o Gemini Flash que
foi substituído em 28/04/2026 por instabilidade — 8/39 falhas com erro 503).

### Fix v3 (28/04/2026): tema_loja + anti-generico + sufixo SKU + fix conflito

Validação real do Fix v2 com 39 produtos revelou 4 bugs adicionais resolvidos
nesta iteração:

- **`tema_loja` no `config.json`** — cada loja tem campo de tema/keywords
  (PPJ=religioso/cristão, iPaper=abstrato/Bauhaus, AllQuadros=vintage/floral).
  O LLM recebe esse tema no prompt e usa quando o título Etsy é genérico
  (ex: "Conjunto de 3 Artes de Parede" + tema PPJ → "Conjunto de 3 Artes Cristãs").
- **SEO words PT expandidas no prompt** — "arte de parede", "impressao",
  "decoracao", "para sala/quarto/escritorio/bercario", "digital", "baixar".
- **SKU mais distintivo** — LLM escolhe 2-3 palavras MAIS distintivas
  (não todas), 12-20 chars ideal.
- **Pós-processamento `_limpar_sufixo_sku`** em
  `scripts/traduzir_nome.py:46-58` remove preposições/conjunções/artigos
  no final do SKU PascalCase via regex de palavras reais
  (ex: `JesusEACapturaMilagrosaDe` → `JesusEACapturaMilagrosa`).
  Aplicado antes E depois do cap de 25 chars.
- **Fix bug de conflito SKU** em `_resolver_conflitos_sku`: 2 produtos
  diferentes que viraram o mesmo `nome_curto` agora SEMPRE conflitam,
  mesmo que `nome_display` seja idêntico (era ignorado por heurística
  "se display igual, é o mesmo produto" — não confiável).

A Etapa 2.5 (filtro de quadros via Gemini) **continua exclusiva** do modo
"So Links" — no modo "Links + Imagens" o operador ja pre-selecionou as
4 imagens manualmente na planilha de input, entao filtrar de novo e
desnecessario.

### Fix v4 (28/04/2026)

- **Banidas categorias de produto no display**: Conjunto, Arte/Artes, Poster*,
  Cartaz/es, Imagem/Imagens, Quadro/s, Decoração. LLM agora inventa nome
  temático obrigatoriamente quando título Etsy é genérico.
- **Sanitização de acentos antes da regex**: fix do bug `PosteresF` (Fix v3)
  onde LLM retornou acento por engano e regex ASCII quebrou.
- **Lista SEO PT expandida**: adicionados moderno/a, minimalista, contemporaneo,
  vintage, boho, aesthetic, abstract, colorful e variantes.
- **Tema da loja agora é OBRIGATÓRIO**: prompt mudou de "fallback opcional"
  para "MANDATORY thematic invention" — aceitando que casos raros soarão
  artificiais.

### Fix v5 — Templates Shopee Q1/KIT separados (28/04/2026)

**Bug descoberto:** título Shopee não refletia tipo do produto. Kit 3 saía
como "Quadro Decorativo..." em vez de "Kit 3 Quadros Decorativos...".

**Solução:**
- Cada loja recebeu 2 templates: `titulo_padrao_q1` e `titulo_padrao_kit`
  no `config.json` (campo único `titulo_padrao` foi removido — sem fallback)
- Variação A escolhida (sem "com" ou "Conjunto"):
  `Kit N Quadros Decorativos {seo plural} ... - {nome_arte}`
- Função `_pluralizar_pt()` adicionada em `web/art_name.py` para concordância
  gramatical ("Minimalista" → "Minimalistas", "Moderno" → "Modernos")
- Locuções (ex: "Arte Abstrata" → "Artes Abstratas") tratadas primeiro
- Estrangeiras (Bauhaus, Vintage, Boho) e substantivos invariantes (Natureza,
  Design) mantêm forma original via `_PLURAL_MAP`

**Importante:** título Shopee é isolado de ERP/Kakashi. Pode ser ajustado
livremente para otimizar SEO de plataforma sem afetar gestão de produto.

### Fix v6 — Coluna QUANTIDADE + suporte KIT4/7/8/9 (28/04/2026)

**Bugs descobertos:**
- LLM erra detecção de tipo quando título Etsy é genérico (ex: "Wall Art Set").
  Operador precisa de override manual.
- Sistema só suportava 5 tipos de KIT com preço (KIT2/3/5/6); KIT8 estava nas
  variações mas sem preço (bug latente).

**Mudanças:**
1. Coluna A da planilha de input agora é QUANTIDADE (1 a 9, ou vazio para
   detecção automática). Coluna B passou a ser LINK ETSY (era A antes).
2. Quantidade manual TEM PRIORIDADE sobre LLM e sobre `determinar_tipo()`.
   Lida em [scripts/read_input.py](../scripts/read_input.py) e propagada
   por [web/core.py](../web/core.py) em ambos os modos.
3. Adicionados KIT4, KIT7, KIT8, KIT9 com preços por interpolação linear:
   - KIT4: 30x40 SM R$89,90 / CM R$244,90 — 40x60 SM R$139,90 / CM R$324,90
   - KIT7: 30x40 SM R$149,90 / CM R$399,90 — 40x60 SM R$229,90 / CM R$539,90
   - KIT8: 30x40 SM R$169,90 / CM R$449,90 — 40x60 SM R$259,90 / CM R$609,90
   - KIT9: 30x40 SM R$189,90 / CM R$499,90 — 40x60 SM R$289,90 / CM R$679,90
4. Tamanhos novos KITs: apenas 3040 e 4060 (alinhado com KIT2/5/6 atuais).
5. Padrões de `determinar_tipo()` expandidos para 2-9 quadros (en + pt).
6. `TIPOS_VALIDOS` e `TIPO_NOME` expandidos para incluir KIT4/7/8/9.
7. Endpoint `/api/modelo` em [web/app.py](../web/app.py) agora gera template
   com coluna QUANTIDADE e tooltip de instrução em A1.

**Validação manual:** valores não-numéricos ou fora de 1-9 viram `None` no
parser e disparam aviso `"Quantidade '<raw>' invalida..."` em core.py,
caindo pra detecção automática do LLM.

### Fix v7 — Output Shopee no formato oficial (28/04/2026)

**Antes:** Peter gerava planilha simplificada (`cadastrar_produtos_shopee.xlsx`).
Operador editava manualmente, copiando dados pra template oficial Shopee antes
de subir.

**Agora:** Peter gera direto no template oficial
(`Shopee_mass_upload_2026-04-10_basic_template.xlsx`). Operador sobe direto
na Shopee, sem retrabalho.

**Mudança técnica:**
- `TEMPLATE_PATH` em `scripts/build_shopee_template.py` aponta pra template oficial
- Aba `Planilha1` → `Modelo`
- Dados começam na linha 7 (era 5)
- 53 colunas idênticas em ambos os templates — lógica de preenchimento não mudou
- Abas auxiliares (`Orientação`, `Fazer upload do exemplo`,
  `Intervalo do PP para Encomenda`, `Lista de Modelos de Tabela de M`,
  `HiddenShopBrand`, `HiddenTax`) preservadas — necessárias pra validação Shopee

**Template antigo permanece em `planilhas_padrao/`** como histórico.

### Nova loja DecorKids — decoração infantil (29/04/2026)

Sistema agora suporta **4 lojas**: PPJ, iPaper, AllQuadros e **DecorKids**.

**Diferenças do DecorKids:**
- **Template Shopee** com formato do anúncio concorrente:
  - Q1: `Quadro Decorativo Infantil {seo} | Quarto Bebê Menino e Menina – {nome_arte}`
  - KIT: `Kit {n} Quadros Decorativos Infantil {seo} | Quarto Bebê Menino e Menina – {nome_arte}`
  - "Infantil" singular mesmo em KIT (busca SEO BR é "infantil", não "infantis")
  - Pipe `|` separa o bloco SEO do bloco demográfico
- **Descrição ERP/Kakashi** ganha prefixo `Infantil ` entre `tipo_nome` e
  `nome_display`. Exemplo: `Kit 3 Quadros - Infantil Animais Safari No13`.
  Implementado via novo campo `prefixo_descricao_erp` no `config.json` —
  PPJ/iPaper/AllQuadros têm `""`, DecorKids tem `"Infantil "`.
- **SKU sem prefixo**: `KIT3_AnimaisSafariNo13` (a palavra "Infantil" só
  aparece nas descrições, nunca no SKU).
- **10 temas curados** mapeados em `_extrair_seo_keywords` (DecorKids):
  Safari, Animais Fofos, Natureza Boho, Transporte, Carros, Fundo do Mar,
  Flores e Floral, Arco Iris, Fada, Bailarina.
- **Default `{seo}` vazio** quando nada bate (`defaults["DecorKids"] = ""`).
  Sem default temático pra não enganar comprador. Cleanup de espaço duplo
  do Fix v5 garante título limpo.
- **Sufixos `NoN` altos esperados** (No13...No52) — vários produtos com mesmo
  tema (ex: muitos "Animais Safari" com numerações diferentes). Operador
  confirmou que isso é OK.

**Pendência (placeholder):** `imagens_fixas["DecorKids"]` é cópia das URLs
do AllQuadros. Operador deve fornecer 5 URLs ImgBB próprias do tema infantil
e atualizar `config.json`.

### Estratégia "régua 25% off via tabela inflada" (16/05/2026)

Validada empiricamente em 15/05/2026 (produto "Deus No Comando", iPaper).
Substitui o modelo anterior de "preço-alvo direto" — agora Peter cadastra
com **tabela inflada** + operador ativa **Promoção do Vendedor 25%** contínua
na Shopee. Resultado: card com riscado preto + tag verde "-25%", margem
20-25% preservada, sem disparar flag de "desconto enganoso" (Lei 14.532/2023).

**Fórmula:** `inflado = floor(alvo / 0.75 × 100) / 100`. A Shopee aplica
CEILING (centavos) ao calcular `inflado × 0.75`, resultando exatamente no
preço-alvo. Valores hardcoded em `config.json` (chaves `precos` e
`precos_alvo` em paralelo) — não recalculados em runtime pra evitar bugs de
float.

**Tipos suportados:** apenas Q1, KIT2, KIT3 (alinhado com 12 SKUs canônicos
validados). KIT4-9 (do Fix v6) **removidos**. Se o LLM/operador tentar
detectar `KIT4`+, cai pra Q1 com warning — operador resolve manualmente.

**Fluxo 2-etapas (operador):**
1. Peter run 1 → planilha de cadastro Shopee (preço da col "Preço" = inflado)
2. Operador sobe na Shopee Seller Center, aguarda processamento
3. Operador exporta `mass_update_sales_info` da Shopee (Meus Produtos →
   Ações → Exportar)
4. Peter run 2 (card "Gerar Planilha de Desconto" no frontend) → upload do
   arquivo → POST `/api/desconto` → baixa `discount_25off_<data>.xlsx`
5. Operador sobe `discount_25off_*.xlsx` na Shopee (Promoções → Promoção
   do Vendedor → Importar)

**Implementação:** `scripts/build_discount_template.py` parseia SKU
(`{TIPO}_{TAM}{MOL}_{NOME}` ex: `Q1_4060MM_Salmo4610`), faz lookup em
`CONFIG["precos"]` e `CONFIG["precos_alvo"]`, gera XLSX com 9 colunas
(formato template-discount oficial Shopee). Endpoint em `web/app.py`
`/api/desconto`. Frontend: card secundário em `index.html` + handler em
`app.js`.

## Filtro de imagens (modo "So Links")

Anuncios Etsy frequentemente tem imagens que NAO sao do quadro (cards de texto
do vendedor, video posters, instrucoes, diagramas de tamanho). Antes do upload
no ImgBB, o pipeline roda um filtro automatico via **Gemini 2.5 Flash** que
identifica e remove essas imagens.

- **Ativacao:** `GEMINI_API_KEY` no `.env` (https://aistudio.google.com/apikey).
  Sem a key, o filtro fica desativado e o comportamento original e mantido.
- **Custo:** ~US$0.00005 por imagem analisada. Lote de 30 produtos x 6 imagens
  = ~US$0.009 (~R$0.05). Negligenciavel.
- **Tempo:** ~5-10s por imagem. Lote de 30 produtos pode adicionar 5-10 min.
- **Seletor de metodo (avancado):** `FRAME_DETECTION_METHOD=opencv|gemini` no
  `.env`. Default = gemini. OpenCV existe como alternativa gratuita mas falha
  em cards de texto com moldura (texto e detectado como quadro).
- **Buffer:** Firecrawl retorna ate 5 imagens (1 capa + 4 extras) para o filtro
  ter de onde escolher quando algumas sao filtradas. Planilha Shopee usa 4
  (capa + 3 detalhes — colunas R, S, T, U); o 5 buffer cobre 1 imagem ruim.

## Arquivos de Referencia
| Arquivo | Descricao |
|---------|-----------|
| `planilhas_padrao/Shopee_mass_upload_*_basic_template.xlsx` | Template oficial Shopee BR |
| `planilhas_padrao/cadastrar_produtos_erp.xls` | Template ERP Tiny (com produto exemplo) |
| `planilhas_padrao/kakashi_art_generator.xlsx` | Template Kakashi (3 colunas: SKU, Descricao, URL imagem) |
| `planilhas_links_artes/` | Planilhas de entrada com URLs Etsy |
| `.claude/lojas.md` | Padroes SEO de titulo por loja |
| `.claude/sku-e-precos.md` | Estrutura SKU e tabela de precos |
| `.claude/regras-nome-arte.md` | Regras para gerar nome da arte em PascalCase |
| `.claude/template-shopee.md` | Mapeamento exato das 53 colunas da Shopee |

## Estrutura de Pastas
```
Peter_Copy_Ads/
├── .claude/              # Documentacao e skill
├── scripts/              # Scripts Python
├── planilhas_padrao/     # Templates oficiais (Shopee + ERP)
├── planilhas_links_artes/ # Input: URLs da Etsy
├── planilhas_geradas_shopee/ # Output: planilhas para Shopee
└── planilhas_geradas_erp/   # Output: planilhas para ERP
```
