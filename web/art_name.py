"""
art_name.py — Gera o nome da arte (SKU + display) a partir do titulo Etsy.

Regras de .claude/regras-nome-arte.md:
- SKU: PascalCase, sem acentos, sem espacos, "e" vira "E", romanos maiusculos
- Display: nome da arte limpo, com acentos e espacos
"""
import re
import unicodedata

# Palavras SEO que NAO entram no nome da arte
SEO_WORDS = {
    "moderno", "moderna", "modernos", "modernas",
    "minimalista", "minimalistas",
    "aesthetic",
    "contemporaneo", "contemporanea", "contemporaneo",
    "para sala", "para quarto", "para escritorio",
    "sala", "quarto", "escritorio",
    "kit", "quadro", "quadros", "conjunto",
    "arte de parede", "decorativo", "decorativos", "decorativa", "decorativas",
    "decoracao",
    "com moldura", "sem moldura",
    "estampado", "estampada", "impresso", "impressa",
    "wall art", "print", "poster", "home decor", "digital download",
    "framed", "unframed", "canvas",
    "art print", "wall decor", "wall hanging",
    "set of", "set",
    "boho", "bohemian",
    "vintage",
    "abstract", "abstrato", "abstrata",
    "colorful", "colorido", "colorida",
}

# Regex para algarismos romanos (palavras isoladas)
ROMAN_RE = re.compile(r'^(M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3}))$', re.IGNORECASE)


def remover_acentos(texto: str) -> str:
    """Remove acentos e cedilha, mantendo letras latinas."""
    nfkd = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _eh_romano(palavra: str) -> bool:
    """Verifica se uma palavra e um numero romano valido (nao vazio)."""
    if not palavra:
        return False
    return bool(ROMAN_RE.match(palavra)) and palavra.upper() != ''


def para_pascal_case(nome: str) -> str:
    """
    Converte um nome de arte para PascalCase sem acentos.
    Regras:
    - "e" (conjuncao portuguesa) vira "E" maiusculo
    - Algarismos romanos ficam totalmente maiusculos
    - Caracteres especiais como ":" sao removidos (ex: "Salmo 46:10" -> "Salmo4610")
    """
    # Remover acentos
    sem_acentos = remover_acentos(nome)

    # Remover ":" e outros separadores que devem ser ignorados (nao geram espaco)
    sem_acentos = re.sub(r'[:;]', '', sem_acentos)

    # Substituir hifens e underscores por espaco
    sem_acentos = re.sub(r'[-_]', ' ', sem_acentos)

    # Remover outros caracteres nao alfanumericos (exceto espaco)
    sem_acentos = re.sub(r'[^a-zA-Z0-9 ]', '', sem_acentos)

    # Dividir em palavras
    palavras = sem_acentos.split()
    if not palavras:
        return ""

    resultado = []
    for palavra in palavras:
        if not palavra:
            continue
        # Conjuncao "e" vira "E"
        if palavra.lower() == 'e':
            resultado.append('E')
        # "and" em ingles: PascalCase normal -> "And"
        elif palavra.lower() == 'and':
            resultado.append('And')
        # Algarismo romano: manter maiusculo
        elif _eh_romano(palavra):
            resultado.append(palavra.upper())
        else:
            resultado.append(palavra.capitalize())

    return ''.join(resultado)


def _filtrar_seo(texto: str) -> str:
    """Remove palavras SEO de um texto, retornando o que sobrar."""
    palavras = texto.split()
    resultado = []
    i = 0
    while i < len(palavras):
        bigrama = (palavras[i].lower() + ' ' + palavras[i + 1].lower()) if i + 1 < len(palavras) else ""
        if bigrama in SEO_WORDS:
            i += 2
            continue
        if palavras[i].lower() in SEO_WORDS:
            i += 1
            continue
        resultado.append(palavras[i])
        i += 1
    nome = ' '.join(resultado).strip()
    return re.sub(r'[,.\-–—|]+$', '', nome).strip()


def _extrair_nome_display(titulo: str) -> str:
    """
    Extrai o nome da arte do titulo Etsy, removendo palavras SEO.
    Mantém acentos e capitalização original das palavras restantes.

    Estrategia:
    - Se ha separadores (|, -, –), divide e escolhe a parte mais "arte"
      (geralmente a primeira parte nao-SEO)
    - Caso contrario, remove SEO words do titulo inteiro
    """
    # Remover parenteses e conteudo entre parenteses
    titulo_limpo = re.sub(r'\(.*?\)', '', titulo).strip()

    # Tentar dividir por separadores comuns em titulos Etsy
    partes = re.split(r'\s*[|–—]\s*|\s+-\s+', titulo_limpo)
    partes = [p.strip() for p in partes if p.strip()]

    if len(partes) >= 2:
        # Escolher a PRIMEIRA parte que sobra algo apos filtrar SEO
        # (a arte costuma vir no inicio ou no fim com hifen)
        candidatos = []
        for p in partes:
            filtrado = _filtrar_seo(p)
            if filtrado:
                candidatos.append((p, filtrado))

        if candidatos:
            # Preferir partes mais curtas e sem muitas palavras SEO
            # A primeira parte com conteudo util e geralmente o nome da arte
            melhor = candidatos[0][1]
            return melhor

    # Sem separadores: filtrar SEO do titulo completo
    nome = _filtrar_seo(titulo_limpo)
    return nome if nome else titulo_limpo


