"""
migrate_to_supabase.py — Migra skus_em_uso.json (arquivo local) pra tabela
Supabase. Rodar UMA vez apos o operador criar a tabela via supabase_schema.sql.

Uso:
    # 1. Garante env vars SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env
    # 2. Roda:
    python scripts/migrate_to_supabase.py
    #    --dry-run pra simular sem escrever
"""
import os
import sys
import json
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import sku_storage

JSON_PATH = BASE / "skus_em_uso.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="So simula, nao escreve")
    args = parser.parse_args()

    if sku_storage.info() != "supabase":
        print("[ERRO] Backend ativo: " + sku_storage.info() +
              ". Esperado 'supabase'.\n"
              "Confira SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.")
        sys.exit(1)

    if not JSON_PATH.exists():
        print("[ERRO] " + str(JSON_PATH) + " nao encontrado.")
        sys.exit(1)

    with open(JSON_PATH, encoding="utf-8") as f:
        skus_json = json.load(f)

    print("Backend ativo:    " + sku_storage.info())
    print("Source JSON:      " + str(JSON_PATH) + " (" + str(len(skus_json)) + " entradas)")
    from collections import Counter
    por_loja = Counter(v.get("loja", "?") for v in skus_json.values())
    print("Distribuicao por loja:")
    for loja, n in sorted(por_loja.items()):
        print("  " + str(loja) + ": " + str(n))

    # Verifica se ja tem dados no Supabase
    print()
    print("Verificando estado atual do Supabase...")
    skus_remoto = sku_storage._sb_carregar()
    print("Supabase atual:   " + str(len(skus_remoto)) + " entradas")

    novos = set(skus_json.keys()) - set(skus_remoto.keys())
    ja_existem = set(skus_json.keys()) & set(skus_remoto.keys())
    so_no_remoto = set(skus_remoto.keys()) - set(skus_json.keys())

    print("Diff:")
    print("  Novos (vai inserir):           " + str(len(novos)))
    print("  Ja existem (upsert no-op):     " + str(len(ja_existem)))
    print("  So no Supabase (preservados):  " + str(len(so_no_remoto)))

    if args.dry_run:
        print()
        print("DRY RUN: nada foi escrito.")
        return

    if not novos:
        print()
        print("Nada novo pra migrar. Saindo.")
        return

    print()
    print("Inserindo " + str(len(novos)) + " novos no Supabase...")
    # Insert em batch — supabase REST aceita ate ~1000 linhas por request
    BATCH = 500
    novos_dict = {k: skus_json[k] for k in novos}
    items = list(novos_dict.items())
    for i in range(0, len(items), BATCH):
        chunk = dict(items[i:i+BATCH])
        sku_storage._sb_salvar(chunk)
        print("  Batch " + str(i // BATCH + 1) + ": " + str(len(chunk)) + " inseridos")

    # Confirma
    print()
    print("Confirmando estado final...")
    final = sku_storage._sb_carregar()
    print("Supabase final:   " + str(len(final)) + " entradas")
    por_loja_final = Counter(v.get("loja", "?") for v in final.values())
    print("Distribuicao por loja:")
    for loja, n in sorted(por_loja_final.items()):
        print("  " + str(loja) + ": " + str(n))


if __name__ == "__main__":
    main()
