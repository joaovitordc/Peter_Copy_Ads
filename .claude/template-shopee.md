# Mapeamento Exato - Template Shopee BR

Template: `planilhas_padrao/cadastrar_produtos_shopee.xlsx`
Aba: **Planilha1**

## Estrutura de Linhas

| Linha | Conteudo |
|-------|----------|
| 1 | Nomes PT-BR das colunas |
| 2 | Obrigatoriedade (Obrigatorio / Opcional / Condicional obrigatorio) |
| 3 | Descricoes longas de cada campo |
| 4 | Regras de validacao |
| **5+** | **Dados do produto (comecar aqui!)** |

Cada produto gera **8 linhas** (2 tamanhos × 4 molduras).
O **Numero de Integracao de Variacao** (col E) deve ser o mesmo nas 8 linhas de um produto.

---

## Colunas Preenchidas

| Col | Nome PT-BR | Valor |
|-----|-----------|-------|
| **A** | Categoria | `101156` |
| **B** | Nome do Produto | Titulo SEO completo da loja (ver lojas.md) |
| **C** | Descricao do Produto | Texto fixo padrao (ver sku-e-precos.md) |
| **D** | SKU principal | `TIPO_NomeLimpo` (ex: `KIT3_PrimaryFlow`) |
| **E** | Numero de Integracao de Variacao | Auto-incremento: 1, 2, 3... (mesmo nas 8 linhas) |
| **F** | Nome da Variacao 1 | `Tamanho` |
| **G** | Opcao para Variacao 1 | `30x40` ou `40x60` |
| **H** | Imagem por Variacao | (vazio) |
| **I** | Nome da Variacao 2 | `Moldura` |
| **J** | Opcao para Variacao 2 | `Sem Moldura` / `Moldura Preta` / `Moldura Branca` / `Moldura Madeira` |
| **K** | Preco | Da tabela em sku-e-precos.md |
| **L** | Estoque | `1000` |
| **M** | SKU da Variacao | `TIPO_TAMANHOMOLDURAnomeLimpo` (ex: `KIT3_3040MB_PrimaryFlow`) |
| N | Template Tabela Medidas | (vazio) |
| O | Imagem de Tamanhos | (vazio) |
| P | GTIN (EAN) | (vazio) |
| Q | IDs de compatibilidade | (vazio) |
| **R** | Imagem de capa | URL ImgBB da imagem de capa |
| **S** | Imagem do produto 1 | URL ImgBB imagem 1 (da Etsy) |
| **T** | Imagem do produto 2 | URL ImgBB imagem 2 (da Etsy) |
| **U** | Imagem do produto 3 | URL ImgBB imagem 3 (da Etsy) |
| **V** | Imagem do produto 4 | `https://i.postimg.cc/9FqFR363/1-MELI.jpg` (FIXA) |
| **W** | Imagem do produto 5 | `https://i.postimg.cc/8Cw1QT6v/2-MELI.jpg` (FIXA) |
| **X** | Imagem do produto 6 | `https://i.postimg.cc/cLRxhR1X/3-MELI.jpg` (FIXA) |
| **Y** | Imagem do produto 7 | `https://i.postimg.cc/LsmHbJnR/4-MELI.jpg` (FIXA) |
| **Z** | Imagem do produto 8 | `https://i.postimg.cc/wj8xDfz1/5-MELI.jpg` (FIXA) |
| **AA** | Peso | `1` (kg) |
| **AB** | Comprimento | `45` (cm) |
| **AC** | Largura | `65` (cm) |
| **AD** | Altura | `5` (cm) |
| AE-BA | Campos fiscais/tributarios | (vazios) |

---

## Ordem das Variacoes (8 linhas por produto)

| Linha | Tamanho (col G) | Moldura (col J) | SM/CM |
|-------|-----------------|-----------------|-------|
| 1 | 30x40 | Sem Moldura | SM |
| 2 | 30x40 | Moldura Preta | CM |
| 3 | 30x40 | Moldura Branca | CM |
| 4 | 30x40 | Moldura Madeira | CM |
| 5 | 40x60 | Sem Moldura | SM |
| 6 | 40x60 | Moldura Preta | CM |
| 7 | 40x60 | Moldura Branca | CM |
| 8 | 40x60 | Moldura Madeira | CM |

---

## Nomes Internos (Row 1) — NAO EDITAR

```
A: ps_category|0|0
B: ps_product_name|1|0
C: ps_product_description|1|0
D: ps_sku_parent_short|0|0
E: et_title_variation_integration_no|0|0
F: et_title_variation_1|0|0
G: et_title_option_for_variation_1|0|0
H: et_title_image_per_variation|0|3
I: et_title_variation_2|0|0
J: et_title_option_for_variation_2|0|0
K: ps_price|1|1
L: ps_stock|0|1
M: ps_sku_short|0|0
N: ps_new_size_chart|0|1
O: et_title_size_chart|0|3
P: ps_gtin_code|0|0
Q: sl_tool_mass_upload_compatibility_title|0|0
R: ps_item_cover_image|0|3
S: ps_item_image_1|0|3
T: ps_item_image_2|0|3
U: ps_item_image_3|0|3
V: ps_item_image_4|0|3
W: ps_item_image_5|0|3
X: ps_item_image_6|0|3
Y: ps_item_image_7|0|3
Z: ps_item_image_8|0|3
AA: ps_weight|1|1
AB: ps_length|0|1
AC: ps_width|0|1
AD: ps_height|0|1
AE: channel_id.90022|0|0
AF: channel_id.90024|0|0
AG: channel_id.91003|0|0
AH: ps_product_pre_order_dts|0|1
AI: ps_invoice_ncm|0|0
AJ: ps_invoice_cfop_same|0|0
AK: ps_invoice_cfop_diff|0|0
AL: ps_invoice_origin|0|0
AM: ps_invoice_csosn|0|0
AN: ps_invoice_cest|0|0
AO: ps_invoice_measure_unit|0|0
AP: ps_pis_cofins_cst_default|0|0
AQ: ps_federal_state_taxes_default|0|0
AR: ps_operation_type_default|0|0
AS: ps_ex_tipi_default|0|0
AT: ps_fci_num_default|0|0
AU: ps_recopi_num_default|0|0
AV: ps_additional_info_default|0|0
AW: sl_label_product_is_grouped_item|0|0
AX: sl_label_grouped_item_gtin_sscc|0|0
AY: sl_label_grouped_item_qty|0|0
AZ: sl_label_grouped_item_measure_unity|0|0
BA: et_title_reason|0|0
```