def determinar_tipo(n_imagens: int, titulo: str) -> str:
    """
    Determina o tipo do produto (Q1, KIT2, KIT3...) a partir de pistas no titulo e
    no numero de imagens.
    """
    titulo_lower = titulo.lower()

    # Tentar detectar kit pelo titulo
    for n in [8, 6, 5, 3, 2]:
        patterns = [
            f"kit {n}",
            f"kit de {n}",
            f"set of {n}",
            f"set {n}",
            f"{n} quadros",
            f"{n} prints",
            f"{n} pieces",
            f"{n} panel",
        ]
        for p in patterns:
            if p in titulo_lower:
                if n == 1:
                    return "Q1"
                return f"KIT{n}"

    # Fallback por numero de imagens
    if n_imagens >= 6:
        return "KIT6"
    elif n_imagens >= 5:
        return "KIT5"
    elif n_imagens >= 3:
        return "KIT3"
    elif n_imagens >= 2:
        return "KIT2"
    return "Q1"


def gerar_nome_arte(titulo_etsy: str, n_imagens: int = 1) -> tuple[str, str, str]:
    """
    Gera (nome_sku, nome_display, tipo) a partir do titulo de um anuncio Etsy.

    nome_sku:     PascalCase sem acentos  (para o SKU)
    nome_display: Nome limpo com acentos  (para ERP e titulo Shopee)
    tipo:         Q1, KIT2, KIT3, etc.
    """
    # 1. Extrair nome display
    nome_display = _extrair_nome_display(titulo_etsy)

    # 2. Gerar SKU PascalCase
    nome_sku = para_pascal_case(nome_display)

    # 3. Determinar tipo
    tipo = determinar_tipo(n_imagens, titulo_etsy)

    return nome_sku, nome_display, tipo


def gerar_titulo_seo(loja: str, nome_display: str, tipo: str, titulo_etsy: str, config: dict) -> str:
    """
    Gera o titulo SEO para a Shopee usando o template da loja.
    Limita a 120 caracteres.
    """
    template = config["lojas"][loja]["titulo_padrao"]

    # Determinar n (numero de quadros no kit)
    n = tipo[3:] if tipo.startswith("KIT") else "1"

    # Extrair keywords SEO relevantes do titulo Etsy (que NAO sao o nome da arte)
    seo_keywords = _extrair_seo_keywords(loja, titulo_etsy)

    titulo = template.format(
        seo=seo_keywords,
        nome_arte=nome_display,
        n=n,
    )

    # Remover espacos duplos que ocorrem quando seo_keywords e vazio
    titulo = re.sub(r'  +', ' ', titulo).strip()

    # Garantir limite de 120 chars
    if len(titulo) > 120:
        # Tentar reduzir keywords SEO
        titulo_min = template.format(seo='', nome_arte=nome_display, n=n)
        titulo_min = re.sub(r'  +', ' ', titulo_min).strip()
        titulo = titulo_min[:120]

    return titulo


def _extrair_seo_keywords(loja: str, titulo_etsy: str) -> str:
    """
    Extrai/seleciona palavras-chave SEO adequadas para a loja a partir do titulo Etsy.
    """
    titulo_lower = remover_acentos(titulo_etsy.lower())

    # Keywords por loja (em ordem de preferencia)
    keywords_por_loja = {
        "PPJ": [
            ("religioso", "Religioso"),
            ("christian", "Religioso"),
            ("cristao", "Cristão"),
            ("biblical", "Com Textos Bíblicos"),
            ("biblic", "Com Textos Bíblicos"),
            ("salmo", "Com Textos Bíblicos"),
            ("psalm", "Com Textos Bíblicos"),
            ("faith", "Religioso"),
            ("god", "Religioso"),
            ("jesus", "Religioso"),
            ("pray", "Religioso"),
            ("espiritu", "Espiritual"),
            ("minimalista", "Minimalista"),
            ("minimalist", "Minimalista"),
        ],
        "iPaper": [
            ("bauhaus", "Bauhaus"),
            ("abstrat", "Arte Abstrata"),
            ("abstract", "Arte Abstrata"),
            ("geometric", "Geométrico"),
            ("vintage", "Vintage"),
            ("modern", "Moderno"),
            ("design", "Design"),
            ("aesthetic", "Aesthetic"),
            ("contempor", "Contemporâneo"),
            ("minimalista", "Minimalista"),
            ("minimalist", "Minimalista"),
        ],
        "AllQuadros": [
            ("vintage", "Vintage"),
            ("safari", "Natureza"),
            ("tropical", "Tropical"),
            ("floral", "Floral"),
            ("botanical", "Botanico"),
            ("abstract", "Abstrato"),
            ("modern", "Moderno"),
            ("minimalista", "Minimalista"),
            ("minimalist", "Minimalista"),
            ("aesthetic", "Aesthetic"),
        ],
    }

    keywords = keywords_por_loja.get(loja, [])
    encontradas = []

    for chave, label in keywords:
        if chave in titulo_lower and label not in encontradas:
            encontradas.append(label)
            if len(encontradas) >= 2:
                break

    # Se nenhuma keyword especifica encontrada, usar default por loja
    if not encontradas:
        defaults = {
            "PPJ": "Minimalista",
            "iPaper": "Arte Moderna",
            "AllQuadros": "Minimalista",
        }
        encontradas = [defaults.get(loja, "")]

    return ' '.join(encontradas)
