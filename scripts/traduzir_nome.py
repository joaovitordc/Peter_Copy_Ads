"""
traduzir_nome.py - Traduz titulo de anuncio Etsy para nome curto em portugues
+ identifica tipo do produto (Q1, KIT2, KIT3, KIT5, KIT6, KIT8).

Usa OpenAI GPT-4o-mini (substituiu Gemini 2.5 Flash em 28/04/2026 apos 8/39 falhas
com erro 503 em validacao real).
Custo: ~US$0.0001 por chamada (~3x mais barato que Gemini Flash).
Tempo: ~1 segundo.

Fix v3 (28/04/2026): aceita tema_loja para gerar nomes tematicos quando
titulo Etsy e generico. Pos-processamento remove preposicoes/conjuncoes
no final do SKU PascalCase via regex de palavras reais.

Fix v4 (28/04/2026): banidas categorias de produto no display
(Conjunto, Arte/Artes, Poster*, Cartaz*, Imagem*, Quadro*, Decoracao);
LLM agora INVENTA nome tematico obrigatoriamente quando titulo Etsy e
generico. Sanitiza acentos via unicodedata.normalize antes da regex
PascalCase (fix do bug PosteresF, onde LLM retornou acento por engano
e regex ASCII quebrou).

Uso programatico:
    from scripts.traduzir_nome import traduzir_para_pt
    resultado = traduzir_para_pt(
        "Christian Wall Art Set of 3 Religious Posters",
        tema_loja="religioso, cristao, biblico",
    )
    # -> {"display": "Conjunto de 3 Posteres Cristaos",
    #     "curto":   "PosteresCristaos",
    #     "tipo":    "KIT3"}

Uso CLI:
    python scripts/traduzir_nome.py "Set of 3 Christian Posters" \
        --tema-loja "religioso, cristao"
"""
import os
import re
import sys
import json
import argparse
import unicodedata

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# Tipos validos suportados pelo sistema (do config.json)
TIPOS_VALIDOS = ["Q1", "KIT2", "KIT3", "KIT4", "KIT5", "KIT6", "KIT7", "KIT8", "KIT9"]

# Preposicoes/conjuncoes/artigos que nao devem terminar um SKU
SUFIXOS_INVALIDOS = {
    "De", "Da", "Do", "Em", "Para", "Por", "Com",
    "No", "Na", "E", "Ou", "O", "A", "Os", "As",
}

# Captura palavras PascalCase reais: "JesusEACapturaMilagrosaDe"
# -> ["Jesus", "E", "A", "Captura", "Milagrosa", "De"]
_PASCAL_WORD_RE = re.compile(r'[A-Z][a-z]*|[A-Z]+(?=[A-Z]|$)')


def _limpar_sufixo_sku(curto: str) -> str:
    """Remove preposicoes/conjuncoes/artigos no final do SKU PascalCase.

    Sanitiza acentos primeiro (LLM as vezes ignora regra "no accents"),
    depois quebra em palavras PascalCase reais via regex.
    """
    if not curto:
        return curto

    # Sanitizar acentos antes do processamento (defesa contra LLM mandar acento)
    curto = unicodedata.normalize('NFD', curto)
    curto = ''.join(c for c in curto if unicodedata.category(c) != 'Mn')

    # Remover qualquer caractere nao-ASCII restante (cedilha, etc)
    curto = ''.join(c for c in curto if c.isascii())

    palavras = _PASCAL_WORD_RE.findall(curto)
    while palavras and palavras[-1] in SUFIXOS_INVALIDOS:
        palavras.pop()
    return "".join(palavras)


