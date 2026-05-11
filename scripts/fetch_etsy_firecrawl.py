"""
fetch_etsy_firecrawl.py — Busca titulo + imagens de anuncios Etsy via Firecrawl agent.

Alternativa a fetch_etsy_images.py (que usa Etsy Open API). Ideal quando a chave
da Etsy nao foi aprovada ou para volumes que excedem o rate limit gratuito da Etsy.

Requer: FIRECRAWL_API_KEY no .env (https://www.firecrawl.dev/)

Uso:
    python scripts/fetch_etsy_firecrawl.py <url_etsy> [<url_etsy_2> ...]

Saida (mesmo formato de fetch_etsy_images.py.processar_listings):
    [{"listing_id": "...", "titulo": "...", "imagens": [...], "url": "...", "_falhou": False}]

Estrategia:
- Dispatch em paralelo (limitado por MAX_PARALLEL).
- Polling concorrente cada POLL_INTERVAL segundos.
- Timeout global TIMEOUT_TOTAL — quem nao terminar entra como _falhou=True.
"""
import sys
import os
import re
import json
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE = "https://api.firecrawl.dev/v2"

MAX_PARALLEL    = int(os.environ.get("FIRECRAWL_MAX_PARALLEL", "5"))
POLL_INTERVAL   = int(os.environ.get("FIRECRAWL_POLL_INTERVAL", "15"))
TIMEOUT_TOTAL   = int(os.environ.get("FIRECRAWL_TIMEOUT", "600"))   # 10 min por onda (schema atual e complexo)
MAX_CREDITS     = int(os.environ.get("FIRECRAWL_MAX_CREDITS", "1500"))  # creditos por job

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {
            "type": "string",
            "description": "Full original Etsy listing title (as displayed on the page).",
        },
        "img_capa": {
            "type": "string",
            "description": "Cover image direct CDN URL (i.etsystatic.com, ending in .jpg).",
        },
        "imagens_extras": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Up to 4 additional product image URLs in carousel order.",
        },
    },
    "required": ["titulo", "img_capa"],
}

EXTRACTION_PROMPT = (
    "Visit the Etsy listing URL and extract:\n"
    "(1) The full original product title as displayed on Etsy.\n"
    "(2) The cover image URL and up to 4 additional product image URLs "
    "(direct CDN URLs from i.etsystatic.com, prefer the largest version like "
    "il_fullxfull or il_794xN).\n"
    "If the page shows CAPTCHA or appears blocked, still return best-effort "
    "data from any cached/snippet content available."
)


def extract_listing_id(url_or_id: str) -> str:
    m = re.search(r'/listing/(\d+)', url_or_id)
    if m:
        return m.group(1)
    if url_or_id.isdigit():
        return url_or_id
    raise ValueError(f"Nao foi possivel extrair listing ID de: {url_or_id}")


def _titulo_do_slug(url: str) -> str:
    m = re.search(r'/listing/\d+/([^?/]+)', url)
    if not m:
        return ""
    slug = m.group(1)
    return ' '.join(w.capitalize() for w in slug.replace('-', ' ').split())


def _headers() -> dict:
    if not FIRECRAWL_API_KEY:
        raise RuntimeError("FIRECRAWL_API_KEY nao configurada no .env")
    return {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type":  "application/json",
    }


