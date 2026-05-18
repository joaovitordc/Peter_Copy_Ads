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
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse, unquote

# Caminho base do projeto
BASE_DIR = Path(__file__).parent.parent

# Adicionar scripts/ ao path para que o Python encontre os modulos
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Imports diretos (Vercel detecta estaticamente e inclui no bundle)
import read_input as _read_input
import upload_images as _upload_images
import build_shopee_template as _build_shopee
import build_erp_template as _build_erp
import export_kakashi as _export_kakashi
import fetch_etsy_images as _fetch_etsy_api
import fetch_etsy_firecrawl as _fetch_etsy_firecrawl


def _get_etsy_fetcher():
    """Escolhe o fetcher baseado nas API keys disponiveis. Firecrawl tem prioridade."""
    if os.environ.get("FIRECRAWL_API_KEY"):
        return _fetch_etsy_firecrawl
    if os.environ.get("ETSY_API_KEY"):
        return _fetch_etsy_api
    return None

# Importar config.json
CONFIG_PATH = BASE_DIR / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

from web.art_name import gerar_nome_arte, gerar_titulo_seo


class ProcessamentoError(Exception):
    def __init__(self, mensagem: str, avisos: list[str] | None = None):
        super().__init__(mensagem)
        self.avisos = avisos or []


def _slug_to_titulo(slug: str) -> str:
    """Converte slug URL-safe em titulo legivel (decode %-encoding + spaces + capitalize)."""
    slug = unquote(slug)
    slug = re.sub(r'[-_]+', ' ', slug)
    palavras = slug.split()
    return ' '.join(w.capitalize() for w in palavras if w)


def _titulo_do_slug(url: str) -> str:
    """Extrai titulo aproximado do slug da URL.

    Suporta Etsy, Shopee BR/INTL, e fallback generico (ultimo segmento do path).
    Usado no modo 'Links + Imagens' como base para a etapa de traducao LLM.
    """
    if not url:
        return ""

    # Etsy: /listing/{id}/{slug}
    m = re.search(r'/listing/\d+/([^?/]+)', url)
    if m:
        return _slug_to_titulo(m.group(1))

    # Shopee BR/INTL: /{slug}-i.{shopid}.{itemid}
    m = re.search(r'/([^/?]+?)-i\.\d+\.\d+', url)
    if m:
        return _slug_to_titulo(m.group(1))

    # Fallback generico: ultimo segmento nao-vazio do path
    path = urlparse(url).path
    segmentos = [s for s in path.split('/') if s]
    if segmentos:
        return _slug_to_titulo(segmentos[-1])

    return ""


def _carregar_skus_existentes() -> dict:
    """Carrega SKUs em uso via scripts/sku_storage (Supabase quando configurado,
    arquivo local como fallback). Retorna dict vazio em caso de erro."""
    try:
        import sku_storage
        return sku_storage.carregar()
    except Exception as e:
        print(f"[AVISO] _carregar_skus_existentes falhou: {e}", file=sys.stderr)
        return {}


# (loja, categoria) onde o LLM NAO deve inventar nomes alternativos em caso
# de conflito. Pra essas, o resolver vai direto pro sufixo NoN — preserva
# os temas canonicos (Carros, Bailarina, Animais Fofos, etc.) em vez de
# inventar nomes aleatorios fora dos 10 temas curados.
_CATEGORIAS_SUFIXO_NON_DIRETO = {("AllQuadros", "infantil")}