SYSTEM_PROMPT = """You are an expert at translating Etsy product titles into short Portuguese identifiers for a Brazilian decorative art shop.

Your task is to extract from each Etsy title:
1. The SUBJECT of the artwork (what is depicted), in Portuguese
2. Whether it's a single piece (Q1) or a kit/set (KIT2, KIT3, KIT5, KIT6, KIT8)

═══ Rules for naming ═══

[DISPLAY NAME — 2-4 words, the SUBJECT only]
- Output 2-4 Portuguese words describing what the art DEPICTS (the subject)
- Use proper Portuguese accents in display name
- Numbers ARE allowed in display when meaningful (Bible verses like "Romanos 15:13", quantities like "Jesus Alimenta 5000")

[SHORT IDENTIFIER (curto) — PascalCase, 12-20 chars IDEAL]
- Choose the 2-3 MOST DISTINCTIVE words from the display name
- Do NOT include every word — pick words that uniquely identify this art
- PascalCase WITHOUT accents (Á→A, É→E, Ê→E, Ç→C, Õ→O, Ã→A, etc)
- Portuguese conjunction "e" stays capital E
- NEVER end with a preposition, conjunction or article: De, Da, Do, Em, Para, Por, Com, No, Na, E, Ou, O, A, Os, As
- If natural truncation would end with one of these, drop that word entirely

═══ BANNED NOUNS (NEVER use as the subject in display or curto) ═══

These are product categories or generic words. They are redundant with the
shop's product type prefix (Kit N Quadros, Quadro) or too generic to identify
the art:

- Conjunto, Conjuntos
- Arte, Artes
- Poster, Posteres, Pôster, Pôsteres, Posters
- Cartaz, Cartazes
- Imagem, Imagens
- Quadro, Quadros
- Decoração, Decoracao

If the Etsy title literally says "Set of 3 Wall Art Posters", you MUST replace
this with a thematic noun (see "MANDATORY thematic invention" below).

═══ Generic/SEO words to REMOVE (do not include in display or curto) ═══

Portuguese: arte de parede, impressao, impressoes, impressão, impressões,
para impressao, decorativo, decorativa, com moldura, sem moldura, para sala,
para quarto, para escritorio, para bercario, download, digital, baixar,
moderno, moderna, modernos, modernas, minimalista, minimalistas, contemporaneo,
contemporanea, vintage, boho, bohemian, aesthetic, abstract, abstrato, abstrata,
colorido, colorida.

English: print, prints, wall art, wall decor, home decor, modern, kit, framed,
unframed, digital download, set of, set, art print, poster, posters, framed art,
minimalist, contemporary, vintage, boho, aesthetic, abstract, colorful, decor.

═══ MANDATORY thematic invention ═══

If after removing banned/SEO words the title doesn't mention a SPECIFIC SUBJECT
(saint name, biblical scene, location, animal, abstract spiritual concept,
art style with named artist, geographical place), you MUST invent a thematic
noun based on the shop theme provided.

The shop theme will be provided as: "Shop theme: [keywords]"

Examples of generic→thematic conversion (PPJ, religious shop):

- "Set of 3 Wall Art Christian Posters" → "Fé Cristã" or "Devoção" (NOT "Posteres Cristãos")
- "Modern Christian Wall Art" → "Cristandade" or "Vida Cristã"
- "Religious Posters Set 3" → "Tríade da Fé" or "Trindade Sagrada"
- "Bible Wall Art" → "Sagradas Escrituras" or "Palavra de Deus"
- "Wall Art Boho Religious" → "Espiritualidade" or "Devoção"

Examples for iPaper (abstract/Bauhaus shop):

- "Set of 3 Modern Posters" → "Composição Moderna" or "Geometria Bauhaus"
- "Wall Art Abstract" → "Abstração Cromática" or "Forma Geométrica"

Examples for AllQuadros (vintage/nature shop):

- "Wall Art Vintage" → "Cena Vintage" or "Paisagem Retrô"
- "Botanical Wall Art" → "Botânica Tropical" or "Folhagem"

Even if it sounds slightly artificial, NEVER fall back to using the banned
nouns. Inventing a thematic name is REQUIRED, not optional.

═══ Type detection rules ═══

- "Set of 2", "diptych", "duo", "Conjunto de 2", "2 quadros" → KIT2
- "Set of 3", "trio", "Conjunto de 3", "3 prints", "3 quadros" → KIT3
- "Set of 4", "Conjunto de 4", "4 prints", "4 quadros" → KIT4
- "Set of 5", "Conjunto de 5", "5 prints", "5 quadros" → KIT5
- "Set of 6", "Conjunto de 6", "6 prints", "6 quadros" → KIT6
- "Set of 7", "Conjunto de 7", "7 prints", "7 quadros" → KIT7
- "Set of 8", "Conjunto de 8", "8 prints", "8 quadros" → KIT8
- "Set of 9", "Conjunto de 9", "9 prints", "9 quadros" → KIT9
- Otherwise → Q1

═══ Examples (with shop theme) ═══

Input: "Jesus and the Lost Sheep Bible Art Print"
Shop theme: "religioso, cristão, bíblico"
Output: {"display": "Ovelha Perdida", "curto": "OvelhaPerdida", "tipo": "Q1"}

Input: "Set of 3 Christian Wall Art Religious Posters Modern Home Decor"
Shop theme: "religioso, cristão, bíblico"
Output: {"display": "Cristandade", "curto": "Cristandade", "tipo": "KIT3"}
(NOTE: NO "Posteres" or "Conjunto" in display — invented thematic noun)

Input: "Conjunto De 3 Artes De Parede Modernas"
Shop theme: "religioso, cristão, bíblico"
Output: {"display": "Vida Cristã", "curto": "VidaCrista", "tipo": "KIT3"}
(NOTE: NO "Conjunto" or "Artes" — invented from theme)

Input: "Romans 15:13 Bible Verse Wall Art Hope"
Shop theme: "religioso, cristão, bíblico"
Output: {"display": "Romanos 15:13 Esperança", "curto": "Romanos15Esperanca", "tipo": "Q1"}
(NOTE: number IS allowed in display when meaningful — verse reference)

Input: "Set of 3 Modern Bauhaus Posters Geometric"
Shop theme: "abstrato, moderno, Bauhaus, geométrico"
Output: {"display": "Composição Bauhaus", "curto": "ComposicaoBauhaus", "tipo": "KIT3"}
(NOTE: NO "Posteres" — invented from theme)

Input: "Vintage Botanical Wall Art Print"
Shop theme: "vintage, natureza, floral"
Output: {"display": "Botânica Vintage", "curto": "BotanicaVintage", "tipo": "Q1"}"""


