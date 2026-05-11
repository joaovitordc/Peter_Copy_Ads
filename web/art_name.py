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


def determinar_tipo(n_imagens: int, titulo: str, frame_count_capa: int = 0) -> str:
    """
    Determina o tipo do produto (Q1, KIT2, KIT3...) a partir de pistas no titulo
    e, opcionalmente, do numero de frames detectados na imagem de capa.

    IMPORTANTE: NAO usa n_imagens (numero de fotos do anuncio) como fallback.
    Um anuncio de quadro solo tipicamente tem 4-7 fotos (mockup, lifestyle, detalhe).
    Esse parametro fica aceito por compatibilidade mas e ignorado.

    Args:
        n_imagens: ignorado (compatibilidade).
        titulo: titulo do anuncio Etsy (ingles ou portugues).
        frame_count_capa: numero de quadros detectados na imagem de capa pelo
                          filtro Gemini. Se >=2 e titulo silente, vira KIT_N.

    Prioridades:
      1. Padrao numerico no titulo: 'kit 3', 'set of 3', '3 quadros', '3 pieces' etc.
      2. Padrao nomeado: 'trio'->KIT3, 'duo'/'diptych'/'diptico'->KIT2,
         'triptych'/'triptico'->KIT3.
      3. frame_count_capa >= 2: vira KIT{frame_count_capa} (capped em 8).
      4. Default: Q1.
    """
    titulo_lower = titulo.lower()

    # 1. Padrao numerico
    for n in [9, 8, 7, 6, 5, 4, 3, 2]:
        patterns = [
            # Padroes em ingles
            f"kit {n}",
            f"kit de {n}",
            f"set of {n}",
            f"set {n}",
            f"{n} quadros",
            f"{n} prints",
            f"{n} pieces",
            f"{n} piece ",
            f"{n} panel",
            f"{n} panels",
            f"{n} parts",
            f"{n} pcs",
            # Padroes em portugues (bug 28/04/2026: slugs PT nao batiam)
            f"conjunto de {n}",
            f"conjunto {n}",
            f"de {n} posteres",
            f"de {n} posters",
            f"de {n} quadros",
            f"de {n} artes",
            f"de {n} prints",
            f"de {n} impressoes",
            f"{n} pecas",
            f"{n} peças",
            f"{n} posteres",
        ]
        for p in patterns:
            if p in titulo_lower:
                return f"KIT{n}"

    # 2. Padroes nomeados
    nomeados = {
        "trio":      "KIT3",
        "triptych":  "KIT3",
        "triptico":  "KIT3",  # sem acento (titulo_lower passa por remover_acentos)
        "tríptico":  "KIT3",
        "diptych":   "KIT2",
        "diptico":   "KIT2",
        "díptico":   "KIT2",
        "duo":       "KIT2",
        "duet":      "KIT2",
    }
    for palavra, tipo in nomeados.items():
        # Match como palavra inteira (com bordas) para nao pegar 'duo' dentro de 'duomo'
        if re.search(rf'\b{re.escape(palavra)}\b', titulo_lower):
            return tipo

    # 3. Frame count da capa como tiebreaker
    if frame_count_capa >= 2:
        n = min(frame_count_capa, 9)
        # Mapear para tipos validos (KIT2 a KIT9, todos suportados)
        validos = [2, 3, 4, 5, 6, 7, 8, 9]
        n_proximo = min(validos, key=lambda v: abs(v - n))
        return f"KIT{n_proximo}"

    # 4. Default
    return "Q1"


def gerar_nome_arte(
    titulo_etsy: str,
    n_imagens: int = 1,
    frame_count_capa: int = 0,
) -> tuple[str, str, str]:
    """
    Gera (nome_sku, nome_display, tipo) a partir do titulo de um anuncio Etsy.

    nome_sku:     PascalCase sem acentos  (para o SKU, MAX 30 chars)
    nome_display: Nome limpo com acentos  (para ERP e titulo Shopee)
    tipo:         Q1, KIT2, KIT3, etc.

    Args:
        titulo_etsy:      titulo do anuncio (ingles ou portugues).
        n_imagens:        ignorado (compatibilidade).
        frame_count_capa: numero de quadros detectados na capa pelo filtro Gemini.
                          Usado quando o titulo nao tem pistas explicitas de kit.

    Regra de negocio: SKU nunca pode passar de 30 chars (ideal 15-20).
    Se passar, mantem so as primeiras N palavras significativas.
    """
    # 1. Extrair nome display
    nome_display = _extrair_nome_display(titulo_etsy)

    # 2. Gerar SKU PascalCase
    nome_sku = para_pascal_case(nome_display)

    # 3. Se SKU passou de 30 chars, truncar por palavras significativas
    if len(nome_sku) > 30:
        palavras = nome_display.split()
        for n in (3, 2, 1):
            if n > len(palavras):
                continue
            cand_display = ' '.join(palavras[:n])
            cand_sku = para_pascal_case(cand_display)
            if 0 < len(cand_sku) <= 30:
                nome_display = cand_display
                nome_sku = cand_sku
                break
        else:
            # Hard cap absoluto se nem 1 palavra coube
            nome_sku = nome_sku[:30]

    # 4. Determinar tipo
    tipo = determinar_tipo(n_imagens, titulo_etsy, frame_count_capa=frame_count_capa)

    return nome_sku, nome_display, tipo


