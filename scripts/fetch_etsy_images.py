"""
fetch_etsy_images.py — Busca as 3 primeiras imagens de um anuncio Etsy via API oficial.

Requer: ETSY_API_KEY no .env (keystring da Etsy Developer App)
Obter em: https://www.etsy.com/developers/register

Uso:
    python scripts/fetch_etsy_images.py <listing_id_ou_url> [<listing_id_2> ...]

Saida: JSON para stdout com lista de objetos {listing_id, titulo, imagens}
"""
import sys, json, os, re, time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

ETSY_API_KEY = os.environ.get("ETSY_API_KEY", "")
BASE_URL = "https://openapi.etsy.com/v3/application"
DELAY = 0.3  # segundos entre chamadas


def extract_listing_id(url_or_id: str) -> str:
    """Extrai o listing ID de uma URL ou retorna o ID direto."""
    m = re.search(r'/listing/(\d+)', url_or_id)
    if m:
        return m.group(1)
    if url_or_id.isdigit():
        return url_or_id
    raise ValueError(f"Nao foi possivel extrair listing ID de: {url_or_id}")


def get_listing_images(listing_id: str) -> list[str]:
    """Retorna lista de URLs das imagens (fullxfull) do listing."""
    if not ETSY_API_KEY:
        print("[ERRO] ETSY_API_KEY nao configurada no .env", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}/listings/{listing_id}/images"
    headers = {"x-api-key": ETSY_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            imgs = []
            for img in data.get("results", []):
                full = img.get("url_fullxfull") or img.get("url_570xN") or ""
                if full:
                    imgs.append(full)
            return imgs[:3]
        elif r.status_code == 403:
            print(f"  [ERRO] API key invalida ou sem permissao: {r.text[:100]}", file=sys.stderr)
            return []
        elif r.status_code == 404:
            print(f"  [AVISO] Listing {listing_id} nao encontrado (removido ou privado)", file=sys.stderr)
            return []
        else:
            print(f"  [ERRO] Status {r.status_code}: {r.text[:100]}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"  [ERRO] {e}", file=sys.stderr)
        return []


def get_listing_title(listing_id: str) -> str:
    """Retorna o titulo do listing."""
    headers = {"x-api-key": ETSY_API_KEY}
    url = f"{BASE_URL}/listings/{listing_id}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("title", "")
        return ""
    except Exception:
        return ""


def processar_listings(inputs: list[str]) -> list[dict]:
    resultados = []
    for inp in inputs:
        try:
            lid = extract_listing_id(inp)
        except ValueError as e:
            print(f"  [AVISO] {e}", file=sys.stderr)
            continue

        print(f"  Buscando {lid}...", file=sys.stderr)

        titulo = get_listing_title(lid)
        time.sleep(DELAY)
        imagens = get_listing_images(lid)
        time.sleep(DELAY)

        falhou = not titulo or not imagens
        resultados.append({
            "listing_id": lid,
            "titulo":     titulo,
            "imagens":    imagens,
            "url":        inp if "etsy.com" in inp else f"https://www.etsy.com/listing/{lid}",
            "_falhou":    falhou,
        })

        if falhou:
            print(f"    FALHA: {lid} - sem titulo ({not titulo}) ou sem imagens ({not imagens}). API pode estar bloqueada.", file=sys.stderr)
        elif titulo:
            print(f"    OK: \"{titulo[:60]}\" - {len(imagens)} imagens", file=sys.stderr)
        else:
            print(f"    OK: {lid} - {len(imagens)} imagens", file=sys.stderr)

    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/fetch_etsy_images.py <url_ou_id> [...]", file=sys.stderr)
        sys.exit(1)

    inputs = sys.argv[1:]
    print(f"[INFO] Buscando {len(inputs)} listings na Etsy API...", file=sys.stderr)
    resultados = processar_listings(inputs)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