USER_PROMPT_BASE = (
    "Etsy title: \"{titulo}\"\n"
    "Shop theme: \"{tema_loja}\"\n\n"
    "Return JSON with display, curto, tipo."
)

USER_PROMPT_EVITAR = (
    "\n\nIMPORTANT: These short identifiers are ALREADY taken and CANNOT be reused. "
    "Generate DIFFERENT ones (use synonyms or different aspects of the subject):\n{evitar_lista}"
)


def traduzir_para_pt(
    titulo_etsy: str,
    tema_loja: str = "",
    evitar: list[str] | None = None,
) -> dict:
    """
    Traduz titulo Etsy via GPT-4o-mini.

    Args:
        titulo_etsy: titulo original do anuncio Etsy
        tema_loja:   tema/keywords da loja (ex: "religioso, cristao, biblico").
                     Quando vazio, LLM funciona sem fallback tematico.
        evitar:      lista de nome_curto ja em uso (para retry de conflito SKU)

    Returns:
        dict com chaves: display (str), curto (str), tipo (str em TIPOS_VALIDOS)
        Em caso de erro retorna {"display": "", "curto": "", "tipo": "Q1"} -
        chamador usa fallback gerar_nome_arte().
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERRO] OPENAI_API_KEY nao configurada no .env", file=sys.stderr)
        return {"display": "", "curto": "", "tipo": "Q1"}

    try:
        from openai import OpenAI
    except ImportError:
        print("[ERRO] openai nao instalado. Rode: pip install openai", file=sys.stderr)
        return {"display": "", "curto": "", "tipo": "Q1"}

    try:
        client = OpenAI(api_key=api_key)

        user_prompt = USER_PROMPT_BASE.format(titulo=titulo_etsy, tema_loja=tema_loja)
        if evitar:
            evitar_str = "\n".join(f"  - {n}" for n in evitar)
            user_prompt += USER_PROMPT_EVITAR.format(evitar_lista=evitar_str)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # baixa pra consistencia, nao zero pra permitir retry com 'evitar'
            max_tokens=200,
        )

        text = response.choices[0].message.content or "{}"
        data = json.loads(text)

        display = (data.get("display") or "").strip()
        curto = (data.get("curto") or "").strip()
        tipo = (data.get("tipo") or "Q1").strip().upper()

        # Validacao do tipo - se LLM retornar invalido, fallback Q1
        if tipo not in TIPOS_VALIDOS:
            print(f"[AVISO] tipo invalido '{tipo}' do LLM, usando Q1", file=sys.stderr)
            tipo = "Q1"

        # Pos-processamento: remove preposicoes/conjuncoes finais
        curto = _limpar_sufixo_sku(curto)

        # Cap final de seguranca (max 25 para deixar 5 chars para prefixo TIPO_)
        if len(curto) > 25:
            curto = curto[:25]
            curto = _limpar_sufixo_sku(curto)  # re-limpa apos truncar

        return {"display": display, "curto": curto, "tipo": tipo}

    except Exception as e:
        print(f"[ERRO] traduzir_para_pt falhou: {e}", file=sys.stderr)
        return {"display": "", "curto": "", "tipo": "Q1"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("titulo", help="Titulo do anuncio Etsy")
    parser.add_argument(
        "--tema-loja",
        default="",
        help="Tema da loja (ex: 'religioso, cristao, biblico')",
    )
    args = parser.parse_args()

    resultado = traduzir_para_pt(args.titulo, tema_loja=args.tema_loja)
    print(json.dumps({
        "input":     args.titulo,
        "tema_loja": args.tema_loja,
        "display":   resultado["display"],
        "curto":     resultado["curto"],
        "tipo":      resultado["tipo"],
    }, indent=2, ensure_ascii=False))
