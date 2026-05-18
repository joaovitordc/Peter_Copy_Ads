"""
sku_storage.py — Abstracao do banco de SKUs em uso.

Decide o backend baseado em env vars (auto-detect):

  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY presentes
      -> Supabase (PostgREST direto via `requests`)
  Caso contrario
      -> Arquivo local skus_em_uso.json (dev local + fallback de emergencia)

Schema (Supabase, ver scripts/supabase_schema.sql):
  peter_skus_em_uso (
    sku_base          TEXT PK,
    lojas_cadastradas TEXT[] NOT NULL DEFAULT '{}',
    tipo              TEXT NOT NULL,
    display           TEXT,
    criado_em         DATE NOT NULL DEFAULT CURRENT_DATE
  )

Interface publica:

  carregar() -> dict
      {sku_base: {"lojas": ["PPJ","iPaper"], "loja": "PPJ" (compat: 1a da lista),
                  "tipo": "Q1", "display": "...", "criado_em": "2026-05-18"}}

  adicionar(sku_base, info)
      Idempotente: se SKU ja existe no banco, faz MERGE da loja no array
      (sem duplicar). Se nao existe, INSERT. Atalho preferido pra writes
      granulares no fluxo de cadastro de produto.
      info: {"loja": "AllQuadros", "tipo": "Q1", "display": "..." [, "criado_em"]}

  liberar_loja(sku_base, loja) -> bool
      Remove a loja do array `lojas_cadastradas`. Se o array ficar vazio,
      deleta a linha (libera o nome pra reuso). Retorna True se algo mudou.

  liberar(sku_base) -> bool
      Remove a linha INTEIRA (libera independente de quantas lojas tinha).
      Uso administrativo — operador "esquece" esse SKU completamente.

  salvar(skus: dict) -> None  [retrocompat]
      Aceita formato classico {sku: {loja, tipo, display, ...}} e chama
      adicionar() por SKU. Nao apaga linhas que sumiram do dict.

  info() -> str
      Pra debug — retorna qual backend ta ativo ('local' ou 'supabase').
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
    or os.environ.get("SUPABASE_KEY", "")
)
_SB_TABLE = "peter_skus_em_uso"
_HTTP_TIMEOUT = 15


def _backend() -> str:
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


def _sb_row_to_info(r: dict) -> dict:
    """Normaliza linha do PostgREST pro formato interno do Peter."""
    lojas = r.get("lojas_cadastradas") or []
    return {
        "lojas":     lojas,
        "loja":      lojas[0] if lojas else "",  # retrocompat (callers antigos)
        "tipo":      r.get("tipo", ""),
        "display":   r.get("display", ""),
        "criado_em": r.get("criado_em", ""),
    }


def _sb_carregar() -> dict:
    url = (
        f"{_SB_URL}/rest/v1/{_SB_TABLE}"
        f"?select=sku_base,lojas_cadastradas,tipo,display,criado_em"
    )
    resp = requests.get(url, headers=_sb_headers(), timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return {r["sku_base"]: _sb_row_to_info(r) for r in resp.json()}


def _sb_get_one(sku_base: str) -> Optional[dict]:
    """Retorna linha bruta do Supabase ou None."""
    url = (
        f"{_SB_URL}/rest/v1/{_SB_TABLE}"
        f"?sku_base=eq.{sku_base}"
        f"&select=sku_base,lojas_cadastradas,tipo,display,criado_em"
        f"&limit=1"
    )
    resp = requests.get(url, headers=_sb_headers(), timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def _sb_adicionar(sku_base: str, info: dict) -> None:
    """SELECT + INSERT ou PATCH (merge da loja no array sem duplicar)."""
    if not sku_base:
        return
    loja_nova = info.get("loja", "")

    existente = _sb_get_one(sku_base)
    if existente is not None:
        # SKU ja existe — MERGE da loja no array (se ainda nao esta la)
        lojas_atuais = existente.get("lojas_cadastradas") or []
        if loja_nova and loja_nova not in lojas_atuais:
            novas = lojas_atuais + [loja_nova]
            url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
            resp = requests.patch(
                url,
                headers=_sb_headers({"Prefer": "return=minimal"}),
                json={"lojas_cadastradas": novas},
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
        # Se loja ja estava no array, no-op (idempotente)
        return

    # SKU novo — INSERT
    row = {
        "sku_base":          sku_base,
        "lojas_cadastradas": [loja_nova] if loja_nova else [],
        "tipo":              info.get("tipo", ""),
        "display":           info.get("display", ""),
        "criado_em":         info.get("criado_em", date.today().isoformat()),
    }
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}"
    resp = requests.post(
        url,
        headers=_sb_headers({"Prefer": "return=minimal,resolution=ignore-duplicates"}),
        json=[row],
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


def _sb_liberar_loja(sku_base: str, loja: str) -> bool:
    """Remove 1 loja do array. Se array vazio depois, deleta a linha."""
    if not sku_base or not loja:
        return False
    existente = _sb_get_one(sku_base)
    if existente is None:
        return False
    lojas = existente.get("lojas_cadastradas") or []
    if loja not in lojas:
        return False
    novas = [l for l in lojas if l != loja]
    if not novas:
        # Ultima loja — deleta linha inteira
        return _sb_liberar(sku_base)
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
    resp = requests.patch(
        url,
        headers=_sb_headers({"Prefer": "return=minimal"}),
        json={"lojas_cadastradas": novas},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return True


def _sb_liberar(sku_base: str) -> bool:
    """DELETE FROM peter_skus_em_uso WHERE sku_base = $1."""
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


def _sb_salvar(skus: dict) -> None:
    """Retrocompat — chama adicionar() pra cada SKU (faz merge inteligente)."""
    for sku_base, info in skus.items():
        try:
            _sb_adicionar(sku_base, info)
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase adicionar({sku_base}) falhou: {e}", file=sys.stderr)


# ─────────────────────────── Backend Local (arquivo JSON) ────────────────────

def _local_carregar() -> dict:
    """Mergeia arquivo do deploy com /tmp. Formato normalizado pra
    {lojas, loja, tipo, display, criado_em}. JSON antigo (chave 'loja' string)
    e migrado pra 'lojas' (lista de 1 elemento)."""
    skus_raw: dict = {}
    if LOCAL_PATH.exists():
        try:
            with open(LOCAL_PATH, encoding="utf-8") as f:
                skus_raw.update(json.load(f))
        except json.JSONDecodeError:
            pass
    if str(LOCAL_PATH_TMP) != str(LOCAL_PATH) and LOCAL_PATH_TMP.exists():
        try:
            with open(LOCAL_PATH_TMP, encoding="utf-8") as f:
                skus_raw.update(json.load(f))
        except json.JSONDecodeError:
            pass
    # Normalizar: garantir que cada entry tem 'lojas' (lista) e 'loja' (str)
    skus: dict = {}
    for sku, info in skus_raw.items():
        lojas = info.get("lojas") or ([info["loja"]] if info.get("loja") else [])
        skus[sku] = {
            "lojas":     lojas,
            "loja":      lojas[0] if lojas else "",
            "tipo":      info.get("tipo", ""),
            "display":   info.get("display", ""),
            "criado_em": info.get("criado_em", ""),
        }
    return skus


def _local_target() -> Path:
    if os.environ.get("VERCEL"):
        LOCAL_PATH_TMP.parent.mkdir(parents=True, exist_ok=True)
        return LOCAL_PATH_TMP
    return LOCAL_PATH


def _local_persistir(skus: dict) -> None:
    """Grava o dict no arquivo target. Formato gravado: lista 'lojas' (nao
    'loja' string) pra alinhar com o schema novo."""
    target = _local_target()
    serializado = {
        sku: {
            "lojas":     info.get("lojas") or ([info["loja"]] if info.get("loja") else []),
            "tipo":      info.get("tipo", ""),
            "display":   info.get("display", ""),
            "criado_em": info.get("criado_em", ""),
        }
        for sku, info in skus.items()
    }
    with open(target, "w", encoding="utf-8") as f:
        json.dump(serializado, f, indent=2, ensure_ascii=False, sort_keys=True)


def _local_adicionar(sku_base: str, info: dict) -> None:
    if not sku_base:
        return
    skus = _local_carregar()
    loja_nova = info.get("loja", "")
    if sku_base in skus:
        lojas_atuais = skus[sku_base].get("lojas") or []
        if loja_nova and loja_nova not in lojas_atuais:
            skus[sku_base]["lojas"] = lojas_atuais + [loja_nova]
            _local_persistir(skus)
        return
    skus[sku_base] = {
        "lojas":     [loja_nova] if loja_nova else [],
        "tipo":      info.get("tipo", ""),
        "display":   info.get("display", ""),
        "criado_em": info.get("criado_em", date.today().isoformat()),
    }
    _local_persistir(skus)


def _local_liberar_loja(sku_base: str, loja: str) -> bool:
    if not sku_base or not loja:
        return False
    skus = _local_carregar()
    if sku_base not in skus:
        return False
    lojas = skus[sku_base].get("lojas") or []
    if loja not in lojas:
        return False
    novas = [l for l in lojas if l != loja]
    if not novas:
        skus.pop(sku_base)
    else:
        skus[sku_base]["lojas"] = novas
    _local_persistir(skus)
    return True


def _local_liberar(sku_base: str) -> bool:
    skus = _local_carregar()
    if sku_base in skus:
        skus.pop(sku_base)
        _local_persistir(skus)
        return True
    return False


def _local_salvar(skus: dict) -> None:
    """Retrocompat: chama adicionar() pra cada SKU (merge friendly)."""
    for sku_base, info in skus.items():
        _local_adicionar(sku_base, info)


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


def adicionar(sku_base: str, info: dict) -> None:
    if _backend() == "supabase":
        try:
            _sb_adicionar(sku_base, info)
            return
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase adicionar falhou: {e}. Fallback local.", file=sys.stderr)
    _local_adicionar(sku_base, info)


def liberar_loja(sku_base: str, loja: str) -> bool:
    if _backend() == "supabase":
        try:
            return _sb_liberar_loja(sku_base, loja)
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase liberar_loja falhou: {e}. Fallback local.", file=sys.stderr)
    return _local_liberar_loja(sku_base, loja)


def liberar(sku_base: str) -> bool:
    if _backend() == "supabase":
        try:
            return _sb_liberar(sku_base)
        except Exception as e:
            print(f"[AVISO][sku_storage] Supabase liberar falhou: {e}. Fallback local.", file=sys.stderr)
    return _local_liberar(sku_base)


def info() -> str:
    return _backend()