def _start_job(url: str) -> Optional[str]:
    """Dispara um job de extracao no Firecrawl. Retorna job_id ou None."""
    payload = {
        "urls":       [url],
        "prompt":     EXTRACTION_PROMPT,
        "schema":     EXTRACTION_SCHEMA,
        "model":      "spark-1-mini",
        "maxCredits": MAX_CREDITS,
    }
    try:
        r = requests.post(f"{FIRECRAWL_BASE}/agent", headers=_headers(), json=payload, timeout=30)
        if r.status_code != 200:
            print(f"  [ERRO] Firecrawl POST {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return None
        data = r.json()
        if not data.get("success"):
            print(f"  [ERRO] Firecrawl recusou job: {data}", file=sys.stderr)
            return None
        return data.get("id")
    except Exception as e:
        print(f"  [ERRO] Firecrawl POST: {e}", file=sys.stderr)
        return None


def _poll_job(job_id: str) -> dict:
    """Consulta status do job. Retorna dict bruto da API."""
    try:
        r = requests.get(f"{FIRECRAWL_BASE}/agent/{job_id}", headers=_headers(), timeout=30)
        if r.status_code != 200:
            return {"success": False, "status": "failed", "error": f"HTTP {r.status_code}"}
        return r.json()
    except Exception as e:
        return {"success": False, "status": "failed", "error": str(e)}


def _resultado_falha(url: str) -> dict:
    try:
        lid = extract_listing_id(url)
    except ValueError:
        lid = ""
    return {
        "listing_id": lid,
        "titulo":     _titulo_do_slug(url),
        "imagens":    [],
        "url":        url,
        "_falhou":    True,
    }


def _resultado_sucesso(url: str, data: dict) -> dict:
    try:
        lid = extract_listing_id(url)
    except ValueError:
        lid = ""

    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        titulo = _titulo_do_slug(url)

    imgs: list[str] = []
    capa = (data.get("img_capa") or "").strip()
    if capa:
        imgs.append(capa)
    for img in data.get("imagens_extras") or []:
        img = (img or "").strip()
        if img and img not in imgs:
            imgs.append(img)
        if len(imgs) >= 5:
            break

    return {
        "listing_id": lid,
        "titulo":     titulo,
        "imagens":    imgs[:5],
        "url":        url,
        "_falhou":    not titulo or not imgs,
    }


def _processar_onda(urls: list[str]) -> list[dict]:
    """Processa uma onda de ate MAX_PARALLEL URLs simultaneamente."""
    pending: dict[str, str] = {}  # url -> job_id
    resultados: dict[str, dict] = {}

    # Dispatch
    for url in urls:
        jid = _start_job(url)
        if jid:
            pending[url] = jid
            print(f"  [JOB] {url} -> {jid}", file=sys.stderr)
        else:
            resultados[url] = _resultado_falha(url)
            print(f"  [FALHA] dispatch {url}", file=sys.stderr)

    # Polling
    inicio = time.time()
    while pending and (time.time() - inicio) < TIMEOUT_TOTAL:
        time.sleep(POLL_INTERVAL)
        for url in list(pending.keys()):
            jid = pending[url]
            resp = _poll_job(jid)
            status = resp.get("status")

            if status == "completed":
                data = resp.get("data") or {}
                resultados[url] = _resultado_sucesso(url, data)
                titulo = resultados[url]["titulo"][:60]
                n = len(resultados[url]["imagens"])
                print(f"  [OK] {url}", file=sys.stderr)
                print(f"       titulo: \"{titulo}\" ({n} imagens)", file=sys.stderr)
                del pending[url]
            elif status == "failed":
                resultados[url] = _resultado_falha(url)
                err = resp.get("error") or ""
                # Se nao veio erro no top-level, pode ter vindo no data.refusal
                data = resp.get("data") or {}
                if not err and isinstance(data, dict):
                    err = data.get("refusal") or data.get("error") or ""
                if "max credits" in str(err).lower():
                    err = (
                        f"limite de creditos atingido (FIRECRAWL_MAX_CREDITS={MAX_CREDITS}). "
                        f"Aumente o valor no .env ou simplifique o schema."
                    )
                print(f"  [FALHA] {url}: {err}", file=sys.stderr)
                del pending[url]
            # status == "processing" -> continua

    # Antes de marcar como timeout, fazer um poll final - pode ter completado agora
    for url in list(pending.keys()):
        jid = pending[url]
        resp = _poll_job(jid)
        status = resp.get("status")
        if status == "completed":
            data = resp.get("data") or {}
            resultados[url] = _resultado_sucesso(url, data)
            titulo = resultados[url]["titulo"][:60]
            n = len(resultados[url]["imagens"])
            print(f"  [OK pos-timeout] {url}", file=sys.stderr)
            print(f"       titulo: \"{titulo}\" ({n} imagens)", file=sys.stderr)
            del pending[url]

    # O que sobrou em pending vira falha por timeout real
    for url in pending:
        resultados[url] = _resultado_falha(url)
        print(
            f"  [TIMEOUT] {url} (>{TIMEOUT_TOTAL}s) - "
            f"considere FIRECRAWL_TIMEOUT mais alto no .env",
            file=sys.stderr,
        )

    return [resultados[url] for url in urls]


def processar_listings(inputs: list[str]) -> list[dict]:
    """
    Recebe lista de URLs Etsy. Retorna lista de dicts com titulo + imagens.
    Mesma assinatura de fetch_etsy_images.processar_listings para hot-swap.
    """
    if not FIRECRAWL_API_KEY:
        print("[ERRO] FIRECRAWL_API_KEY nao configurada no .env", file=sys.stderr)
        return [_resultado_falha(u) for u in inputs]

    todos: list[dict] = []
    total = len(inputs)
    print(f"[INFO] Firecrawl: processando {total} URLs em ondas de {MAX_PARALLEL}...", file=sys.stderr)

    for i in range(0, total, MAX_PARALLEL):
        onda = inputs[i:i + MAX_PARALLEL]
        n_onda = i // MAX_PARALLEL + 1
        print(f"[INFO] Onda {n_onda}: {len(onda)} URLs", file=sys.stderr)
        todos.extend(_processar_onda(onda))

    sucessos = sum(1 for r in todos if not r.get("_falhou"))
    print(f"[INFO] Concluido: {sucessos}/{total} extraidos com sucesso", file=sys.stderr)
    return todos


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/fetch_etsy_firecrawl.py <url_etsy> [...]", file=sys.stderr)
        sys.exit(1)

    inputs = sys.argv[1:]
    resultados = processar_listings(inputs)
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