def _resolver_conflitos_sku(
    produtos_brutos: list[dict],
    avisos: list[str],
    tema_loja: str = "",
    loja: str = "",
    categoria: str = "padrao",
) -> None:
    """
    Para cada produto, garante que `nome_curto_ai` nao conflita com SKU ja
    cadastrado em skus_em_uso.json (ou no proprio lote atual).

    Estrategia:
      1. Se nome ja livre, mantem.
      2. (Categorias com tema curado, ex AllQuadros/infantil) pula direto pro
         sufixo NoN. (Outras) pede ao LLM outro nome ate 3 vezes (lista 'evitar').
      3. Se ainda conflita, adiciona sufixo No2, No3, ... ate achar livre.

    Modifica produtos_brutos in-place (atualiza nome_curto_ai e nome_display_ai).
    """
    usar_llm_retry = (loja, categoria) not in _CATEGORIAS_SUFIXO_NON_DIRETO

    try:
        import traduzir_nome as _trad
    except ImportError:
        usar_llm_retry = False  # sem tradutor, so resta sufixo NoN

    skus_existentes = _carregar_skus_existentes()
    nomes_no_lote: dict[str, str] = {}  # nome_curto -> display (intra-lote)

    def conflita(nome_curto: str, nome_display: str) -> bool:
        if not nome_curto:
            return False
        # Conflito intra-lote: SEMPRE que nome_curto ja foi usado.
        # (mesmo display nao garante mesmo produto - sao anuncios distintos)
        if nome_curto in nomes_no_lote:
            return True
        # Conflito com SKUs ja cadastrados em skus_em_uso.json
        if nome_curto in skus_existentes:
            return True
        return False

    for produto in produtos_brutos:
        nome_curto = (produto.get("nome_curto_ai") or "").strip()
        nome_display = (produto.get("nome_display_ai") or "").strip()
        titulo = produto.get("titulo", "")

        if not nome_curto:
            continue  # sem nome da IA, fallback (gerar_nome_arte) cuidara depois

        # 1. Sem conflito? Otimo.
        if not conflita(nome_curto, nome_display):
            nomes_no_lote[nome_curto] = nome_display
            continue

        nome_original = nome_curto

        # 2. (Outras categorias) Tenta 3 vezes pedir outro nome ao LLM.
        # Pra (AllQuadros, infantil) em _CATEGORIAS_SUFIXO_NON_DIRETO, pula
        # direto pro NoN — mantem tema canonico (Carros, Bailarina, etc.).
        if usar_llm_retry:
            evitar = [nome_curto]
            for tentativa in range(1, 4):
                resultado_alt = _trad.traduzir_para_pt(
                    titulo, tema_loja=tema_loja, evitar=evitar,
                )
                curto_alt = resultado_alt["curto"]
                display_alt = resultado_alt["display"]
                if not curto_alt:
                    print(f"[SKU] Tentativa {tentativa} (LLM): falhou", file=sys.stderr)
                    break
                print(
                    f"[SKU] Tentativa {tentativa} (LLM): "
                    f"'{nome_curto}' -> '{curto_alt}'",
                    file=sys.stderr,
                )
                if not conflita(curto_alt, display_alt):
                    nome_curto = curto_alt
                    nome_display = display_alt
                    break
                evitar.append(curto_alt)
        else:
            print(
                f"[SKU] Loja '{loja}' usa sufixo NoN direto "
                f"(preserva tema canonico). Conflito: '{nome_curto}'",
                file=sys.stderr,
            )

        # 3. Se ainda conflita, adicionar sufixo NoN ate achar livre
        if conflita(nome_curto, nome_display):
            base_curto = nome_curto[:22]  # cap pra deixar espaco pro sufixo
            base_display = nome_display
            for n in range(2, 100):
                cand_curto = f"{base_curto}No{n}"
                cand_display = f"{base_display} No{n}"
                if not conflita(cand_curto, cand_display):
                    nome_curto = cand_curto
                    nome_display = cand_display
                    print(f"[SKU] Sufixo aplicado: '{nome_original}' -> '{nome_curto}'", file=sys.stderr)
                    break
            else:
                # Nao encontrou em 100 tentativas (extremamente improvavel)
                avisos.append(
                    f"Conflito persistente no SKU para titulo '{titulo[:40]}'. "
                    f"Edite skus_em_uso.json manualmente."
                )

        if nome_curto != nome_original:
            avisos.append(
                f"Nome original '{nome_original}' ja em uso. Renomeado para '{nome_curto}'."
            )

        produto["nome_curto_ai"] = nome_curto
        produto["nome_display_ai"] = nome_display
        nomes_no_lote[nome_curto] = nome_display


