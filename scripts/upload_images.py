"""
upload_images.py — Faz upload de imagens no ImgBB e retorna URLs diretas.

Uso:
    python scripts/upload_images.py <url_img1> [url_img2] [url_img3] ...

Saida: JSON para stdout com lista de URLs diretas do ImgBB.

A API ImgBB aceita upload por URL diretamente, sem necessidade de baixar as imagens.
URLs retornadas terminam em .jpg ou .png (formato aceito pela Shopee).
"""
import sys, json, os, time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
DELAY_ENTRE_UPLOADS = 0.6  # segundos


def upload_url(image_url: str, nome: str = "") -> str | None:
    """Envia uma URL de imagem ao ImgBB e retorna a URL direta resultante."""
    if not IMGBB_API_KEY or IMGBB_API_KEY == "sua_chave_aqui":
        print("[ERRO] IMGBB_API_KEY nao configurada no .env", file=sys.stderr)
        sys.exit(1)

    try:
        resp = requests.post(
            IMGBB_UPLOAD_URL,
            data={"key": IMGBB_API_KEY, "image": image_url},
            timeout=30,
        )
        data = resp.json()
        if data.get("success"):
            url = data["data"]["display_url"]
            print(f"  OK: {image_url[:60]}... -> {url}", file=sys.stderr)
            return url
        else:
            print(f"  [ERRO] ImgBB: {data.get('error', {}).get('message', 'desconhecido')}", file=sys.stderr)
            # Retry uma vez
            time.sleep(2)
            resp2 = requests.post(
                IMGBB_UPLOAD_URL,
                data={"key": IMGBB_API_KEY, "image": image_url},
                timeout=30,
            )
            data2 = resp2.json()
            if data2.get("success"):
                url = data2["data"]["display_url"]
                print(f"  OK (retry): {url}", file=sys.stderr)
                return url
            return None
    except Exception as e:
        print(f"  [ERRO] Excecao ao fazer upload: {e}", file=sys.stderr)
        return None


def upload_imagens(urls: list[str]) -> list[str | None]:
    """Faz upload de uma lista de URLs, retorna lista de URLs ImgBB (ou None se falhou)."""
    resultados = []
    for i, url in enumerate(urls):
        if url:
            result = upload_url(url)
            resultados.append(result)
            if i < len(urls) - 1:
                time.sleep(DELAY_ENTRE_UPLOADS)
        else:
            resultados.append(None)
    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/upload_images.py <url1> [url2] [url3] ...", file=sys.stderr)
        sys.exit(1)

    input_urls = sys.argv[1:]
    print(f"[INFO] Enviando {len(input_urls)} imagens ao ImgBB...", file=sys.stderr)

    resultados = upload_imagens(input_urls)
    print(json.dumps(resultados, ensure_ascii=False))
