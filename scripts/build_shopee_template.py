"""
build_shopee_template.py — Gera planilha Shopee com 8 variacoes por produto.

Uso:
    python scripts/build_shopee_template.py <input.json> [--loja PPJ]

Entrada: JSON com lista de produtos (ver formato abaixo).
Saida: planilhas_geradas_shopee/shopee_<loja>_<data>.xlsx

Formato do JSON de entrada:
{
  "loja": "PPJ",
  "produtos": [
    {
      "nome_arte_sku": "DeusEBomOTempoTodo",
      "nome_arte_display": "Deus e Bom o Tempo Todo",
      "tipo": "Q1",
      "titulo_shopee": "Quadro Decorativo Religioso Para Sala, Escritório e Quarto - Deus e Bom o Tempo Todo",
      "imagem_capa": "https://i.ibb.co/xxx/capa.jpg",
      "imagem_1": "https://i.ibb.co/xxx/img1.jpg",
      "imagem_2": "https://i.ibb.co/xxx/img2.jpg",
      "imagem_3": "https://i.ibb.co/xxx/img3.jpg"
    }
  ]
}
"""
import sys, json, os, argparse
from datetime import date
import openpyxl
from openpyxl.utils import get_column_letter

# Carrega config.json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

DESCRICAO_PADRAO = """Transforme o seu ambiente com Quadros de Decoração de interiores (Sala, Quarto e Escritórios).

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
Caso queira produzir algum quadro personalizado ou tinha alguma dúvida sobre o produto, não hesite em chamar nossa equipe no Chat."""

# Row 1: internal field names (Shopee template structure)
ROW1_HEADERS = [
    "ps_category|0|0", "ps_product_name|1|0", "ps_product_description|1|0",
    "ps_sku_parent_short|0|0", "et_title_variation_integration_no|0|0",
    "et_title_variation_1|0|0", "et_title_option_for_variation_1|0|0",
    "et_title_image_per_variation|0|3", "et_title_variation_2|0|0",
    "et_title_option_for_variation_2|0|0", "ps_price|1|1", "ps_stock|0|1",
    "ps_sku_short|0|0", "ps_new_size_chart|0|1", "et_title_size_chart|0|3",
    "ps_gtin_code|0|0", "sl_tool_mass_upload_compatibility_title|0|0",
    "ps_item_cover_image|0|3", "ps_item_image_1|0|3", "ps_item_image_2|0|3",
    "ps_item_image_3|0|3", "ps_item_image_4|0|3", "ps_item_image_5|0|3",
    "ps_item_image_6|0|3", "ps_item_image_7|0|3", "ps_item_image_8|0|3",
    "ps_weight|1|1", "ps_length|0|1", "ps_width|0|1", "ps_height|0|1",
    "channel_id.90022|0|0", "channel_id.90024|0|0", "channel_id.91003|0|0",
    "ps_product_pre_order_dts|0|1", "ps_invoice_ncm|0|0",
    "ps_invoice_cfop_same|0|0", "ps_invoice_cfop_diff|0|0",
    "ps_invoice_origin|0|0", "ps_invoice_csosn|0|0", "ps_invoice_cest|0|0",
    "ps_invoice_measure_unit|0|0", "ps_pis_cofins_cst_default|0|0",
    "ps_federal_state_taxes_default|0|0", "ps_operation_type_default|0|0",
    "ps_ex_tipi_default|0|0", "ps_fci_num_default|0|0",
    "ps_recopi_num_default|0|0", "ps_additional_info_default|0|0",
    "sl_label_product_is_grouped_item|0|0", "sl_label_grouped_item_gtin_sscc|0|0",
    "sl_label_grouped_item_qty|0|0", "sl_label_grouped_item_measure_unity|0|0",
    "et_title_reason|0|0",
]

ROW2_META = ["basic", "dc115f855aa8e718d858320a594d9639", "0", "1416244638"]

ROW3_HEADERS = [
    "Categoria", "Nome do Produto", "Descrição do Produto", "SKU principal",
    "Número de Integração de Variação", "Nome da Variação 1",
    "Opção para Variação 1", "Imagem por Variação", "Nome da Variação 2",
    "Opção para Variação 2", "Preço", "Estoque", "SKU da Variação",
    "Template da Tabela de Medidas", "Imagem de Tamanhos", "GTIN (EAN)",
    "IDs de compatibilidade", "Imagem de capa", "Imagem do produto 1",
    "Imagem do produto 2", "Imagem do produto 3", "Imagem do produto 4",
    "Imagem do produto 5", "Imagem do produto 6", "Imagem do produto 7",
    "Imagem do produto 8", "Peso", "Comprimento", "Largura", "Altura",
    "Entrega Direta", "Retirada pelo Comprador", "Shopee Xpress",
    "Prazo de Postagem para Encomenda", "NCM", "CFOP (Mesmo Estado)",
    "CFOP (Outro Estado)", "Origem", "CSOSN", "CEST", "Unidade de Medida",
    "CST PIS/Cofins", "% total de tributos federais, estaduais e municipais",
    "Tipo de Operação", "EX TIPI (tabela de exceções IPI)",
    "Nr. de controle da FCI", "Nr. RECOPI",
    "Informações adicionais do produto", "Produto é um item agrupável",
    "GTIN da Unidade Tributável", "Quantidade da Unidade Tributável",
    "Unidade de medida do item agrupável", "Motivo da Falha",
]

