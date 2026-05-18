"""
migrate_to_supabase.py — Migra SKUs de 1+ planilhas Shopee (mass_update_sales_info)
pra tabela peter_skus_em_uso no Supabase. Cada SKU vira 1 linha; mesmo SKU em
multiplas planilhas faz MERGE no array `lojas_cadastradas`.

Uso:
    # 1. Garante env vars SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env
    # 2. Roda passando 1 ou mais planilhas com a flag --xlsx loja=path
    python scripts/migrate_to_supabase.py \\
        --xlsx AllQuadros=C:/Users/.../mass_update_sales_info_allquadros.xlsx \\
        --xlsx PPJ=C:/Users/.../mass_update_sales_info_ppj.xlsx \\
        --xlsx iPaper=C:/Users/.../mass_update_sales_info_ipaper.xlsx
    #
    # --dry-run pra simular sem escrever
    # --from-json pra usar skus_em_uso.json como input (sem XLSX)
"""
import os
import sys
import json
import argparse
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import sku_storage

JSON_PATH = BASE / "skus_em_uso.json"

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def ler_skus_xlsx(path: str) -> dict[str, dict]:
    """Le mass_update_sales_info.xlsx (formato Shopee) e extrai
    {sku_base: {tipo, display}} a partir da coluna F (Nº de Ref. SKU).

    SKU formato: {TIPO}_{TAMMOL}_{NOME} -> radical (TIPO, NOME).
    Usa XML direto pois openpyxl quebra no XLSX da Shopee (activePane invalido).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    shared_strings: list[str] = []
    with zipfile.ZipFile(path) as z:
        try:
            with z.open("xl/sharedStrings.xml") as f:
                tree = ET.parse(f)
                for si in tree.getroot().findall("main:si", NS):
                    t = si.find("main:t", NS)
                    if t is not None and t.text:
                        shared_strings.append(t.text)
                    else:
                        parts = [
                            r.find("main:t", NS).text or ""
                            for r in si.findall("main:r", NS)
                            if r.find("main:t", NS) is not None
                        ]
                        shared_strings.append("".join(parts))
        except KeyError:
            pass

        with z.open("xl/worksheets/sheet1.xml") as f:
            tree = ET.parse(f)
            rows = tree.getroot().find("main:sheetData", NS).findall("main:row", NS)

    def cell_value(c):
        t = c.get("t")
        v = c.find("main:v", NS)
        if v is None:
            is_ = c.find("main:is", NS)
            if is_ is not None:
                tnode = is_.find("main:t", NS)
                return tnode.text if tnode is not None else None
            return None
        if t == "s":
            idx = int(v.text)
            return shared_strings[idx] if 0 <= idx < len(shared_strings) else None
        return v.text

    # 1a varredura: header
    header_row = rows[0] if rows else None
    if header_row is None:
        return {}
    header = [cell_value(c) for c in header_row.findall("main:c", NS)]

    # Detectar indice da coluna do SKU (F = "et_title_variation_sku" no formato
    # Shopee). Tolerante a mudancas de ordem.
    def _find_col(predicate):
        for i, h in enumerate(header):
            if h and predicate(str(h).lower()):
                return i
        return None

    idx_sku = _find_col(lambda h: "sku" in h and "variation" in h)
    if idx_sku is None:
        idx_sku = _find_col(lambda h: "variation_sku" in h or "ref. sku" in h or "ref sku" in h)
    if idx_sku is None:
        # Fallback: coluna F (index 5)
        idx_sku = 5

    skus: dict[str, dict] = {}
    for row in rows[1:]:
        cells = {c.get("r", ""): c for c in row.findall("main:c", NS)}
        row_idx = row.get("r", "")
        # Pegar celula pela coluna detectada (letra correspondente)
        letra = chr(ord("A") + idx_sku)
        c = cells.get(letra + row_idx)
        if c is None:
            continue
        sku_var = cell_value(c)
        if not sku_var:
            continue
        partes = str(sku_var).split("_")
        if len(partes) < 3:
            continue
        tipo = partes[0]
        sku_base = "_".join(partes[2:])
        if sku_base not in skus:
            skus[sku_base] = {"tipo": tipo, "display": sku_base}  # display = sku_base como fallback
    return skus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xlsx", action="append", default=[],
        help="loja=path/para/arquivo.xlsx (repetir pra cada loja)",
    )
    parser.add_argument(
        "--from-json", action="store_true",
        help="Migra a partir de skus_em_uso.json em vez de XLSXs",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if sku_storage.info() != "supabase":
        print("[ERRO] Backend ativo: " + sku_storage.info() +
              ". Esperado 'supabase'.\n"
              "Confira SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.")
        sys.exit(1)

    # Acumula: {sku_base: {"lojas": set, "tipo": str, "display": str}}
    agregado: dict[str, dict] = {}

    if args.from_json:
        if not JSON_PATH.exists():
            print("[ERRO] " + str(JSON_PATH) + " nao encontrado.")
            sys.exit(1)
        with open(JSON_PATH, encoding="utf-8") as f:
            skus_json = json.load(f)
        print(f"Source JSON: {JSON_PATH} ({len(skus_json)} entradas)")
        for sku_base, info in skus_json.items():
            lojas = info.get("lojas") or ([info["loja"]] if info.get("loja") else [])
            agregado[sku_base] = {
                "lojas": set(lojas),
                "tipo": info.get("tipo", "Q1"),
                "display": info.get("display", sku_base),
            }

    if args.xlsx:
        for spec in args.xlsx:
            if "=" not in spec:
                print(f"[ERRO] Formato esperado: --xlsx loja=path. Recebido: {spec}")
                sys.exit(1)
            loja, path = spec.split("=", 1)
            loja = loja.strip()
            path = path.strip().strip('"').strip("'")
            print(f"\nLendo XLSX [{loja}]: {path}")
            skus_loja = ler_skus_xlsx(path)
            print(f"  {len(skus_loja)} SKUs extraidos")
            for sku_base, info in skus_loja.items():
                if sku_base in agregado:
                    agregado[sku_base]["lojas"].add(loja)
                    # Tipo nao deveria conflitar (mesmo SKU = mesmo produto base)
                    # Se conflitar, mantem o primeiro encontrado
                else:
                    agregado[sku_base] = {
                        "lojas": {loja},
                        "tipo": info["tipo"],
                        "display": info["display"],
                    }

    if not agregado:
        print("[ERRO] Nada a migrar. Use --xlsx ou --from-json.")
        sys.exit(1)

    # Sumario
    print()
    print(f"Total SKUs agregados: {len(agregado)}")
    distribuicao_n_lojas = Counter(len(v["lojas"]) for v in agregado.values())
    print("Distribuicao por # de lojas:")
    for n, qtd in sorted(distribuicao_n_lojas.items()):
        print(f"  {n} loja(s): {qtd} SKUs")
    distribuicao_tipos = Counter(v["tipo"] for v in agregado.values())
    print("Distribuicao por tipo:")
    for t, qtd in sorted(distribuicao_tipos.items()):
        print(f"  {t}: {qtd}")
    # Cross-loja
    cross = {sku: v["lojas"] for sku, v in agregado.items() if len(v["lojas"]) >= 2}
    if cross:
        print(f"\n{len(cross)} SKUs cross-loja (presentes em >=2 lojas):")
        for sku in sorted(cross)[:10]:
            print(f"  {sku} -> {sorted(cross[sku])}")
        if len(cross) > 10:
            print(f"  ... e mais {len(cross) - 10}")

    if args.dry_run:
        print("\nDRY RUN: nada foi escrito no Supabase.")
        return

    # Verifica estado atual do Supabase
    print("\nVerificando estado atual do Supabase...")
    skus_remoto = sku_storage._sb_carregar()
    print(f"Supabase atual: {len(skus_remoto)} entradas")

    # Insere (adicionar() faz merge inteligente — idempotente)
    print(f"\nMigrando {len(agregado)} SKUs (adicionar = INSERT ou MERGE de lojas)...")
    hoje = date.today().isoformat()
    erros = []
    for i, (sku_base, info) in enumerate(agregado.items(), 1):
        # Pra cada loja do SKU, chamar adicionar() — merge cuida do array
        for loja in sorted(info["lojas"]):
            try:
                sku_storage.adicionar(sku_base, {
                    "loja": loja,
                    "tipo": info["tipo"],
                    "display": info["display"],
                    "criado_em": hoje,
                })
            except Exception as e:
                erros.append((sku_base, loja, str(e)))
        if i % 50 == 0:
            print(f"  {i}/{len(agregado)} processados")
    print(f"  {len(agregado)}/{len(agregado)} processados")
    if erros:
        print(f"\n[AVISO] {len(erros)} erros (primeiros 5):")
        for sku, loja, msg in erros[:5]:
            print(f"  {sku} [{loja}]: {msg}")

    # Confirma
    print("\nConfirmando estado final...")
    final = sku_storage._sb_carregar()
    print(f"Supabase final: {len(final)} entradas")
    distribuicao_n_lojas_final = Counter(len(v.get("lojas") or []) for v in final.values())
    print("Distribuicao por # de lojas no Supabase:")
    for n, qtd in sorted(distribuicao_n_lojas_final.items()):
        print(f"  {n} loja(s): {qtd} SKUs")


if __name__ == "__main__":
    main()
