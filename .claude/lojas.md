# Lojas Shopee - Padroes de Titulo SEO

Temos 4 lojas na Shopee Brasil, cada uma com nicho e padrao de titulo diferentes.
O **nome da arte sempre vem no final, apos o hifen** (`-`) ou travessao (`–`).
As palavras entre o tipo de produto e o hifen sao **SEO puro** — nao entram no SKU.

---

## PPJ — Foco religioso / minimalista

**Padrao:**
```
Quadro Decorativo [Categoria] Minimalista Moderno Para Sala, Escritório e Quarto - [Nome Da Arte]
```

**Regra de 120 chars:** se ultrapassar, remover "Moderno" primeiro, depois "Minimalista". O nome da arte nunca e cortado.

**Exemplos:**
- `Quadro Decorativo Religioso Minimalista Moderno Para Sala, Escritório e Quarto - Deus e Bom`
- `Quadro Decorativo Cristão Minimalista Moderno Para Sala, Escritório e Quarto - Note to God`
- `Quadro Decorativo Bíblico Minimalista Para Sala, Escritório e Quarto - Salmo 46:10` *(sem "Moderno" pois passaria de 120)*

**Tags SEO comuns para PPJ:**
Religioso, Cristão, Bíblico, Evangélico, Católico, Fé, Espiritual — escolher a mais adequada ao tema da arte.

---

## iPaper — Foco artistico / Bauhaus / design

**Padrao:**
```
Quadro Decorativo [Estilo] Para Sala, Quarto ou Escritório – [Nome Da Arte]
```
> Usa travessao `–` (nao hifen simples `-`)

**Exemplos:**
- `Quadro Decorativo Bauhaus Para Sala, Quarto ou Escritório – Primary Flow`
- `Quadro Decorativo Arte Abstrata Moderna Para Sala, Quarto ou Escritório – Geometric Bloom`

**Tags SEO comuns para iPaper:**
Bauhaus, Arte Abstrata, Moderno, Vintage, Minimalista, Aesthetic, Design, Contemporâneo

---

## AllQuadros — Foco kits / conjuntos

**Padrao:**
```
Kit [N] Quadros Decorativos [Estilo] [Tags] Moderno - [Nome Da Arte]
```

**Exemplos:**
- `Kit 3 Quadros Decorativos Vintage Minimalista Para Sala, Quarto ou Escritório - Safari Tribal`
- `Kit 3 Quadros Decorativos Haring Skate Moderno - Pisa89 Flower`

**Tags SEO comuns para AllQuadros:**
Vintage, Minimalista, Moderno, Aesthetic, Para Sala, Para Quarto, Decoração, Conjunto

---

## AllQuadros / categoria "Infantil" — Foco infantil / nursery / kids

> Refatoracao 18/05/2026: o que antes era "loja DecorKids" agora e a
> categoria `infantil` dentro da loja `AllQuadros`. Mesmo template SEO,
> mesmo prefixo ERP, mesmo conjunto de temas curados — apenas o SKU
> agora persiste como `lojas_cadastradas=['AllQuadros']` em vez de
> `['DecorKids']`. No frontend, o operador seleciona AllQuadros + clica
> em "Infantil" no sub-card de categoria.

**Padrao Q1:**
```
Quadro Decorativo Infantil [Tema] | Quarto Bebê Menino e Menina – [Nome Da Arte]
```

**Padrao KIT:**
```
Kit [N] Quadros Decorativos Infantil [Tema] | Quarto Bebê Menino e Menina – [Nome Da Arte]
```
> "Infantil" singular mesmo em KIT (busca SEO BR é por "infantil"). Usa pipe `|`
> separando bloco SEO do bloco demografico, e travessao `–` (nao hifen) antes do nome.

**Exemplos:**
- `Quadro Decorativo Infantil Safari Animais Fofos | Quarto Bebê Menino e Menina – Leão da Selva`
- `Kit 3 Quadros Decorativos Infantil Flores e Florais | Quarto Bebê Menino e Menina – Jardim Encantado`
- `Kit 3 Quadros Decorativos Infantil | Quarto Bebê Menino e Menina – Animais Safari No13` *(quando Etsy nao tem tema; cleanup remove espaco duplo)*

**10 temas curados (do operador):**
1. Animais Fofos
2. Natureza Boho
3. Transporte
4. Carros
5. Fundo do Mar
6. Flores e Floral *(vira "Flores e Florais" em KIT por concordancia PT)*
7. Arco Iris
8. Fada *(singular mantido em KIT)*
9. Bailarina *(singular mantido em KIT)*
10. Safari

**Descricao ERP/Kakashi:** ganha prefixo `Infantil ` automaticamente:
`Kit 3 Quadros - Infantil Animais Safari No13`. SKU NAO ganha prefixo
(`KIT3_AnimaisSafariNo13`).

---

## Regras Gerais

1. Limite Shopee: **2 a 120 caracteres** para nome do produto (usar até 120)
2. O hifen (`-` ou `–`) separa o SEO do nome da arte — nome da arte SEMPRE no final
3. As palavras antes do hifen nao entram no SKU
4. Acentos e cedilha sao aceitos no titulo (e recomendados para SEO)
5. Ao processar uma arte, perguntar qual loja antes de gerar o titulo
