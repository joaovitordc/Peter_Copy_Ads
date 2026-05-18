"""
build_shopee_template.py — Gera planilha Shopee no formato oficial pra upload em massa.

A partir do Fix v7 (28/04/2026), gera diretamente no formato oficial Shopee
(Shopee_mass_upload_..._basic_template.xlsx) — operador sobe direto na plataforma
sem necessidade de copiar/colar pra template oficial.

Estrutura preservada do template oficial:
- Aba "Modelo" com 6 linhas de metadata (mantidas intactas)
- Dados de produtos a partir da linha 7
- Abas auxiliares (Orientação, HiddenTax, etc.) preservadas — validam upload

Uso:
    python scripts/build_shopee_template.py <input.json> [--loja PPJ]

Entrada: JSON com lista de produtos (ver formato abaixo).
Saida: planilhas_geradas_shopee/shopee_<loja>_<data>.xlsx

Formato do JSON de entrada:
{
  "loja": "PPJ",
  "produtos": [
    {
      "nome_arte_sku": "DeusEBom",
      "nome_arte_display": "Deus e Bom o Tempo Todo",
      "tipo": "Q1",
      "titulo_shopee": "Quadro Decorativo Religioso Minimalista Para Sala, Escritório e Quarto - Deus e Bom o Tempo Todo",
      "imagem_capa": "https://i.ibb.co/xxx/capa.jpg",
      "imagem_1": "https://i.ibb.co/xxx/img1.jpg",
      "imagem_2": "https://i.ibb.co/xxx/img2.jpg",
      "imagem_3": "https://i.ibb.co/xxx/img3.jpg"
    }
  ]
}
"""
import sys, json, os, argparse, shutil
from datetime import date
import openpyxl

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Carrega config.json
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

TEMPLATE_PATH = os.path.join(BASE_DIR, "planilhas_padrao", "Shopee_mass_upload_2026-04-10_basic_template.xlsx")

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


# Banco de SKUs em uso agora mora em scripts/sku_storage (auto-decide entre
# Supabase quando configurado e arquivo local como fallback). Em Vercel sem
# Supabase, escreve em /tmp (volatil); em dev local, escreve no arquivo do
# repo. Esses wrappers existem so pra retrocompat — codigo novo deve chamar
# sku_storage diretamente.
import sku_storage as _sku_storage  # noqa: E402  (import depois das dependencias acima)


def carregar_skus() -> dict:
    return _sku_storage.carregar()


def salvar_skus(skus: dict):
    _sku_storage.salvar(skus)


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

    # imagens_fixas agora e por loja: CONFIG["imagens_fixas"][loja] = {"img4":..,"img5":..}
    imagens_fixas_global = CONFIG["imagens_fixas"]
    if loja in imagens_fixas_global and isinstance(imagens_fixas_global[loja], dict):
        imagens_fixas = imagens_fixas_global[loja]
    else:
        # Fallback para estrutura antiga (chaves img4-img8 no nivel raiz)
        # ou loja desconhecida - usa qualquer set como ultima opcao
        if all(k in imagens_fixas_global for k in ("img4", "img5", "img6", "img7", "img8")):
            imagens_fixas = imagens_fixas_global
        else:
            primeira_loja = next(iter(imagens_fixas_global.values()))
            imagens_fixas = primeira_loja
            print(
                f"[AVISO] Loja '{loja}' sem imagens_fixas configurada. Usando set fallback.",
                file=sys.stderr,
            )

    # Verificar conflitos de SKU antes de gerar
    skus_existentes = carregar_skus()
    conflitos = []
    for produto in produtos:
        nome_sku = produto["nome_arte_sku"]
        if nome_sku in skus_existentes:
            existente = skus_existentes[nome_sku]
            if existente["display"] != produto.get("nome_arte_display", ""):
                lojas_existente = existente.get("lojas") or [existente.get("loja", "?")]
                conflitos.append(
                    f"  CONFLITO: SKU '{nome_sku}' ja existe para '{existente['display']}' "
                    f"(em {', '.join(lojas_existente)}, criado {existente['criado_em']}). "
                    f"Produto atual: '{produto.get('nome_arte_display', '')}'"
                )
    if conflitos:
        # Imprime no terminal pra debug + levanta exception para o pipeline web
        # capturar e mostrar no UI (em vez de matar o processo com sys.exit).
        print("[ERRO] Conflitos de SKU encontrados:", file=sys.stderr)
        for c in conflitos:
            print(c, file=sys.stderr)
        # Quando rodando como CLI standalone, ainda saimos com erro
        if __name__ == "__main__":
            sys.exit(1)
        # Quando importado pelo pipeline web, levantamos exception com info util
        raise ValueError(
            "Conflito de SKU - este nome ja foi usado para outra arte. Detalhes:\n"
            + "\n".join(conflitos)
            + "\nResolucao: edite skus_em_uso.json (apaga a entrada antiga) "
            "OU mude o nome da arte para algo unico."
        )

    # Copiar template oficial Shopee como base (6 linhas de metadata, dados na linha 7)
    hoje = date.today().strftime("%Y-%m-%d")
    nome_arquivo = f"shopee_{loja.lower()}_{hoje}.xlsx"
    caminho = os.path.join(output_dir, nome_arquivo)
    # Se arquivo existir e estiver bloqueado, usar sufixo numerico
    if os.path.exists(caminho):
        base = caminho[:-5]
        sufixo = 2
        while os.path.exists(f"{base}_{sufixo}.xlsx"):
            sufixo += 1
        caminho = f"{base}_{sufixo}.xlsx"
    shutil.copy2(TEMPLATE_PATH, caminho)

    wb = openpyxl.load_workbook(caminho)
    ws = wb["Modelo"]

    # Dados comecam na linha 7 (apos 6 linhas de metadata do template oficial Shopee).
    # ws.append() insere automaticamente apos a ultima linha preenchida.
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
                "", "",                         # P: GTIN, Q: ID marca (vazio — deu problema com 5485339)
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

    wb.save(caminho)

    # Registrar novos SKUs no banco. adicionar() faz MERGE inteligente:
    # se o SKU ja existe no banco com outras lojas (ex: PPJ ja cadastrou
    # `DeusEBom`, agora AllQuadros tambem), adiciona AllQuadros ao array
    # `lojas_cadastradas` sem duplicar. Se for SKU novo, faz INSERT.
    hoje = date.today().strftime("%Y-%m-%d")
    for produto in produtos:
        nome_sku = produto["nome_arte_sku"]
        _sku_storage.adicionar(nome_sku, {
            "loja":      loja,
            "tipo":      produto.get("tipo", "Q1"),
            "display":   produto.get("nome_arte_display", ""),
            "criado_em": hoje,
        })

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