ROW4_REQUIRED = [
    "Opcional", "Obrigatório", "Obrigatório", "Opcional",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Obrigatório", "Condicional obrigatório", "Opcional",
    "Condicional obrigatório", "Condicional obrigatório", "Opcional", "Opcional",
    "Opcional", "Opcional", "Opcional", "Opcional", "Opcional", "Opcional",
    "Opcional", "Opcional", "Opcional",
    "Obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Opcional",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório",
    "Condicional obrigatório", "Condicional obrigatório", "Condicional obrigatório", "",
]


def get_preco(tipo: str, tamanho_sku: str, tipo_moldura: str) -> float:
    """Retorna o preco da tabela config.json."""
    try:
        return CONFIG["precos"][tipo][tamanho_sku][tipo_moldura]
    except KeyError:
        print(f"  [AVISO] Preco nao encontrado para {tipo}/{tamanho_sku}/{tipo_moldura}, usando 0", file=sys.stderr)
        return 0.0


def gerar_shopee(input_json: dict, output_dir: str) -> str:
    loja = input_json.get("loja", "LOJA")
    produtos = input_json.get("produtos", [])
    imagens_fixas = CONFIG["imagens_fixas"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Modelo"

    # Escrever linhas de cabecalho (1-4)
    ws.append(ROW1_HEADERS)
    row2 = ROW2_META + [""] * (53 - len(ROW2_META))
    ws.append(row2)
    ws.append(ROW3_HEADERS)
    ws.append(ROW4_REQUIRED)
    ws.append([""] * 53)  # linha 5 (instrucoes - deixar vazia na versao gerada)
    ws.append([""] * 53)  # linha 6 (validacoes - deixar vazia)

    # Dados comecam na linha 7
    num_integracao = 1
    total_linhas = 0

    for produto in produtos:
        nome_sku = produto["nome_arte_sku"]
        titulo = produto["titulo_shopee"]
        tipo = produto.get("tipo", "Q1")
        sku_principal = f"{tipo}_{nome_sku}"
        img_capa = produto.get("imagem_capa", "")
        img1 = produto.get("imagem_1", "")
        img2 = produto.get("imagem_2", "")
        img3 = produto.get("imagem_3", "")

        for var in CONFIG["variacoes"]:
            tamanho = var["tamanho"]
            tam_sku = var["tam_sku"]
            moldura = var["moldura"]
            mol_sku = var["mol_sku"]
            tipo_mold = var["tipo_mold"]
            sku_var = f"{tipo}_{tam_sku}{mol_sku}_{nome_sku}"
            preco = get_preco(tipo, tam_sku, tipo_mold)

            linha = [
                CONFIG["shopee_category_id"],  # A: Categoria
                titulo,                          # B: Nome do Produto
                DESCRICAO_PADRAO,               # C: Descricao
                sku_principal,                  # D: SKU principal
                num_integracao,                 # E: Nº Integracao Variacao
                "Tamanho",                      # F: Nome Variacao 1
                tamanho,                        # G: Opcao Variacao 1
                "",                             # H: Imagem por Variacao (vazio)
                "Moldura",                      # I: Nome Variacao 2
                moldura,                        # J: Opcao Variacao 2
                preco,                          # K: Preco
                CONFIG["default_stock"],        # L: Estoque
                sku_var,                        # M: SKU Variacao
                "", "",                         # N: Template medidas, O: Img tamanhos
                "", "",                         # P: GTIN, Q: compatibilidade
                img_capa,                       # R: Imagem de capa
                img1,                           # S: Imagem 1
                img2,                           # T: Imagem 2
                img3,                           # U: Imagem 3
                imagens_fixas["img4"],          # V: Imagem 4
                imagens_fixas["img5"],          # W: Imagem 5
                imagens_fixas["img6"],          # X: Imagem 6
                imagens_fixas["img7"],          # Y: Imagem 7
                imagens_fixas["img8"],          # Z: Imagem 8
                CONFIG["default_weight_kg"],    # AA: Peso
                CONFIG["default_comprimento_cm"],# AB: Comprimento
                CONFIG["default_largura_cm"],   # AC: Largura
                CONFIG["default_altura_cm"],    # AD: Altura
            ]
            # Completar ate 53 colunas com vazios
            linha += [""] * (53 - len(linha))
            ws.append(linha)
            total_linhas += 1

        num_integracao += 1

    # Salvar
    hoje = date.today().strftime("%Y-%m-%d")
    nome_arquivo = f"shopee_{loja.lower()}_{hoje}.xlsx"
    caminho = os.path.join(output_dir, nome_arquivo)
    wb.save(caminho)
    print(f"[OK] Shopee: {caminho} ({len(produtos)} produtos, {total_linhas} linhas)", file=sys.stderr)
    return caminho


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Arquivo JSON com dados dos produtos")
    parser.add_argument("--output-dir", default="planilhas_geradas_shopee")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    base = os.path.dirname(os.path.dirname(__file__))
    output_dir = os.path.join(base, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    caminho = gerar_shopee(data, output_dir)
    print(caminho)
