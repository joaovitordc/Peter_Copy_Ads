"""
sku_storage.py — Abstracao do banco de SKUs em uso.

Decide o backend baseado em env vars (auto-detect):

  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY presentes
      -> Supabase (PostgREST direto via `requests`)
  Caso contrario
      -> Arquivo local skus_em_uso.json (dev local + fallback de emergencia)

Interface publica:

  carregar() -> dict              # {sku_base: {loja, tipo, display, criado_em}}
  salvar(skus: dict) -> None      # upsert do dict inteiro (sem deletar linhas que sumiram)
  liberar(sku_base) -> bool       # remove 1 SKU (libera pra reuso). Retorna True se removeu.
  adicionar(sku_base, info)       # insere (no-op se ja existe). Atalho pra writes
                                  # granulares evitar carregar+salvar tudo.

Caminho futuro (ERP): adicionar mais tabelas no mesmo banco Supabase
(produtos, vendas, estoque...) sem refator desse modulo. Continuamos
gerenciando `skus_em_uso` como "nomes reservados" complementando o ERP.
"""
import os
import json
import sys
from pathlib import Path
from datetime import date
from typing import Optional

import requests


BASE_DIR = Path(__file__).parent.parent
LOCAL_PATH = BASE_DIR / "skus_em_uso.json"
LOCAL_PATH_TMP = Path("/tmp/skus_em_uso.json")

_SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.environ.get("SUPABASE_KEY", "")  # fallback caso a env var venha com nome diferente
)
_SB_TABLE = "peter_skus_em_uso"  # prefixado pra coexistir com tabelas do EllO ERP no mesmo banco
_HTTP_TIMEOUT = 15


def _backend() -> str:
    """Retorna 'supabase' se configurado, 'local' caso contrario."""
    if _SB_URL and _SB_KEY:
        return "supabase"
    return "local"


# ─────────────────────────── Backend Supabase (PostgREST) ────────────────────

def _sb_headers(extra: Optional[dict] = None) -> dict:
    h = {
        "apikey": _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _sb_carregar() -> dict:
    """SELECT * FROM skus_em_uso. Retorna dict no formato classico."""
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?select=sku_base,loja,tipo,display,criado_em"
    resp = requests.get(url, headers=_sb_headers(), timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    rows = resp.json()
    return {
        r["sku_base"]: {
            "loja": r.get("loja", ""),
            "tipo": r.get("tipo", ""),
            "display": r.get("display", ""),
            "criado_em": r.get("criado_em", ""),
        }
        for r in rows
    }


def _sb_salvar(skus: dict) -> None:
    """Upsert do dict inteiro (resolution=merge-duplicates). Nao apaga linhas
    que sumiram do dict — pra apagar use liberar() explicitamente."""
    if not skus:
        return
    rows = [
        {
            "sku_base": sku_base,
            "loja": info.get("loja", ""),
            "tipo": info.get("tipo", ""),
            "display": info.get("display", ""),
            "criado_em": info.get("criado_em", date.today().isoformat()),
        }
        for sku_base, info in skus.items()
    ]
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}"
    resp = requests.post(
        url,
        headers=_sb_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        json=rows,
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


def _sb_liberar(sku_base: str) -> bool:
    """DELETE FROM skus_em_uso WHERE sku_base = $1. Retorna True se removeu."""
    if not sku_base:
        return False
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
    resp = requests.delete(
        url,
        headers=_sb_headers({"Prefer": "return=representation"}),
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


def _sb_adicionar(sku_base: str, info: dict) -> None:
    """INSERT com ON CONFLICT DO NOTHING. Atalho pra granular writes."""
    if not sku_base:
        return
    row = {
        "sku_base": sku_base,
        "loja": info.get("loja", ""),
        "tipo": info.get("tipo", ""),
        "display": info.get("display", ""),
        "criado_em": info.get("criado_em", date.today().isoformat()),
    }
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}"
    resp = requests.post(
        url,
        headers=_sb_headers({"Prefer": "resolution=ignore-duplicates,return=minimal"}),
        json=[row],
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


# ─────────────────────────── Backend Local (arquivo JSON) ────────────────────

def _local_carregar() -> dict:
    """Mergeia arquivo do deploy (read-only /var/task em Vercel) com /tmp
    (escritas da lambda atual). Cobre transicao caso Supabase fique offline."""
    skus: dict = {}
    if LOCAL_PATH.exists():
        try:
            with open(LOCAL_PATH, encoding="utf-8") as f:
                skus.update(json.load(f))
        except json.JSONDecodeError:
            pass
    if str(LOCAL_PATH_TMP) != str(LOCAL_PATH) and LOCAL_PATH_TMP.exists():
        try:
            with open(LOCAL_PATH_TMP, encoding="utf-8") as f:
                skus.update(json.load(f))
        except json.JSONDecodeError:
            pass
    return skus


def _local_target() -> Path:
    """Em Vercel escreve em /tmp (read-only fora dele); local escreve no repo."""
    if os.environ.get("VERCEL"):
        LOCAL_PATH_TMP.parent.mkdir(parents=True, exist_ok=True)
        return LOCAL_PATH_TMP
    return LOCAL_PATH


def _local_salvar(skus: dict) -> None:
    target = _local_target()
    with open(target, "w", encoding="utf-8") as f:
        json.dump(skus, f, indent=2, ensure_ascii=False, sort_keys=True)


def _local_liberar(sku_base: str) -> bool:
    skus = _local_carregar()
    if sku_base in skus:
        skus.pop(sku_base)
        _local_salvar(skus)
        return True
    return False


def _local_adicionar(sku_base: str, info: dict) -> None:
    skus = _local_carregar()
    if sku_base not in skus:
        skus[sku_base] = {
            "loja": info.get("loja", ""),
            "tipo": info.get("tipo", ""),
            "display": info.get("display", ""),
            "criado_em": info.get("criado_em", date.today().isoformat()),
        }
        _local_salvar(skus)


# ─────────────────────────── API publica (dispatcher) ────────────────────────

def carregar() -> dict:
    if _backend() == "supabase":
        try:
            return _sb_carregar()
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase carregar falhou: {e}. Fallback local.", file=sys.stderr)
            return _local_carregar()
    return _local_carregar()


def salvar(skus: dict) -> None:
    if _backend() == "supabase":
        try:
            _sb_salvar(skus)
            return
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase salvar falhou: {e}. Fallback local.", file=sys.stderr)
    _local_salvar(skus)


def liberar(sku_base: str) -> bool:
    if _backend() == "supabase":
        try:
            return _sb_liberar(sku_base)
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase liberar falhou: {e}. Fallback local.", file=sys.stderr)
    return _local_liberar(sku_base)


def adicionar(sku_base: str, info: dict) -> None:
    if _backend() == "supabase":
        try:
            _sb_adicionar(sku_base, info)
            return
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase adicionar falhou: {e}. Fallback local.", file=sys.stderr)
    _local_adicionar(sku_base, info)


def info() -> str:
    """Pra debug — retorna qual backend ta ativo."""
    return _backend()