def processar(
    filepath: str,
    loja: str,
    output_dir: str,
    modo: str = "links_com_imagens",
    progress_cb: Callable[[str, int], None] | None = None,
    categoria: str = "",
) -> dict:
    """
    Pipeline completo: planilha → 2 planilhas geradas (Shopee + ERP).

    Args:
        filepath:    Arquivo .xlsx/.xls/.csv de entrada
        loja:        PPJ | iPaper | AllQuadros
        output_dir:  Pasta de destino das planilhas geradas
        modo:        "links" (requer API Etsy) | "links_com_imagens" (sem API)
        progress_cb: Callback(mensagem, percentual)
        categoria:   "padrao" | "infantil" (so AllQuadros tem 'infantil').
                     Vazio = usa categoria_default da loja.

    Returns:
        {"shopee_path", "erp_path", "produtos", "avisos"}
    """

    def progresso(msg: str, pct: int):
        if progress_cb:
            progress_cb(msg, pct)

    # Validar loja
    if loja not in CONFIG["lojas"]:
        raise ProcessamentoError(f"Loja '{loja}' invalida. Use: {', '.join(CONFIG['lojas'].keys())}")

    loja_cfg = CONFIG["lojas"][loja]

    # Validar categoria (default = categoria_default da loja)
    if not categoria:
        categoria = loja_cfg.get("categoria_default", "padrao")
    if categoria not in loja_cfg["categorias"]:
        cats_validas = ", ".join(loja_cfg["categorias"].keys())
        raise ProcessamentoError(
            f"Categoria '{categoria}' invalida para loja '{loja}'. Use: {cats_validas}"
        )

    cat_cfg = loja_cfg["categorias"][categoria]
    tema_loja = cat_cfg.get("tema_loja", "")

    # No modo 'links' precisamos de pelo menos um fetcher (Firecrawl OU Etsy API)
    fetcher = None
    if modo == "links":
        fetcher = _get_etsy_fetcher()
        if fetcher is None:
            raise ProcessamentoError(
                "Modo 'So Links' requer FIRECRAWL_API_KEY (recomendado) ou ETSY_API_KEY no .env. "
                "Crie uma chave gratuita em https://www.firecrawl.dev/ ou use o modo 'Links + Imagens'."
            )
        print(f"[INFO] Usando fetcher: {fetcher.__name__}", file=sys.stderr)

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
            "Nenhum link de anuncio encontrado na planilha. "
            "Verifique se o arquivo contem URLs (ex: etsy.com/listing/..., "
            "shopee.com.br/..., etc.)."
        )

    total = len(dados)
    progresso(f"Encontrados {total} links da Etsy", 10)

    # ── Etapa 2: Obter titulo e imagens de cada produto ───────────────────
    produtos_brutos = []

    if modo == "links":
        # Gate: modo autonomo so suporta URLs Etsy (fetchers sao Etsy-especificos).
        # Para Shopee/outros sites, operador deve usar modo 'Links + Imagens'.
        urls = [item["url"] for item in dados]
        nao_etsy = [u for u in urls if not re.search(r'etsy\.com/(?:pt/)?listing/\d+', u)]
        if nao_etsy:
            raise ProcessamentoError(
                f"Modo 'So Links' suporta apenas URLs Etsy ({len(nao_etsy)} de "
                f"{len(urls)} URLs sao de outros sites). Para Shopee/outros, use o "
                f"modo 'Links + Imagens' fornecendo as imagens manualmente. "
                f"URL incompativel (primeira): {nao_etsy[0][:80]}"
            )

        # Busca titulo + imagens em lote (paralelizado quando o fetcher suporta)
        progresso(f"Buscando dados do Etsy de {total} produtos...", 15)
        try:
            resultados = fetcher.processar_listings(urls)
        except Exception as e:
            raise ProcessamentoError(f"Erro ao buscar dados na Etsy: {e}")

        # Mapear quantidade_manual de volta por URL (parse_entrada le mas fetcher nao propaga)
        quantidades_por_url = {item["url"]: item for item in dados}

        for r in resultados:
            url = r.get("url", "")
            if r.get("_falhou"):
                avisos.append(
                    f"Falha no scrape de {url} - preencha imagens manualmente "
                    f"ou use o modo 'Links + Imagens' para esse produto"
                )
                continue
            entrada = quantidades_por_url.get(url, {})
            produtos_brutos.append({
                "url":               url,
                "titulo":            r.get("titulo", ""),
                "imagens":           r.get("imagens", []),
                "nome_curto_ai":     "",  # preenchido na Etapa 2.6 (traducao)
                "nome_display_ai":   "",
                "tipo_ai":           "",  # preenchido na Etapa 2.6 (LLM)
                "quantidade_manual": entrada.get("quantidade_manual"),
                "quantidade_raw":    entrada.get("quantidade_raw", ""),
            })

        if not produtos_brutos:
            raise ProcessamentoError(
                "Nenhum produto extraido com sucesso. Veja os avisos abaixo ou use o modo 'Links + Imagens'.",
                avisos=avisos,
            )

        # ── Etapa 2.5: Filtrar imagens sem quadro (Gemini Flash) ──────────
        if os.environ.get("GEMINI_API_KEY"):
            progresso("Validando imagens (filtro de quadros)...", 40)
            import frame_detection as _fd
            metodo = os.environ.get("FRAME_DETECTION_METHOD", "gemini")
            print(f"[INFO] Filtro de quadros ativo (metodo={metodo})", file=sys.stderr)

            for produto in produtos_brutos:
                imgs_originais = produto["imagens"]
                imgs_validas = []
                frame_count_capa = 0  # numero de quadros na 1a imagem valida
                for img_url in imgs_originais:
                    tem, n, motivo = _fd.tem_quadro(img_url, method=metodo)
                    if tem:
                        imgs_validas.append(img_url)
                        # Capturar count da PRIMEIRA imagem valida (geralmente a capa)
                        if frame_count_capa == 0 and n > 0:
                            frame_count_capa = n
                        print(f"  [FRAME OK] n={n} {motivo} -> {img_url[:80]}", file=sys.stderr)
                        if len(imgs_validas) >= 4:
                            break
                    else:
                        aviso = f"Imagem filtrada ({motivo}): {img_url}"
                        avisos.append(aviso)
                        print(f"  [FRAME FILTRADA] {motivo} -> {img_url[:80]}", file=sys.stderr)

                # Se zerou tudo, pelo menos mantem a capa pra nao perder o produto
                produto["imagens"] = imgs_validas[:4] or imgs_originais[:1]
                produto["frame_count_capa"] = frame_count_capa
                if not imgs_validas:
                    avisos.append(
                        f"Nenhuma imagem com quadro detectada em {produto['url']} - "
                        f"usando capa original como fallback"
                    )
        else:
            print("[INFO] Filtro de quadros DESATIVADO (GEMINI_API_KEY ausente)", file=sys.stderr)

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
                "nome_curto_ai":     "",  # preenchido na Etapa 2.6 (traducao)
                "nome_display_ai":   "",
                "tipo_ai":           "",  # preenchido na Etapa 2.6 (LLM)
                "quantidade_manual": item.get("quantidade_manual"),
                "quantidade_raw":    item.get("quantidade_raw", ""),
            })

    if not produtos_brutos:
        raise ProcessamentoError(
            "Nenhum produto carregado. "
            "Verifique os links e tente novamente."
        )

    # ── Etapa 2.6: Traducao EN->PT + tipo (GPT-4o-mini, ~1s por produto) ──
    # Roda em AMBOS os modos. Resolve titulos em ingles ou truncados pelo
    # filtro de SEO words da gerar_nome_arte. LLM tambem retorna o tipo
    # (Q1/KITN), substituindo determinar_tipo() quando bem-sucedido.
    if os.environ.get("OPENAI_API_KEY"):
        progresso("Traduzindo titulos para portugues...", 38)
        import traduzir_nome as _trad
        for p in produtos_brutos:
            resultado = _trad.traduzir_para_pt(p["titulo"], tema_loja=tema_loja)
            p["nome_display_ai"] = resultado["display"]
            p["nome_curto_ai"] = resultado["curto"]
            p["tipo_ai"] = resultado["tipo"]
            if resultado["curto"]:
                print(
                    f"[TRAD] '{p['titulo'][:40]}...' -> "
                    f"display='{resultado['display']}', "
                    f"curto='{resultado['curto']}', "
                    f"tipo='{resultado['tipo']}'",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[TRAD] falhou para '{p['titulo'][:40]}...' - "
                    f"usara fallback gerar_nome_arte",
                    file=sys.stderr,
                )

        # ── Etapa 2.7: Resolver conflitos de SKU (3 retries LLM + sufixo NoN) ──
        progresso("Resolvendo conflitos de SKU...", 42)
        _resolver_conflitos_sku(
            produtos_brutos, avisos, tema_loja=tema_loja, loja=loja, categoria=categoria,
        )

    # ── Etapa 3: Gerar nomes (PascalCase) e titulos SEO ──────────────────
    progresso("Gerando nomes e titulos SEO...", 50)
    produtos_processados = []

    for item in produtos_brutos:
        titulo = item["titulo"]
        n_imagens = len(item["imagens"])
        frame_count_capa = item.get("frame_count_capa", 0)

        # Sempre roda gerar_nome_arte como fallback de nome (mesmo com tipo overrided)
        nome_sku_default, nome_display_default, tipo_default = gerar_nome_arte(
            titulo, n_imagens, frame_count_capa=frame_count_capa,
        )

        nome_curto_ai = (item.get("nome_curto_ai") or "").strip()
        nome_display_ai = (item.get("nome_display_ai") or "").strip()
        tipo_ai = (item.get("tipo_ai") or "").strip()
        quantidade_manual = item.get("quantidade_manual")
        quantidade_raw = (item.get("quantidade_raw") or "").strip()

        # Determinar tipo com prioridade:
        # 1) Quantidade manual da planilha (sempre vence)
        # 2) Tipo retornado pelo LLM
        # 3) Tipo do detector determinar_tipo()
        if quantidade_manual is not None:
            tipo = "Q1" if quantidade_manual == 1 else f"KIT{quantidade_manual}"
            print(
                f"[INFO] Quantidade manual da planilha: {quantidade_manual} -> Tipo='{tipo}'",
                file=sys.stderr,
            )
        elif tipo_ai:
            tipo = tipo_ai
        else:
            tipo = tipo_default

        # Aviso se operador colocou valor invalido (raw nao vazio mas manual=None)
        if quantidade_raw and quantidade_manual is None:
            aviso = (
                f"Quantidade '{quantidade_raw}' invalida na planilha "
                f"(produto '{titulo[:40]}'). Use 1, 2 ou 3 ou deixe vazio. "
                f"Caindo pra detecção automatica."
            )
            avisos.append(aviso)
            print(f"[AVISO] {aviso}", file=sys.stderr)

        # Resto da logica de nome (independente da fonte do tipo)
        if nome_curto_ai and len(nome_curto_ai) <= 30:
            nome_sku = nome_curto_ai
            nome_display = nome_display_ai or nome_curto_ai
            print(
                f"[INFO] Usando nome+tipo: SKU='{nome_sku}' "
                f"Display='{nome_display}' Tipo='{tipo}'",
                file=sys.stderr,
            )
        else:
            nome_sku = nome_sku_default
            nome_display = nome_display_default
            if nome_curto_ai:
                print(f"[INFO] Nome da IA descartado (>{30} chars): '{nome_curto_ai}'", file=sys.stderr)

        # Cap rigido - SKU NUNCA passa de 30 caracteres (regra de negocio)
        if len(nome_sku) > 30:
            print(f"[AVISO] Truncando SKU de {len(nome_sku)} para 30 chars: '{nome_sku}'", file=sys.stderr)
            nome_sku = nome_sku[:30]

        if not nome_sku:
            titulo_preview = titulo[:80] if titulo else "(titulo vazio)"
            url_preview = item.get('url', '')[:60]
            aviso_msg = (
                f"Nao foi possivel gerar nome para titulo='{titulo_preview}' "
                f"(url={url_preview}, {n_imagens} imagens). "
                f"Edite o titulo no Etsy ou use modo 'Links + Imagens'."
            )
            avisos.append(aviso_msg)
            print(f"[AVISO][SEO] {aviso_msg}", file=sys.stderr)
            print(f"[DEBUG][SEO] titulo bruto: {repr(titulo)}", file=sys.stderr)
            continue

        titulo_shopee = gerar_titulo_seo(
            loja, nome_display, tipo, titulo, CONFIG, categoria=categoria,
        )

        produtos_processados.append({
            "nome_arte_sku":     nome_sku,
            "nome_arte_display": nome_display,
            "tipo":              tipo,
            "titulo_shopee":     titulo_shopee,
            "imagens":           item.get("imagens_prefornecidas") or item["imagens"],
        })

    if not produtos_processados:
        raise ProcessamentoError(
            "Nenhum produto valido apos processar os titulos. Veja os avisos abaixo.",
            avisos=avisos,
        )

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

        # Cada slot e independente — se a fonte tem so 1 ou 3 imagens, as
        # demais colunas ficam vazias (nao clonam a capa). Shopee aceita
        # imagem_1/2/3 vazias; nao e obrigatorio preencher as 4.
        produto["imagem_capa"] = urls_imgbb[0] or ""
        produto["imagem_1"]    = urls_imgbb[1] or ""
        produto["imagem_2"]    = urls_imgbb[2] or ""
        produto["imagem_3"]    = urls_imgbb[3] or ""

        # delay entre produtos removido — upload_imagens ja paraleliza com
        # 4 workers; throttle inter-produto era margem extra pra rate-limit
        # ImgBB que se mostrou desnecessaria na pratica (operador estava
        # estourando 5min timeout do Vercel Hobby plan).

    # ── Etapa 4.5: Separar OK x rejeitados ────────────────────────────────
    # Criterio de rejeicao: imagem_capa vazia (upload falhou ou ImgBB rejeitou).
    # Produto sem capa quebraria Shopee/ERP/Kakashi — melhor isolar.
    produtos_ok = []
    produtos_rejeitados = []
    for p in produtos_processados:
        if not p.get("imagem_capa"):
            produtos_rejeitados.append({
                "nome_arte_display": p["nome_arte_display"],
                "nome_arte_sku":     p["nome_arte_sku"],
                "tipo":              p["tipo"],
                "motivo":            "imagem_capa vazia (upload ImgBB falhou)",
            })
            avisos.append(
                f"Produto '{p['nome_arte_display']}' rejeitado: capa nao subiu pro ImgBB. "
                f"Tente novamente — geralmente intermitencia da rede/ImgBB."
            )
        else:
            produtos_ok.append(p)

    if not produtos_ok:
        raise ProcessamentoError(
            f"Todos os {len(produtos_processados)} produtos foram rejeitados "
            f"(upload de imagens falhou pra todos). Verifique conexao/ImgBB e tente de novo.",
            avisos=avisos,
        )

    # ── Etapa 5: Montar JSON intermediario (so produtos OK) ───────────────
    progresso("Montando dados dos produtos...", 82)
    input_json = {
        "loja": loja,
        "categoria": categoria,
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
            for p in produtos_ok
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

    # ── Etapa 8: Gerar planilha Kakashi ───────────────────────────────────
    progresso("Gerando planilha Kakashi...", 95)
    kakashi_path = None
    try:
        kakashi_path, avisos_kakashi = _export_kakashi.gerar_kakashi(input_json, output_dir)
        avisos.extend(avisos_kakashi)
    except Exception as e:
        avisos.append(f"Erro ao gerar planilha Kakashi: {e}")

    # ── Etapa 9: Gerar planilha de rejeitados (se houver) ─────────────────
    rejeitados_path = None
    if produtos_rejeitados:
        progresso("Gerando planilha de rejeitados...", 98)
        try:
            import build_rejeitados_template as _build_rej
            rejeitados_path = _build_rej.gerar_rejeitados(produtos_rejeitados, output_dir, loja)
        except Exception as e:
            avisos.append(f"Erro ao gerar planilha de rejeitados: {e}")

    progresso("Concluido!", 100)

    return {
        "shopee_path":     shopee_path,
        "erp_path":        erp_path,
        "kakashi_path":    kakashi_path,
        "rejeitados_path": rejeitados_path,
        "produtos":        len(produtos_ok),
        "rejeitados":      len(produtos_rejeitados),
        "avisos":          avisos,
        "input_json":      input_json,  # snapshot pra regenerar via /api/descartar
    }
