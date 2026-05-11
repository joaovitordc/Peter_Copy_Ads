"""
frame_detection.py — Detecta se uma imagem contem ao menos 1 quadro/frame.

Dois metodos:
  - opencv (padrao, gratuito): heuristica de contornos retangulares com area significativa
  - gemini (pago, ~US$0.00005/imagem): Gemini 2.5 Flash com structured output

Uso programatico:
    from scripts.frame_detection import tem_quadro
    ok, n_frames, motivo = tem_quadro("https://i.etsystatic.com/.../img.jpg")

Uso CLI:
    python scripts/frame_detection.py <url> [--method opencv|gemini] [--min-area-pct 0.05]
"""
import os
import sys
import json
import time
import argparse
import tempfile
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ── Cache em memoria por URL para evitar reprocessar ──────────────────────────
_CACHE: dict[tuple[str, str], tuple[bool, int, str]] = {}


def _baixar_imagem_bytes(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


# ── Metodo A: OpenCV (gratuito) ────────────────────────────────────────────────

def _interior_eh_arte(img, x: int, y: int, w_box: int, h_box: int,
                      min_unique_colors: int = 80) -> tuple[bool, int]:
    """
    Verifica se o interior de um retangulo parece arte (vs texto/uniforme).
    Heuristica: conta cores unicas quantizadas. Texto tem poucas (~5-15);
    arte tem muitas (~80-1000).

    Retorna (eh_arte, num_cores_unicas).
    """
    import cv2
    import numpy as np

    # Recortar interior com margem de 10% pra evitar pegar a moldura
    margin_w = int(w_box * 0.10)
    margin_h = int(h_box * 0.10)
    x1 = max(0, x + margin_w)
    y1 = max(0, y + margin_h)
    x2 = min(img.shape[1], x + w_box - margin_w)
    y2 = min(img.shape[0], y + h_box - margin_h)

    if x2 <= x1 or y2 <= y1:
        return (True, 0)  # fail-open se margem zerou

    interior = img[y1:y2, x1:x2]
    if interior.size == 0:
        return (True, 0)

    # Quantizar cores: 32 bins por canal -> 32^3 = 32768 cores possiveis
    quantized = (interior // 8).astype(np.uint8)
    # Empacotar (R, G, B) -> int unico
    flat = quantized.reshape(-1, 3).astype(np.int32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    n_unique = len(np.unique(packed))

    return (n_unique >= min_unique_colors, n_unique)


def tem_quadro_opencv(
    url: str,
    min_area_pct: float = 0.05,
    canny_low: int = 50,
    canny_high: int = 150,
    blur_kernel: int = 5,
    epsilon_factor: float = 0.02,
    min_unique_colors: int = 80,
) -> tuple[bool, int, str]:
    """
    Detecta retangulos significativos via Canny + contornos, e valida se o
    interior parece arte (vs texto/uniforme) usando contagem de cores unicas.

    Retorna (tem_quadro, n_retangulos_aceitos, motivo).

    Parametros tunaveis:
        min_area_pct:      area minima do retangulo como fracao da imagem total
        canny_low/high:    thresholds do Canny
        blur_kernel:       tamanho do GaussianBlur
        epsilon_factor:    tolerancia do approxPolyDP (perspectiva)
        min_unique_colors: minimo de cores unicas dentro do retangulo p/ aceitar
                           (poucas cores = texto/instrucao; muitas = arte)
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        return (True, -1, f"opencv nao instalado: {e}")

    try:
        img_bytes = _baixar_imagem_bytes(url)
    except Exception as e:
        return (True, -1, f"erro download: {e}")

    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return (True, -1, "imagem invalida (decode falhou)")

        h, w = img.shape[:2]
        total_area = h * w
        min_area = int(min_area_pct * total_area)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)
        edges = cv2.Canny(blurred, canny_low, canny_high)

        # Dilatacao leve para conectar bordas quebradas
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        retangulos_geometria = []  # passou na geometria
        retangulos_arte = []       # passou tambem no check de interior
        rejeitados_por_textura = 0
        cores_diagnostico = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon_factor * peri, True)
            if 4 <= len(approx) <= 6 and cv2.isContourConvex(approx):
                x, y, rw, rh = cv2.boundingRect(approx)
                aspect = max(rw, rh) / max(min(rw, rh), 1)
                if aspect <= 4.0:
                    retangulos_geometria.append({
                        "x": x, "y": y, "w": rw, "h": rh,
                        "area_pct": area / total_area,
                        "vertices": len(approx),
                    })
                    eh_arte, n_cores = _interior_eh_arte(
                        img, x, y, rw, rh, min_unique_colors
                    )
                    cores_diagnostico.append(n_cores)
                    if eh_arte:
                        retangulos_arte.append({
                            "area_pct": area / total_area,
                            "n_cores": n_cores,
                        })
                    else:
                        rejeitados_por_textura += 1

        if retangulos_arte:
            maior_area = max(r["area_pct"] for r in retangulos_arte)
            n_cores_max = max(r["n_cores"] for r in retangulos_arte)
            motivo = (
                f"{len(retangulos_arte)} quadros validos "
                f"(maior area={maior_area:.0%}, {n_cores_max} cores unicas)"
            )
            return (True, len(retangulos_arte), motivo)
        elif retangulos_geometria:
            motivo = (
                f"{len(retangulos_geometria)} retangulos detectados mas todos "
                f"com poucas cores no interior (max {max(cores_diagnostico)} cores; "
                f"limite {min_unique_colors}). Provavelmente texto/uniforme."
            )
            return (False, 0, motivo)
        else:
            return (False, 0, f"0 retangulos com area >= {min_area_pct:.0%}")
    except Exception as e:
        return (True, -1, f"erro processamento: {e}")


# ── Metodo B: Gemini 2.5 Flash (pago barato) ──────────────────────────────────

GEMINI_PROMPT = (
    "Analyze this Etsy product image. The seller is selling FRAMED ART PRINTS. "
    "Decide if this image actually shows the framed art product itself "
    "(a printed picture inside a physical frame) as the dominant subject.\n\n"
    "Set has_frame=TRUE only if:\n"
    "  - The image shows a physical framed print as the main subject "
    "(mockup on wall, lifestyle in a room, detail close-up of the printed art).\n"
    "  - Multiple frames count too (kits/sets).\n\n"
    "Set has_frame=FALSE if:\n"
    "  - The image is a TEXT CARD or INFO CARD (e.g. a beige/cream/white card with "
    "written text describing the parable, the bible verse, the seller's story, "
    "shipping policies, instructions). Even if it has a decorative border, "
    "if the primary content is WRITTEN TEXT, set FALSE.\n"
    "  - The image is a video poster/thumbnail (with play button, no frame visible).\n"
    "  - The image shows only the artwork DIGITAL FILE without a physical frame "
    "(unless it's clearly a mockup of the product).\n"
    "  - The image is size/measurement diagrams, packaging photos, "
    "or anything that's not the actual product.\n\n"
    "Also report text_dominant=true if more than ~30% of the image is occupied "
    "by readable written text (sentences/paragraphs, NOT just a small caption "
    "or watermark on a real photo)."
)

GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "has_frame":      {"type": "boolean"},
        "frame_count":    {"type": "integer"},
        "scene_type": {
            "type": "string",
            "enum": ["mockup", "lifestyle", "text_card", "video", "detail",
                    "diagram", "packaging", "other"],
        },
        "text_dominant":  {"type": "boolean"},
    },
    "required": ["has_frame", "frame_count", "scene_type", "text_dominant"],
}


def tem_quadro_gemini(url: str) -> tuple[bool, int, str]:
    """
    Detecta quadro via Gemini 2.5 Flash (mais barato que Pro).
    Requer GEMINI_API_KEY no .env.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return (True, -1, "GEMINI_API_KEY nao configurada (fail-open)")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return (True, -1, "google-genai nao instalado: pip install google-genai")

    try:
        img_bytes = _baixar_imagem_bytes(url)
    except Exception as e:
        return (True, -1, f"erro download: {e}")

    try:
        client = genai.Client(api_key=api_key)

        # Detectar mime type pelo header dos bytes
        mime = "image/jpeg"
        if img_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type=mime),
                GEMINI_PROMPT,
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema":    GEMINI_SCHEMA,
            },
        )

        data = json.loads(response.text)
        has = bool(data.get("has_frame"))
        n = int(data.get("frame_count", 0) or 0)
        scene = data.get("scene_type", "?")
        text_dom = bool(data.get("text_dominant", False))

        # Override: se texto e dominante, rejeitar mesmo se has_frame veio True
        if text_dom:
            has = False

        motivo = f"gemini: scene={scene}, count={n}, text_dom={text_dom}"
        return (has, n, motivo)
    except Exception as e:
        return (True, -1, f"erro gemini: {e}")


