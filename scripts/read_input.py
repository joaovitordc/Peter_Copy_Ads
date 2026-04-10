"""
read_input.py — Le planilha de entrada com URLs de anuncios Etsy.

Formato esperado da planilha (colunas):
  A: URL do anuncio Etsy (obrigatorio)
  B: URL imagem capa (opcional)
  C: URL imagem 1    (opcional)
  D: URL imagem 2    (opcional)
  E: URL imagem 3    (opcional)

Se as colunas B-E estiverem preenchidas, as imagens sao usadas diretamente
(sem precisar da Etsy API). Caso contrario, o fluxo busca via API.

Uso:
    python scripts/read_input.py planilhas_links_artes/links_artes_PPJ_090426.xlsx

Saida: JSON para stdout com lista de objetos {url, img_capa, img1, img2, img3}.
"""
import sys, json, re, os


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

        # Detectar coluna com URL Etsy (pode estar em qualquer coluna)
        etsy_url = ""
        img_capa = ""
        img1 = img2 = img3 = ""

        # Verificar se a linha tem formato estruturado (col A = etsy URL)
        col_a = linha[0] if len(linha) > 0 else ""
        if re.search(r'etsy\.com/(?:pt/)?listing/\d+', col_a):
            etsy_url = limpar_url(col_a)
            img_capa = limpar_url(linha[1]) if len(linha) > 1 else ""
            img1     = limpar_url(linha[2]) if len(linha) > 2 else ""
            img2     = limpar_url(linha[3]) if len(linha) > 3 else ""
            img3     = limpar_url(linha[4]) if len(linha) > 4 else ""
        else:
            # Formato antigo: escanear todas as celulas por URL Etsy
            for cell in linha:
                if cell and re.search(r'etsy\.com/(?:pt/)?listing/\d+', cell):
                    etsy_url = limpar_url(cell)
                    break

        if not etsy_url or etsy_url in seen_urls:
            continue

        seen_urls.add(etsy_url)
        resultados.append({
            "url": etsy_url,
            "img_capa": img_capa,
            "img1": img1,
            "img2": img2,
            "img3": img3,
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
