"""
upload_images.py — Faz upload de imagens no ImgBB e retorna URLs diretas.

Desde 2026-05-16, as imagens sao **baixadas, cortadas em quadrado (1:1)
centralizado** e re-uploadeadas como JPEG (base64). Shopee exige imagens
quadradas pro card de listagem (CTR algoritmico). Se download/crop falhar
por qualquer motivo, faz fallback gracioso pra upload da URL original
(comportamento antigo).

Uso:
    python scripts/upload_images.py <url_img1> [url_img2] [url_img3] ...

Saida: JSON para stdout com lista de URLs diretas do ImgBB.
"""
import sys, json, os, io, base64, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
UPLOAD_WORKERS = 4          # paraleliza uploads via ThreadPoolExecutor
DOWNLOAD_TIMEOUT = 30       # segundos
JPEG_QUALITY = 92           # qualidade do JPEG re-encodado pos-crop

# User-Agent realista — alguns CDNs (Shopee, etc) podem bloquear bots
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _baixar_e_cortar_quadrado(image_url: str) -> bytes | None:
    """Baixa a imagem, faz crop quadrado centralizado, retorna JPEG bytes.

    Estrategia: lado_menor = min(width, height); recorta as bordas do lado
    maior pra ficar quadrado, mantendo o centro. NAO faz upscale — preserva
    qualidade original.

    Retorna None se download ou processamento falhar — chamador deve cair
    no fallback de uploading a URL original.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  [AVISO] Pillow nao instalado, pulando crop (fallback pra URL original)", file=sys.stderr)
        return None

    try:
        resp = requests.get(image_url, headers=_REQUEST_HEADERS, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))

        # JPEG nao suporta alpha — converte modo se necessario
        if img.mode in ("RGBA", "LA", "P"):
            # Fundo branco pra alpha (mais seguro pra quadros que tem fundo claro)
            fundo = Image.new("RGB", img.size, (255, 255, 255))
            img_rgba = img.convert("RGBA")
            fundo.paste(img_rgba, mask=img_rgba.split()[3] if img_rgba.mode == "RGBA" else None)
            img = fundo
        elif img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        lado = min(w, h)
        left = (w - lado) // 2
        top = (h - lado) // 2
        img_quadrada = img.crop((left, top, left + lado, top + lado))

        buf = io.BytesIO()
        img_quadrada.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception as e:
        print(f"  [AVISO] Falha no crop ({type(e).__name__}: {e}) — fallback pra URL original", file=sys.stderr)
        return None


def upload_url(image_url: str, nome: str = "") -> str | None:
    """Faz crop quadrado e envia ao ImgBB. Fallback pra URL direta se crop falhar."""
    if not IMGBB_API_KEY or IMGBB_API_KEY == "sua_chave_aqui":
        print("[ERRO] IMGBB_API_KEY nao configurada no .env", file=sys.stderr)
        sys.exit(1)

    # Tenta crop quadrado primeiro
    jpeg_bytes = _baixar_e_cortar_quadrado(image_url)
    if jpeg_bytes:
        payload = {"key": IMGBB_API_KEY, "image": base64.b64encode(jpeg_bytes).decode("ascii")}
        modo = "crop quadrado"
    else:
        # Fallback: ImgBB baixa direto da URL (sem garantia de quadrado)
        payload = {"key": IMGBB_API_KEY, "image": image_url}
        modo = "URL original (fallback)"

    try:
        resp = requests.post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
        data = resp.json()
        if data.get("success"):
            url = data["data"]["display_url"]
            print(f"  OK ({modo}): {image_url[:50]}... -> {url}", file=sys.stderr)
            return url
        else:
            print(f"  [ERRO] ImgBB: {data.get('error', {}).get('message', 'desconhecido')}", file=sys.stderr)
            # Retry uma vez (mesmo payload)
            time.sleep(2)
            resp2 = requests.post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
            data2 = resp2.json()
            if data2.get("success"):
                url = data2["data"]["display_url"]
                print(f"  OK (retry, {modo}): {url}", file=sys.stderr)
                return url
            return None
    except Exception as e:
        print(f"  [ERRO] Excecao ao fazer upload: {e}", file=sys.stderr)
        return None


def upload_imagens(urls: list[str]) -> list[str | None]:
    """Faz upload paralelo (UPLOAD_WORKERS=4) com crop quadrado por imagem.

    Mantem a ordem do input (mesmo terminando out-of-order entre threads).
    Falhas individuais viram None na posicao correspondente — nao derrubam
    o batch inteiro. Pra <=1 URL valida, faz sequencial pra evitar overhead
    de threading.
    """
    if not urls:
        return []

    validos = [(i, u) for i, u in enumerate(urls) if u]
    resultados: list[str | None] = [None] * len(urls)

    # Pra 0 ou 1 imagem valida, sequencial e mais barato
    if len(validos) <= 1:
        for i, u in validos:
            resultados[i] = upload_url(u)
        return resultados

    # Paralelo: 4 workers simultaneos. ImgBB aceita uploads concorrentes;
    # cada thread faz download + crop Pillow + upload base64 independente.
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as executor:
        futures = {executor.submit(upload_url, u): i for i, u in validos}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                resultados[i] = fut.result()
            except Exception as e:
                print(f"  [ERRO] Thread upload idx={i}: {e}", file=sys.stderr)
                resultados[i] = None

    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/upload_images.py <url1> [url2] [url3] ...", file=sys.stderr)
        sys.exit(1)

    input_urls = sys.argv[1:]
    print(f"[INFO] Enviando {len(input_urls)} imagens ao ImgBB...", file=sys.stderr)

    resultados = upload_imagens(input_urls)
    print(json.dumps(resultados, ensure_ascii=False))