def gerar_titulo_seo(loja: str, nome_display: str, tipo: str, titulo_etsy: str, config: dict) -> str:
    """
    Gera o titulo SEO para a Shopee usando o template correto baseado em tipo.
    - Q1: usa titulo_padrao_q1 (Quadro Decorativo singular)
    - KITN: usa titulo_padrao_kit, com {n} substituido e {seo} pluralizado
    Limita a 120 caracteres.
    """
    loja_config = config["lojas"][loja]

    # Selecionar template baseado em tipo
    if tipo == "Q1":
        template = loja_config["titulo_padrao_q1"]
        seo_keywords = _extrair_seo_keywords(loja, titulo_etsy)
    else:  # KIT2, KIT3, KIT5, KIT6, KIT8
        template = loja_config["titulo_padrao_kit"]
        seo_singular = _extrair_seo_keywords(loja, titulo_etsy)
        seo_keywords = _pluralizar_pt(seo_singular)

    # Determinar n (numero de quadros no kit, vazio para Q1)
    n = tipo[3:] if tipo.startswith("KIT") else "1"

    titulo = template.format(
        seo=seo_keywords,
        nome_arte=nome_display,
        n=n,
    )

    # Remover espacos duplos quando seo_keywords e vazio
    titulo = re.sub(r'  +', ' ', titulo).strip()

    # Garantir limite de 120 chars
    if len(titulo) > 120:
        # Tentar reduzir removendo SEO
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
        "DecorKids": [
            # Safari (especifico)
            ("safari",        "Safari"),
            # Animais Fofos (generico de animais)
            ("cute animal",   "Animais Fofos"),
            ("animal",        "Animais Fofos"),
            ("animals",       "Animais Fofos"),
            # Natureza Boho
            ("nature",        "Natureza Boho"),
            ("boho",          "Natureza Boho"),
            # Transporte (veiculos diversos)
            ("transport",     "Transporte"),
            ("vehicle",       "Transporte"),
            ("truck",         "Transporte"),
            ("plane",         "Transporte"),
            ("train",         "Transporte"),
            # Carros
            ("cars",          "Carros"),
            ("car ",          "Carros"),  # com espaco evita match em "card", "carry"
            ("carro",         "Carros"),
            # Fundo do Mar
            ("under the sea", "Fundo do Mar"),
            ("ocean",         "Fundo do Mar"),
            ("underwater",    "Fundo do Mar"),
            ("sea",           "Fundo do Mar"),
            ("fish",          "Fundo do Mar"),
            ("whale",         "Fundo do Mar"),
            # Flores e Floral (vira "Flores e Florais" em KIT via PLURAL_MAP existente)
            ("floral",        "Flores e Floral"),
            ("flower",        "Flores e Floral"),
            ("flora",         "Flores e Floral"),
            # Arco Iris
            ("rainbow",       "Arco Iris"),
            # Fada (singular mantido em KIT)
            ("fairy",         "Fada"),
            ("fairies",       "Fada"),
            # Bailarina (singular mantido em KIT)
            ("ballerina",     "Bailarina"),
            ("ballet",        "Bailarina"),
            ("dancer",        "Bailarina"),
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
            "DecorKids": "",  # sem default tematico — template self-cleans espaço duplo
        }
        encontradas = [defaults.get(loja, "")]

    return ' '.join(encontradas)


# Mapeamento singular→plural para keywords SEO em português.
# Usado quando template KIT precisa concordar em número (Modernos, Minimalistas, etc).
# Palavras estrangeiras (Bauhaus, Vintage, Boho) e substantivos coletivos
# (Natureza, Design) não mudam.
_PLURAL_MAP = {
    # PPJ
    "religioso":            "religiosos",
    "cristão":              "cristãos",
    "espiritual":           "espirituais",
    "minimalista":          "minimalistas",
    "com textos bíblicos":  "com textos bíblicos",  # locução fixa

    # iPaper
    "bauhaus":              "bauhaus",      # estrangeira
    "vintage":              "vintage",      # estrangeira
    "moderno":              "modernos",
    "geométrico":           "geométricos",
    "design":               "design",       # substantivo invariante
    "aesthetic":            "aesthetic",    # estrangeira
    "contemporâneo":        "contemporâneos",
    "arte abstrata":        "artes abstratas",

    # AllQuadros
    "natureza":             "natureza",     # substantivo coletivo
    "tropical":             "tropicais",
    "floral":               "florais",
    "botânico":             "botânicos",
    "abstrato":             "abstratos",
    "boho":                 "boho",         # estrangeira

    # Genéricos
    "decorativo":           "decorativos",
}


def _pluralizar_pt(palavras_seo: str) -> str:
    """Pluraliza palavras SEO para uso em template de KIT.

    - Locuções com mais de uma palavra são tratadas primeiro (match longo)
    - Palavras desconhecidas mantêm singular (LLM/futuras adições)
    - Capitalização original é preservada
    """
    if not palavras_seo or not palavras_seo.strip():
        return palavras_seo

    texto = palavras_seo

    # Match de locuções primeiro (chaves com espaço), ordenadas por tamanho desc
    locucoes = sorted(
        [k for k in _PLURAL_MAP if " " in k],
        key=len,
        reverse=True,
    )
    for loc in locucoes:
        # Match case-insensitive, preserva capitalização do plural
        pattern = re.compile(re.escape(loc), re.IGNORECASE)
        match = pattern.search(texto)
        if match:
            original = match.group(0)
            plural = _PLURAL_MAP[loc]
            # Preserva capitalização da primeira letra
            if original[0].isupper():
                plural = plural[0].upper() + plural[1:]
            texto = pattern.sub(plural, texto, count=1)

    # Match de palavras simples
    palavras = texto.split()
    resultado = []
    for palavra in palavras:
        palavra_lower = palavra.lower()
        if palavra_lower in _PLURAL_MAP:
            plural = _PLURAL_MAP[palavra_lower]
            # Preserva capitalização
            if palavra[0].isupper():
                plural = plural[0].upper() + plural[1:]
            resultado.append(plural)
        else:
            resultado.append(palavra)  # desconhecida, mantém

    return " ".join(resultado)
