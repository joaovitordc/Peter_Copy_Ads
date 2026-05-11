# Regras para Nome da Arte (SKU)

O nome da arte no SKU segue o formato **PascalCase** sem acentos, espacos ou caracteres especiais.

---

## Processo de Conversao

1. Extrair o nome da arte do titulo do anuncio Etsy (parte descritiva, nao as palavras SEO)
2. **Selecionar 2-3 palavras mais identificadoras** do nome (as que tornam o SKU unico e reconhecivel)
3. Remover acentos: a→a, e→e, i→i, o→o, u→u, c→c, etc.
4. Remover espacos, virgulas, pontos, hifens, parenteses e outros caracteres nao alfanumericos
5. Aplicar PascalCase: primeira letra de cada palavra maiuscula
6. Aplicar regra do `E`: a conjuncao "e"/"and" entre palavras vira `E` maiusculo
7. Algarismos romanos: totalmente maiusculos

> **Objetivo do SKU curto:** identificar a arte de forma unica sem alongar o SKU. Nao e necessario incluir todas as palavras do nome.

## Limite de Tamanho (regra estrita)

- **SKU completo (com prefixo TIPO_): NUNCA pode passar de 30 caracteres**
- **Ideal: 15-20 caracteres**
- O nome da arte (parte apos `TIPO_`) raramente deve passar de ~22 chars
- Exemplos validos: `Q1_DeusEBom` (11), `KIT3_OvelhaPerdida` (17), `KIT3_OliveiraGetsemani` (22)
- Exemplo INVALIDO: `KIT3_JesusAndTheLostSheepPrintChristianBibleArtGoodShepherd` (61) — esse e o titulo Etsy completo, nao um identificador da arte

Quando o titulo Etsy e muito longo (frequentemente em ingles, com toda a descricao SEO), o nome da arte deve ser **traduzido e resumido em portugues** mantendo so o SUBJECT (Jesus, oliveira, ovelha, leao, etc), nao palavras de marketing (print, wall art, decor, modern, kit).

---

## Regras Especiais

### Conjuncao "E" maiusculo
A conjuncao "e" (ou "and" em ingles) entre duas palavras do nome da arte vira `E` maiusculo, criando um visual PascalCase continuo.

```
Deus e Bom       → DeusEBom
Cruz e Amor      → CruzEAmor
Fé e Esperança   → FeEEsperanca
Faith and Hope   → FaithAndHope  (nao se aplica "E" para "and" ingles, manter AndHope)
```

### Algarismos Romanos
Ficam totalmente maiusculos.
```
Yayoi Kusama III → YayoiKusamaIII
Louis XIV        → LouisXIV
```

### "No1", "No2"...
- Remover `No1` salvo em series numeradas (quando ha No2, No3...) ou colecoes infantis
- Se o produto e parte de uma serie (ex: No1, No2, No3), manter o numero
```
Blessed Club No1  → BlessedClub   (remover, produto unico)
Safari Tribal No1 → SafariTribalNo1  (manter se ha No2, No3)
```

### Palavras SEO — ficam FORA do SKU
Nunca incluir no nome da arte do SKU:
- Moderno, Minimalista, Aesthetic, Contemporaneo
- Para Sala, Para Quarto, Para Escritorio
- Kit, Quadro, Conjunto, Arte de Parede
- Decorativo, Decoracao
- Com Moldura, Sem Moldura
- Estampado, Impresso

---

## Exemplos Completos

| Nome da Arte (display) | SKU (curto, PascalCase) |
|------------------------|------------------------|
| Deus e Bom o Tempo Todo | DeusEBom |
| Primary Flow | PrimaryFlow |
| Safari Tribal | SafariTribal |
| Felicidade, Euforia e Inspiracao | FelicidadeEInspiracao |
| My God Can | MyGodCan |
| Note to God | NoteToGod |
| Fe sobre o Medo | FeSobreMedo |
| Salmo 46:10 | Salmo4610 |
| Blessed Club | BlessedClub |
| Haring Skate | HaringSkate |
| Jesus Pagou Tudo | JesusPagou |
| Este e o Dia que o Senhor Fez | EsteEoDia |
| Ande pela Fe nao pela Vista | AndePelaFe |
| Jesus and the Lost Sheep Print: Christian Bible Art (EN) | OvelhaPerdida ou JesusOvelha |
| Gethsemane Olive Tree Wall Art (EN) | OliveiraGetsemani |
| Good Shepherd Modern Christian Print (EN) | BomPastor |
| Crown of Thorns Watercolor Print (EN) | CoroaEspinhos |

---

## Descricao para ERP (Coluna C)

O campo de descricao do ERP segue o padrao:
```
[Tipo completo] - [Nome da Arte com acentos/display] - [Acabamento] - [Tamanho]
```

Exemplos:
- Produto pai: `Kit 3 Quadros - Felicidade, Euforia e Inspiração`
- Produto filho: `Kit 3 Quadros - Felicidade, Euforia e Inspiração - Moldura Branca - 30x40`

Para o campo de descricao do ERP, usar o nome da arte **com** acentos e separadores originais (virgulas, etc.), nao o PascalCase.

---

## Mapeamento Acabamento (para ERP coluna C e AM)

| Codigo SKU | Nome completo (ERP) | AM (Shopee/ERP variacoes) |
|------------|--------------------|-----------------------------|
| SM | Sem Moldura | Moldura:Sem Moldura |
| MP | Moldura Preta | Moldura:Moldura Preta |
| MB | Moldura Branca | Moldura:Moldura Branca |
| MM | Moldura Madeira | Moldura:Moldura Madeira |
