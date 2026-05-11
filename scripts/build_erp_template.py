"""
build_erp_template.py — Gera planilha ERP (Tiny) com produto pai + filhos.

Uso:
    python scripts/build_erp_template.py <input.json> [--loja PPJ]

Entrada: mesmo JSON usado por build_shopee_template.py
Saida: planilhas_geradas_erp/erp_<loja>_<data>.xlsx

Estrutura: 1 linha pai (tipo V) + 8 filhos (tipo F) por produto.
"""
import sys, json, os, argparse
from datetime import date
import openpyxl

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

# Cabecalhos da planilha ERP (64 colunas — extraido do template cadastrar_produtos_erp.xls)
ERP_HEADERS = [
    "ID", "Código (SKU)", "Descrição", "Unidade", "Classificação fiscal",
    "Origem", "Preço", "Valor IPI fixo", "Observações", "Situação",
    "Estoque", "Preço de custo", "Cód do Fornecedor", "Fornecedor",
    "Localização", "Estoque máximo", "Estoque mínimo", "Peso líquido (Kg)",
    "Peso bruto (Kg)", "GTIN/EAN", "GTIN/EAN tributável",
    "Descrição complementar", "CEST", "Código de Enquadramento IPI",
    "Formato embalagem", "Largura embalagem", "Altura embalagem",
    "Comprimento embalagem", "Diâmetro embalagem", "Tipo do produto",
    "URL imagem 1", "URL imagem 2", "URL imagem 3", "URL imagem 4",
    "URL imagem 5", "URL imagem 6", "Categoria", "Código do pai",
    "Variações", "Marca", "Garantia", "Sob encomenda", "Preço promocional",
    "URL imagem externa 1", "URL imagem externa 2", "URL imagem externa 3",
    "URL imagem externa 4", "URL imagem externa 5", "URL imagem externa 6",
    "Link do vídeo", "Título SEO", "Descrição SEO", "Palavras chave SEO",
    "Slug", "Dias para preparação", "Controlar lotes", "Unidade por caixa",
    "URL imagem externa 7", "URL imagem externa 8", "URL imagem externa 9",
    "URL imagem externa 10", "Markup", "Permitir inclusão nas vendas", "EX TIPI",
]

# Mapeamento de codigo moldura para nome completo (ERP)
MOLDURA_NOME = {
    "SM": "Sem Moldura",
    "MP": "Moldura Preta",
    "MB": "Moldura Branca",
    "MM": "Moldura Madeira",
}

# Mapeamento tipo para descricao por extenso
TIPO_NOME = {
    "Q1":   "Quadro",
    "KIT2": "Kit 2 Quadros",
    "KIT3": "Kit 3 Quadros",
    "KIT4": "Kit 4 Quadros",
    "KIT5": "Kit 5 Quadros",
    "KIT6": "Kit 6 Quadros",
    "KIT7": "Kit 7 Quadros",
    "KIT8": "Kit 8 Quadros",
    "KIT9": "Kit 9 Quadros",
}


def get_preco(tipo: str, tamanho_sku: str, tipo_mold: str) -> float:
    try:
        return CONFIG["precos"][tipo][tamanho_sku][tipo_mold]
    except KeyError:
        return 0.0


def linha_vazia(n=64):
    return [""] * n


