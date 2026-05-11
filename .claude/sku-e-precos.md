# SKU, Variacoes e Tabela de Precos

## Formato do SKU

```
[TIPO]_[TAMANHO][MOLDURA]_[NomeCurto]
```

O `[NomeCurto]` usa **2-3 palavras identificadoras** da arte (nao o nome completo).
Ver regras completas em `regras-nome-arte.md`.

**Exemplos:**
- `Q1_4060MP_DeusEBom`
- `KIT3_3040SM_PrimaryFlow`
- `KIT3_MIX_SafariTribal`
- `Q1_3040SM_NoteToGod`

---

## Tipos de Produto

| Codigo | Descricao | Qtd quadros |
|--------|-----------|-------------|
| `Q1` | Quadro unitario | 1 |
| `KIT2` | Kit com 2 quadros | 2 |
| `KIT3` | Kit com 3 quadros | 3 |
| `KIT5` | Kit com 5 quadros | 5 |
| `KIT6` | Kit com 6 quadros | 6 |
| `KIT8` | Kit com 8 quadros | 8 |

---

## Tamanhos

| Codigo | Dimensao real | Uso tipico |
|--------|--------------|------------|
| `2030` | 20×30 cm | Linha infantil, mini |
| `3040` | 30×40 cm | Padrao menor |
| `4060` | 40×60 cm | **Padrao maior (mais vendido)** |
| `5070` | 50×70 cm | Canvas/premium |
| `6090` | 60×90 cm | Canvas/premium grande |
| `MIX` | Composicao variada | Kits com tamanhos diferentes |

---

## Molduras

| Codigo | Nome completo | Caracteristica |
|--------|--------------|----------------|
| `MM` | Moldura Madeira | Tom amadeirado |
| `MB` | Moldura Branca | Minimalista, clean |
| `MP` | Moldura Preta | Moderna, contraste |
| `SM` | Sem Moldura | So o adesivo impresso |

> **CM** (Com Moldura) = qualquer um de MM, MB, MP. O preco e o mesmo para os tres.

---

## Tabela de Precos de Venda (BRL)

> SM = Sem Moldura | CM = Com Moldura (MM, MB ou MP — mesmo preco)

| Tamanho | Q1 SM | Q1 CM | KIT3 SM | KIT3 CM |
|---------|-------|-------|---------|---------|
| 20x30 | R$ 19,90 | R$ 59,90 | R$ 59,90 | R$ 119,90 |
| 30x40 | R$ 29,90 | R$ 79,90 | R$ 69,90 | R$ 189,90 |
| 40x60 | R$ 49,90 | R$ 109,90 | R$ 109,90 | R$ 249,90 |
| 60x90 | R$ 89,90 | R$ 199,90 | R$ 249,90 | R$ 499,90 |

### Tamanho 50x70 (interpolar entre 40x60 e 60x90)
| Tipo | SM | CM |
|------|----|----|
| Q1 | R$ 69,90 | R$ 149,90 |
| KIT3 | R$ 179,90 | R$ 369,90 |

### KIT2 / KIT5 / KIT6 / KIT8
Calcular proporcionalmente com KIT3 como referencia base.

---

## Variacoes por Produto

Cada produto gera **8 variacoes** (linhas na planilha Shopee):
- 2 tamanhos × 4 molduras (padrao: 30x40 e 40x60)

Ordem das variacoes (seguir o VBA):
1. 30x40 + Sem Moldura
2. 30x40 + Moldura Preta
3. 30x40 + Moldura Branca
4. 30x40 + Moldura Madeira
5. 40x60 + Sem Moldura
6. 40x60 + Moldura Preta
7. 40x60 + Moldura Branca
8. 40x60 + Moldura Madeira

---

## Descricao Padrao (Shopee)

```
Transforme o seu ambiente com Quadros de Decoração de interiores (Sala, Quarto e Escritórios).
 
Esqueça as paredes vazias, nossos quadros estão prontos para dar vida ao ambiente, adicionando um toque moderno e acolhedor.

Informações Técnicas:
Quadros em MDF e COM OPÇÃO de Moldura
30x40cm cada quadro // 40x60cm cada quadro

Acompanha Fita Dupla-Face para opção Sem Moldura.

São feitos em Adesivos Premium

Não acompanha vidro

Foto meramente ilustrativa.

OBS: As cores do produto podem sofrer pequena alteração entre a sua tela e o produto final.

Cuidados:
Limpeza: basta passar um paninho úmido com água.
Não use produtos abrasivos.
Recomendamos o uso em ambiente interno para maior durabilidade.

Prazo de Produção:
Enviamos nossos pedidos em até 24 horas !!
Nossa prioridade e garantir a sua satisfação. ♥

Informações Adicionais:
Caso queira produzir algum quadro personalizado ou tinha alguma dúvida sobre o produto, não hesite em chamar nossa equipe no Chat.
```

---

## Imagens Fixas (posicoes 4-8 na Shopee)

Cada loja tem seu **proprio conjunto de 5 imagens de suporte** (img4-img8) que vao em todas as variacoes do produto. Configuradas em `config.json` -> `imagens_fixas[loja]`.

Estrutura:
```json
"imagens_fixas": {
  "PPJ":        {"img4": "...", "img5": "...", "img6": "...", "img7": "...", "img8": "..."},
  "iPaper":     {"img4": "...", "img5": "...", "img6": "...", "img7": "...", "img8": "..."},
  "AllQuadros": {"img4": "...", "img5": "...", "img6": "...", "img7": "...", "img8": "..."}
}
```

Hospedagem: ImgBB (`i.ibb.co/.../*.png`).

Para trocar as imagens de uma loja, basta substituir as URLs em `config.json` (ou rodar um script de upload novo).

Posicoes 1-3 (capa + produto 1-2) e Imagem de Capa sao extraidas da Etsy e hospedadas no ImgBB.

---

## Fisico do Produto (dimensoes e peso)

| Campo | Valor |
|-------|-------|
| Peso liquido | 1,0 kg |
| Comprimento embalagem | 45 cm |
| Largura embalagem | 65 cm |
| Altura embalagem | 5 cm |
| Estoque padrao | 1000 |
| Categoria Shopee | 101156 |