# ── Selector ──────────────────────────────────────────────────────────────────

def tem_quadro(url: str, method: str = "opencv", **kwargs) -> tuple[bool, int, str]:
    """
    Selector entre opencv (default, gratuito) e gemini (pago).
    method: 'opencv' | 'gemini'
    Restante dos kwargs vai pro detector escolhido.
    """
    cache_key = (url, method)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if method == "gemini":
        result = tem_quadro_gemini(url)
    else:
        result = tem_quadro_opencv(url, **kwargs)

    _CACHE[cache_key] = result
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL da imagem para testar")
    parser.add_argument("--method", choices=["opencv", "gemini"], default="opencv")
    parser.add_argument("--min-area-pct", type=float, default=0.05)
    parser.add_argument("--canny-low", type=int, default=50)
    parser.add_argument("--canny-high", type=int, default=150)
    args = parser.parse_args()

    inicio = time.time()
    if args.method == "opencv":
        ok, n, motivo = tem_quadro_opencv(
            args.url,
            min_area_pct=args.min_area_pct,
            canny_low=args.canny_low,
            canny_high=args.canny_high,
        )
    else:
        ok, n, motivo = tem_quadro_gemini(args.url)
    elapsed = time.time() - inicio

    print(json.dumps({
        "url":     args.url,
        "method":  args.method,
        "ok":      ok,
        "n":       n,
        "motivo":  motivo,
        "tempo_s": round(elapsed, 2),
    }, indent=2, ensure_ascii=False))
