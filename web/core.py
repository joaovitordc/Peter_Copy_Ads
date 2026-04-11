"""
core.py — Orquestrador do pipeline Etsy → Shopee + ERP.

Modos de operacao:
  "links"             — Planilha so com URLs Etsy (requer ETSY_API_KEY aprovada)
  "links_com_imagens" — Planilha com URLs Etsy + imagens ja selecionadas (sem API)
"""
import os
import sys
import re
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
    pass


def _titulo_do_slug(url: str) -> str:
    """Extrai titulo aproximado do slug da URL Etsy (fallback sem API)."""
    m = re.search(r'/listing/\d+/([^?/]+)', url)
    if not m:
        return ""
    slug = m.group(1)
    # "deus-e-bom-o-tempo-todo-arte-de-parede" → "Deus E Bom O Tempo Todo Arte De Parede"
    return ' '.join(w.capitalize() for w in slug.replace('-', ' ').split())


def processar(
    filepath: str,
    loja: str,
    output_dir: str,
    modo: str = "links_com_imagens",
    progress_cb: Callable[[str, int], None] | None = None,
) -> dict:
    """
    Pipeline completo: planilha → 2 planilhas geradas (Shopee + ERP).

    Args:
        filepath:    Arquivo .xlsx/.xls/.csv de entrada
        loja:        PPJ | iPaper | AllQuadros
        output_dir:  Pasta de destino das planilhas geradas
        modo:        "links" (requer API Etsy) | "links_com_imagens" (sem API)
        progress_cb: Callback(mensagem, percentual)

    Returns:
        {"shopee_path", "erp_path", "produtos", "avisos"}
    """

    def progresso(msg: str, pct: int):
        if progress_cb:
            progress_cb(msg, pct)

    # Validar loja
    if loja not in CONFIG["lojas"]:
        raise ProcessamentoError(f"Loja '{loja}' invalida. Use: {', '.join(CONFIG['lojas'].keys())}")

    # Validar ETSY_API_KEY apenas no modo que usa a API
    if modo == "links":
        etsy_key = os.environ.get("ETSY_API_KEY", "")
        if not etsy_key:
            raise ProcessamentoError(
                "ETSY_API_KEY nao configurada. "
                "Enquanto a chave nao for aprovada, use o modo 'Links + Imagens'."
            )

    # Validar IMGBB_API_KEY (necessario em ambos os modos)
    imgbb_key = os.environ.get("IMGBB_API_KEY", "")
    if not imgbb_key or imgbb_key == "sua_chave_aqui":
        raise ProcessamentoError(
            "IMGBB_API_KEY nao configurada no .env. "
            "Obtenha sua chave em https://api.imgbb.com/"
        )

    os.makedirs(output_dir, exist_ok=True)
    avisos = []

    # ── Etapa 1: Ler planilha ─────────────────────────────────────────────
    progresso("Lendo planilha de entrada...", 5)
    try:
        dados = _read_input.parse_entrada(filepath)
    except Exception as e:
        raise ProcessamentoError(f"Erro ao ler planilha: {e}")

    if not dados:
        raise ProcessamentoError(
            "Nenhum link da Etsy encontrado na planilha. "
            "Verifique se o arquivo contem URLs no formato etsy.com/listing/..."
        )

    total = len(dados)
    progresso(f"Encontrados {total} links da Etsy", 10)

    # ── Etapa 2: Obter titulo e imagens de cada produto ───────────────────
    produtos_brutos = []

    if modo == "links":
        # Busca titulo E imagens via API Etsy
        for i, item in enumerate(dados):
            pct = 10 + int((i / total) * 35)
            progresso(f"Buscando dados do Etsy ({i + 1}/{total})...", pct)
            try:
                resultados = _fetch_etsy.processar_listings([item["url"]])
                if resultados:
                    r = resultados[0]
                    produtos_brutos.append({
                        "url":    item["url"],
                        "titulo": r.get("titulo", ""),
                        "imagens": r.get("imagens", []),
                    })
                else:
                    avisos.append(f"Sem dados da API: {item['url']}")
            except Exception as e:
                avisos.append(f"Erro ao buscar {item['url']}: {e}")

    else:
        # Usa titulo do slug + imagens fornecidas na planilha
        progresso(f"Extraindo dados dos {total} links...", 25)
        for item in dados:
            titulo = _titulo_do_slug(item["url"])
            imagens = [
                img for img in [item["img_capa"], item["img1"], item["img2"], item["img3"]]
                if img
            ]
            if not titulo:
                avisos.append(f"Nao foi possivel extrair titulo de: {item['url']}")
                continue
            produtos_brutos.append({
                "url":    item["url"],
                "titulo": titulo,
                "imagens": imagens,
                # Imagens pre-selecionadas (a ordem e: capa, 1, 2, 3)
                "imagens_prefornecidas": imagens,
            })

    if not produtos_brutos:
        raise ProcessamentoError(
            "Nenhum produto carregado. "
            "Verifique os links e tente novamente."
        )

    # ── Etapa 3: Gerar nomes (PascalCase) e titulos SEO ──────────────────
    progresso("Gerando nomes e titulos SEO...", 50)
    produtos_processados = []

    for item in produtos_brutos:
        titulo = item["titulo"]
        n_imagens = len(item["imagens"])

        nome_sku, nome_display, tipo = gerar_nome_arte(titulo, n_imagens)

        if not nome_sku:
            avisos.append(f"Nao foi possivel gerar nome para: {titulo[:60]}")
            continue

        titulo_shopee = gerar_titulo_seo(loja, nome_display, tipo, titulo, CONFIG)

        produtos_processados.append({
            "nome_arte_sku":     nome_sku,
            "nome_arte_display": nome_display,
            "tipo":              tipo,
            "titulo_shopee":     titulo_shopee,
            "imagens":           item.get("imagens_prefornecidas") or item["imagens"],
        })

    if not produtos_processados:
        raise ProcessamentoError("Nenhum produto valido apos processar os titulos.")

    # ── Etapa 4: Upload das imagens para ImgBB ────────────────────────────
    total_p = len(produtos_processados)
    for i, produto in enumerate(produtos_processados):
        pct = 55 + int((i / total_p) * 25)
        progresso(f"Hospedando imagens ({i + 1}/{total_p})...", pct)

        imagens = produto.pop("imagens")
        urls_upload = imagens[:4] if len(imagens) >= 4 else imagens

        try:
            urls_imgbb = _upload_images.upload_imagens(urls_upload)
        except Exception as e:
            avisos.append(f"Erro no upload de '{produto['nome_arte_display']}': {e}")
            urls_imgbb = []

        while len(urls_imgbb) < 4:
            urls_imgbb.append(None)

        produto["imagem_capa"] = urls_imgbb[0] or ""
        produto["imagem_1"]    = urls_imgbb[1] or urls_imgbb[0] or ""
        produto["imagem_2"]    = urls_imgbb[2] or urls_imgbb[0] or ""
        produto["imagem_3"]    = urls_imgbb[3] or urls_imgbb[0] or ""

        if i < total_p - 1:
            time.sleep(0.5)

    # ── Etapa 5: Montar JSON intermediario ────────────────────────────────
    progresso("Montando dados dos produtos...", 82)
    input_json = {
        "loja": loja,
        "produtos": [
            {
                "nome_arte_sku":     p["nome_arte_sku"],
                "nome_arte_display": p["nome_arte_display"],
                "tipo":              p["tipo"],
                "titulo_shopee":     p["titulo_shopee"],
                "imagem_capa":       p["imagem_capa"],
                "imagem_1":          p["imagem_1"],
                "imagem_2":          p["imagem_2"],
                "imagem_3":          p["imagem_3"],
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
        "erp_path":    erp_path,
        "produtos":    len(produtos_processados),
        "avisos":      avisos,
    }
