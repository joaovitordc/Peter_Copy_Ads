"""
core.py — Orquestrador do pipeline Etsy → Shopee + ERP.

Importa as funcoes dos scripts existentes sem modifica-los.
Executa o pipeline completo a partir de um arquivo de entrada.
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Callable

# Caminho base do projeto
BASE_DIR = Path(__file__).parent.parent

# Adicionar scripts/ ao path para que o Python encontre os modulos
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Imports diretos (Vercel detecta estaticamente e inclui no bundle)
import read_input as _read_input
import fetch_etsy_images as _fetch_etsy
import upload_images as _upload_images
import build_shopee_template as _build_shopee
import build_erp_template as _build_erp

# Importar config.json
CONFIG_PATH = BASE_DIR / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

from web.art_name import gerar_nome_arte, gerar_titulo_seo


class ProcessamentoError(Exception):
    """Erro durante o processamento do pipeline."""
    pass


def processar(
    filepath: str,
    loja: str,
    output_dir: str,
    progress_cb: Callable[[str, int], None] | None = None,
) -> dict:
    """
    Pipeline completo: planilha com URLs Etsy → 2 planilhas geradas.

    Args:
        filepath:    Caminho para o arquivo .xlsx/.xls/.csv de entrada
        loja:        Nome da loja (PPJ, iPaper, AllQuadros)
        output_dir:  Diretorio onde salvar as planilhas geradas
        progress_cb: Callback(mensagem, percentual) para atualizacao de progresso

    Returns:
        {
            "shopee_path": str,
            "erp_path": str,
            "produtos": int,
            "avisos": list[str],
        }
    """

    def progresso(msg: str, pct: int):
        if progress_cb:
            progress_cb(msg, pct)

    # Validar loja
    if loja not in CONFIG["lojas"]:
        raise ProcessamentoError(f"Loja '{loja}' nao encontrada. Use: {', '.join(CONFIG['lojas'].keys())}")

    # Validar ETSY_API_KEY
    etsy_key = os.environ.get("ETSY_API_KEY", "")
    if not etsy_key:
        raise ProcessamentoError(
            "ETSY_API_KEY nao configurada no .env. "
            "Obtenha sua chave em https://www.etsy.com/developers/register"
        )

    # Validar IMGBB_API_KEY
    imgbb_key = os.environ.get("IMGBB_API_KEY", "")
    if not imgbb_key or imgbb_key == "sua_chave_aqui":
        raise ProcessamentoError(
            "IMGBB_API_KEY nao configurada no .env. "
            "Obtenha sua chave em https://api.imgbb.com/"
        )

    os.makedirs(output_dir, exist_ok=True)
    avisos = []

    # ── Etapa 1: Ler URLs da planilha ──────────────────────────────────────
    progresso("Lendo planilha de entrada...", 5)
    try:
        urls = _read_input.ler_urls(filepath)
    except Exception as e:
        raise ProcessamentoError(f"Erro ao ler planilha: {e}")

    if not urls:
        raise ProcessamentoError(
            "Nenhum link da Etsy encontrado na planilha. "
            "Verifique se o arquivo contém URLs no formato etsy.com/listing/..."
        )

    total = len(urls)
    progresso(f"Encontrados {total} links da Etsy", 10)

    # ── Etapa 2: Buscar dados de cada listing na API Etsy ──────────────────
    produtos_etsy = []
    for i, url in enumerate(urls):
        pct = 10 + int((i / total) * 35)  # 10% → 45%
        progresso(f"Buscando dados do Etsy ({i + 1}/{total})...", pct)
        try:
            resultados = _fetch_etsy.processar_listings([url])
            if resultados:
                produtos_etsy.append(resultados[0])
            else:
                avisos.append(f"Listing sem dados: {url}")
        except Exception as e:
            avisos.append(f"Erro ao buscar {url}: {e}")
        # Delay entre chamadas ja e feito dentro de processar_listings

    if not produtos_etsy:
        raise ProcessamentoError("Nenhum produto foi carregado da API Etsy. Verifique a ETSY_API_KEY.")

    # ── Etapa 3: Gerar nomes, tipos e titulos SEO ─────────────────────────
    progresso("Gerando nomes e titulos SEO...", 50)
    produtos_processados = []

    for item in produtos_etsy:
        titulo_etsy = item.get("titulo", "")
        imagens_etsy = item.get("imagens", [])
        n_imagens = len(imagens_etsy)

        if not titulo_etsy:
            avisos.append(f"Listing {item.get('listing_id')} sem titulo, pulando.")
            continue

        nome_sku, nome_display, tipo = gerar_nome_arte(titulo_etsy, n_imagens)

        if not nome_sku:
            avisos.append(f"Nao foi possivel gerar nome para: {titulo_etsy[:60]}")
            continue

        titulo_shopee = gerar_titulo_seo(loja, nome_display, tipo, titulo_etsy, CONFIG)

        produtos_processados.append({
            "titulo_etsy": titulo_etsy,
            "nome_arte_sku": nome_sku,
            "nome_arte_display": nome_display,
            "tipo": tipo,
            "titulo_shopee": titulo_shopee,
            "imagens_etsy": imagens_etsy,
        })

    if not produtos_processados:
        raise ProcessamentoError("Nenhum produto valido apos processamento dos titulos.")

    # ── Etapa 4: Upload das imagens para ImgBB ────────────────────────────
    total_p = len(produtos_processados)
    for i, produto in enumerate(produtos_processados):
        pct = 55 + int((i / total_p) * 25)  # 55% → 80%
        progresso(f"Hospedando imagens ({i + 1}/{total_p})...", pct)

        imagens_etsy = produto.pop("imagens_etsy")

        # Precisamos de ate 4 imagens (capa + 3)
        urls_para_upload = imagens_etsy[:4] if len(imagens_etsy) >= 4 else imagens_etsy

        try:
            urls_imgbb = _upload_images.upload_imagens(urls_para_upload)
        except Exception as e:
            avisos.append(f"Erro no upload de imagens de '{produto['nome_arte_display']}': {e}")
            urls_imgbb = []

        # Garantir que temos 4 posicoes (None se falhou)
        while len(urls_imgbb) < 4:
            urls_imgbb.append(None)

        produto["imagem_capa"] = urls_imgbb[0] or ""
        produto["imagem_1"] = urls_imgbb[1] or urls_imgbb[0] or ""
        produto["imagem_2"] = urls_imgbb[2] or urls_imgbb[0] or ""
        produto["imagem_3"] = urls_imgbb[3] or urls_imgbb[0] or ""

        # Delay entre produtos para nao sobrecarregar ImgBB
        if i < total_p - 1:
            time.sleep(0.5)

    # ── Etapa 5: Montar JSON intermediario ────────────────────────────────
    progresso("Montando dados dos produtos...", 82)
    input_json = {
        "loja": loja,
        "produtos": [
            {
                "nome_arte_sku": p["nome_arte_sku"],
                "nome_arte_display": p["nome_arte_display"],
                "tipo": p["tipo"],
                "titulo_shopee": p["titulo_shopee"],
                "imagem_capa": p["imagem_capa"],
                "imagem_1": p["imagem_1"],
                "imagem_2": p["imagem_2"],
                "imagem_3": p["imagem_3"],
            }
            for p in produtos_processados
        ],
    }

    # ── Etapa 6: Gerar planilha Shopee ────────────────────────────────────
    progresso("Gerando planilha Shopee...", 88)
    try:
        shopee_path = _build_shopee.gerar_shopee(input_json, output_dir)
    except Exception as e:
        raise ProcessamentoError(f"Erro ao gerar planilha Shopee: {e}")

    # ── Etapa 7: Gerar planilha ERP ───────────────────────────────────────
    progresso("Gerando planilha ERP...", 94)
    try:
        erp_path = _build_erp.gerar_erp(input_json, output_dir, loja=loja)
    except Exception as e:
        raise ProcessamentoError(f"Erro ao gerar planilha ERP: {e}")

    progresso("Concluido!", 100)

    return {
        "shopee_path": shopee_path,
        "erp_path": erp_path,
        "produtos": len(produtos_processados),
        "avisos": avisos,
    }