def gerar_erp(input_json: dict, output_dir: str, loja: str = None) -> str:
    loja = loja or input_json.get("loja", "LOJA")
    produtos = input_json.get("produtos", [])
    loja_config = CONFIG["lojas"].get(loja, {})
    marca = loja_config.get("marca_erp", loja)
    prefixo = loja_config.get("prefixo_descricao_erp", "")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Produtos"
    ws.append(ERP_HEADERS)

    campos_fixos = {
        "D": "UN",
        "E": CONFIG["classificacao_fiscal"],
        "F": CONFIG["origem_produto"],
        "J": "Ativo",
        "R": CONFIG["default_weight_kg"],
        "S": round(CONFIG["default_weight_kg"] + 0.1, 1),
        "Y": "Pacote / Caixa",
        "Z": CONFIG["default_largura_cm"] - 1,     # largura embalagem (64)
        "AA": CONFIG["default_altura_cm"],           # altura embalagem (5)
        "AB": CONFIG["default_comprimento_cm"] - 1, # comprimento embalagem (44)
        "AK": CONFIG["categoria_erp"],
        "AN": marca,
        "AO": 1,
        "AP": "Não",
        "BC": 0,
        "BD": "Não",
        "BK": "Sim",
    }

    # Mapa coluna -> indice (0-based) baseado em ERP_HEADERS
    col_idx = {h: i for i, h in enumerate(ERP_HEADERS)}

    def make_row(overrides: dict) -> list:
        row = linha_vazia()
        for header, val in campos_fixos.items():
            # Converter letra de coluna para indice
            idx = ord(header[0]) - ord("A")
            if len(header) > 1:
                idx = (idx + 1) * 26 + ord(header[1]) - ord("A")
            if idx < 64:
                row[idx] = val
        for header, val in overrides.items():
            idx = ord(header[0]) - ord("A")
            if len(header) > 1:
                idx = (idx + 1) * 26 + ord(header[1]) - ord("A")
            if idx < 64:
                row[idx] = val
        return row

    total_linhas = 0

    for produto in produtos:
        nome_sku = produto["nome_arte_sku"]
        nome_display = produto["nome_arte_display"]
        tipo = produto.get("tipo", "Q1")
        tipo_nome = TIPO_NOME.get(tipo, tipo)
        sku_pai = f"{tipo}_{nome_sku}"
        img_capa = produto.get("imagem_capa", "")

        # Linha do produto PAI (tipo V)
        desc_pai = f"{tipo_nome} - {prefixo}{nome_display}"
        row_pai = make_row({
            "B": sku_pai,
            "C": desc_pai,
            "G": 0,           # Preço do pai sempre 0 (preco real fica nos filhos)
            "AD": "V",
            "AE": img_capa,
            # AL vazio no pai (sem codigo do pai)
        })
        ws.append(row_pai)
        total_linhas += 1

        # Linhas dos FILHOS (tipo F, 8 variacoes)
        for var in CONFIG["variacoes"]:
            tamanho = var["tamanho"]
            tam_sku = var["tam_sku"]
            moldura = var["moldura"]
            mol_sku = var["mol_sku"]
            tipo_mold = var["tipo_mold"]
            sku_filho = f"{tipo}_{tam_sku}{mol_sku}_{nome_sku}"
            preco = get_preco(tipo, tam_sku, tipo_mold)
            desc_filho = f"{tipo_nome} - {prefixo}{nome_display} - {moldura} - {tamanho}"
            variacoes_str = f"Moldura:{moldura}||Tamanho:{tamanho}||"

            row_filho = make_row({
                "B": sku_filho,
                "C": desc_filho,
                "G": preco,
                "AD": "F",
                "AE": img_capa,
                "AL": sku_pai,
                "AM": variacoes_str,
            })
            ws.append(row_filho)
            total_linhas += 1

    # Salvar
    hoje = date.today().strftime("%Y-%m-%d")
    nome_arquivo = f"erp_{loja.lower()}_{hoje}.xlsx"
    caminho = os.path.join(output_dir, nome_arquivo)
    wb.save(caminho)
    print(f"[OK] ERP: {caminho} ({len(produtos)} produtos, {total_linhas} linhas)", file=sys.stderr)
    return caminho


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Arquivo JSON com dados dos produtos")
    parser.add_argument("--loja", default=None)
    parser.add_argument("--output-dir", default="planilhas_geradas_erp")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    base = os.path.dirname(os.path.dirname(__file__))
    output_dir = os.path.join(base, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    caminho = gerar_erp(data, output_dir, loja=args.loja)
    print(caminho)
