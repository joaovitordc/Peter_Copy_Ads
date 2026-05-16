"""
read_input.py — Le planilha de entrada com URLs de anuncios (qualquer site).

Formato esperado:
  A: QUANTIDADE de quadros no produto (1=Q1, 2=KIT2, 3=KIT3, vazio=detecção automática)
  B: URL do anuncio (obrigatorio) — Etsy, Shopee, ou qualquer site (https?://)
  C: URL imagem capa (opcional)
  D: URL imagem 1    (opcional)
  E: URL imagem 2    (opcional)
  F: URL imagem 3    (opcional)

Detecção de URL é por `https?://` (universal). Antes (pre-30/04/2026) era
restrito a `etsy.com/listing/...`.

Quando QUANTIDADE preenchido com valor valido (1, 2 ou 3), TEM PRIORIDADE
sobre deteccao automatica do LLM e do determinar_tipo(). Valor invalido
(fora de 1-3, texto, decimal nao-inteiro) gera warning e cai pro LLM.

Tipos suportados desde 2026-05-16: Q1 (1 quadro), KIT2, KIT3 apenas.
KIT4-9 foram removidos junto com a migracao pra estrategia 25% off via
tabela inflada (so existe tabela canonica validada pra esses 3 tipos).

Uso:
    python scripts/read_input.py planilhas_links_artes/links_artes_PPJ_090426.xlsx

Saida: JSON para stdout com lista de objetos
{url, img_capa, img1, img2, img3, quantidade_manual, quantidade_raw}.
"""
import sys, json, re, os


_URL_RE = re.compile(r'^https?://', re.IGNORECASE)


def _eh_url(s) -> bool:
    """Verifica se s e uma URL bem-formada (qualquer site)."""
    return bool(s) and bool(_URL_RE.match(str(s).strip()))


def limpar_url(u):
    if not u or not isinstance(u, str):
        return ""
    return re.split(r'\?', u.strip())[0]


def ler_planilha(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    linhas = []  # lista de listas de celulas por linha

    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            linhas.append([str(c).strip() if c else "" for c in row])
    elif ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(filepath)
        ws = wb.sheet_by_index(0)
        for row_idx in range(ws.nrows):
            linhas.append([str(ws.cell_value(row_idx, col)).strip() for col in range(ws.ncols)])
    elif ext == ".csv":
        import csv
        with open(filepath, encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                linhas.append([c.strip() for c in row])
    else:
        print(f"Formato nao suportado: {ext}", file=sys.stderr)
        sys.exit(1)

    return linhas


def parse_entrada(filepath):
    linhas = ler_planilha(filepath)
    resultados = []
    seen_urls = set()

    for linha in linhas:
        if not linha:
            continue

        # NOVO (Fix v6): Coluna A = QUANTIDADE (pode ser vazia, "1", "2"-"9", ou invalida)
        col_a_quantidade = linha[0] if len(linha) > 0 else ""
        # Coluna B = URL Etsy (era A antes do Fix v6)
        col_b_url = linha[1] if len(linha) > 1 else ""

        # Quantidade manual: int valido entre 1 e 3, ou None
        quantidade_manual = None
        if col_a_quantidade:
            try:
                # Aceita "3", "3.0", " 3 " etc
                q = int(float(col_a_quantidade))
                if 1 <= q <= 3:
                    quantidade_manual = q
                # Se fora do range (4-9, 0, negativo), fica None silenciosamente
                # (warning sera dado em core.py)
            except (ValueError, TypeError):
                # Texto invalido, fica None silenciosamente
                pass

        # Detectar URL: aceita em col B (formato novo) OU varrer linha (compat)
        url = ""
        img_capa = img1 = img2 = img3 = ""

        if _eh_url(col_b_url):
            # Formato novo: A=quantidade, B=url, C-F=imagens
            url = limpar_url(col_b_url)
            img_capa = limpar_url(linha[2]) if len(linha) > 2 else ""
            img1     = limpar_url(linha[3]) if len(linha) > 3 else ""
            img2     = limpar_url(linha[4]) if len(linha) > 4 else ""
            img3     = limpar_url(linha[5]) if len(linha) > 5 else ""
        else:
            # Fallback: escanear todas as celulas por URL (formato livre)
            for cell in linha:
                if _eh_url(cell):
                    url = limpar_url(cell)
                    break

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        resultados.append({
            "url":               url,
            "img_capa":          img_capa,
            "img1":              img1,
            "img2":              img2,
            "img3":              img3,
            "quantidade_manual": quantidade_manual,                # int 1-9 ou None
            "quantidade_raw":    str(col_a_quantidade).strip(),    # para warning de invalido
        })

    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/read_input.py <arquivo>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"Arquivo nao encontrado: {filepath}", file=sys.stderr)
        sys.exit(1)

    resultados = parse_entrada(filepath)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))

    com_imagens = sum(1 for r in resultados if r["img_capa"])
    print(f"\n[INFO] {len(resultados)} URLs encontradas ({com_imagens} ja com imagens)", file=sys.stderr)
