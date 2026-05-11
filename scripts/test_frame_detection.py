"""
test_frame_detection.py — Test harness para validar detector de quadros.

Roda o detector em uma lista de URLs e imprime resultados lado a lado
(opencv vs gemini, opcionalmente). Util para calibrar antes de integrar
no pipeline.

Uso:
    # Testar uma lista de URLs em arquivo .txt (uma URL por linha)
    python scripts/test_frame_detection.py urls.txt --method opencv
    python scripts/test_frame_detection.py urls.txt --method gemini
    python scripts/test_frame_detection.py urls.txt --method both

    # Ajustar parametros do OpenCV
    python scripts/test_frame_detection.py urls.txt --method opencv --min-area-pct 0.03

    # Usar URLs inline (separadas por espaco)
    python scripts/test_frame_detection.py --urls "https://..." "https://..." --method opencv

Saida: tabela com URL | metodo | TEM_QUADRO | n | motivo | tempo
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from frame_detection import tem_quadro_opencv, tem_quadro_gemini


def carregar_urls(arquivo: str) -> list[str]:
    urls = []
    with open(arquivo, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and (
                linha.startswith("http://") or linha.startswith("https://")
            ):
                urls.append(linha)
    return urls


def imprimir_resultado(url: str, metodo: str, ok: bool, n: int, motivo: str, tempo: float):
    status = "TEM_QUADRO " if ok else "SEM_QUADRO "
    cor_status = "\033[92m" if ok else "\033[91m"
    reset = "\033[0m"
    if not sys.stdout.isatty():  # sem cor em arquivo
        cor_status = reset = ""

    url_curto = url if len(url) <= 70 else url[:67] + "..."
    print(f"  [{metodo:6}] {cor_status}{status}{reset} n={n:2}  {tempo:5.2f}s  {motivo}")
    print(f"           url: {url_curto}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", nargs="?", help="Arquivo .txt com URLs (uma por linha)")
    parser.add_argument("--urls", nargs="*", help="URLs inline (alternativa ao arquivo)")
    parser.add_argument("--method", choices=["opencv", "gemini", "both"], default="opencv")
    parser.add_argument("--min-area-pct", type=float, default=0.05)
    parser.add_argument("--canny-low", type=int, default=50)
    parser.add_argument("--canny-high", type=int, default=150)
    args = parser.parse_args()

    if args.arquivo:
        urls = carregar_urls(args.arquivo)
    elif args.urls:
        urls = args.urls
    else:
        print("Uso: passar arquivo.txt OU --urls <u1> <u2>...", file=sys.stderr)
        sys.exit(1)

    if not urls:
        print("Nenhuma URL valida encontrada.", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Testando {len(urls)} URLs (metodo: {args.method}) ===\n")

    metodos = ["opencv", "gemini"] if args.method == "both" else [args.method]

    contadores = {m: {"tem": 0, "sem": 0, "erro": 0} for m in metodos}

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}]")

        for metodo in metodos:
            inicio = time.time()
            if metodo == "opencv":
                ok, n, motivo = tem_quadro_opencv(
                    url,
                    min_area_pct=args.min_area_pct,
                    canny_low=args.canny_low,
                    canny_high=args.canny_high,
                )
            else:
                ok, n, motivo = tem_quadro_gemini(url)
            elapsed = time.time() - inicio

            imprimir_resultado(url, metodo, ok, n, motivo, elapsed)

            if n == -1:
                contadores[metodo]["erro"] += 1
            elif ok:
                contadores[metodo]["tem"] += 1
            else:
                contadores[metodo]["sem"] += 1

        print()

    print("\n=== Resumo ===")
    for m in metodos:
        c = contadores[m]
        total = sum(c.values())
        print(
            f"  {m:6}: TEM={c['tem']}  SEM={c['sem']}  ERRO={c['erro']}  "
            f"(total={total})"
        )

    print("\n=== Como avaliar ===")
    print("  Marque manualmente cada URL como 'esperado tem quadro' (Y) ou 'esperado sem quadro' (N)")
    print("  Compare com a saida acima:")
    print("    - Falsos positivos (decidiu TEM mas era texto/video) = ruim")
    print("    - Falsos negativos (decidiu SEM mas tinha quadro)    = ruim")
    print("  Se OpenCV tiver >=85% de acerto, manter. Caso contrario, usar gemini.")


if __name__ == "__main__":
    main()
