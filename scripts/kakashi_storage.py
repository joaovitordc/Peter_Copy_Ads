"""
kakashi_storage.py — Banco de artes pro sistema Kakashi (gerador de PDFs).

Cada arte gerada pelo Peter eh persistida aqui pra permitir baixar planilhas
seletivas depois — operador escolhe so as artes que venderam, baixa um XLSX
com so essas linhas, e sobe no Kakashi pra gerar os PDFs.

Espelha o padrao de sku_storage.py:
  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY presentes -> Supabase via PostgREST
  Caso contrario -> arquivo local kakashi_artes.json (dev mode + fallback)

Schema (Supabase, ver scripts/supabase_schema.sql):
  peter_kakashi_artes (
    sku_base           TEXT PK,
    sku_completo       TEXT NOT NULL,
    tipo               TEXT NOT NULL,
    descricao          TEXT NOT NULL,
    imagem_capa        TEXT NOT NULL,
    loja               TEXT,
    categoria          TEXT,
    criado_em          DATE NOT NULL DEFAULT CURRENT_DATE,
    enviado_kakashi_em DATE              -- NULL = pendente
  )

Interface publica:

  salvar_arte(sku_base, info) -> None
      UPSERT idempotente. info: {sku_completo, tipo, descricao, imagem_capa,
      loja, categoria}. criado_em e enviado_kakashi_em sao preservados em
      updates (so atualiza os campos de descricao/imagem/loja/categoria).

  carregar(loja="", q="", status="todos", sort="criado_desc") -> list[dict]
      Lista filtrada. status: 'todos' | 'pendente' | 'enviado'.
      sort: 'criado_desc' (default) | 'criado_asc' | 'sku_asc' | 'sku_desc'.

  marcar_enviado(sku_bases: list[str]) -> int
      UPDATE enviado_kakashi_em = CURRENT_DATE WHERE sku_base IN (...).
      Retorna quantos foram atualizados.

  desmarcar(sku_base) -> bool
      UPDATE enviado_kakashi_em = NULL pra um SKU. Retorna True se mudou.

  liberar(sku_base) -> bool
      DELETE FROM peter_kakashi_artes WHERE sku_base = $1.

  info() -> str
      'supabase' | 'local' — debug do backend ativo.
"""
import os
import json
import sys
from pathlib import Path
from datetime import date
from typing import Optional

import requests


BASE_DIR = Path(__file__).parent.parent
LOCAL_PATH = BASE_DIR / "kakashi_artes.json"
LOCAL_PATH_TMP = Path("/tmp/kakashi_artes.json")

_SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.environ.get("SUPABASE_KEY", "")
)
_SB_TABLE = "peter_kakashi_artes"
_HTTP_TIMEOUT = 15


def _backend() -> str:
    if _SB_URL and _SB_KEY:
        return "supabase"
    return "local"


def info() -> str:
    return _backend()


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


_SELECT_COLS = (
    "sku_base,sku_completo,tipo,descricao,imagem_capa,loja,categoria,"
    "criado_em,enviado_kakashi_em"
)


def _sb_salvar_arte(sku_base: str, info: dict) -> None:
    """UPSERT via PostgREST. Preserva criado_em e enviado_kakashi_em em
    updates (so atualiza os campos editaveis)."""
    if not sku_base:
        return

    # Verifica se ja existe pra decidir entre INSERT e PATCH parcial.
    url_get = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}&select=sku_base&limit=1"
    resp = requests.get(url_get, headers=_sb_headers(), timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    existe = bool(resp.json())

    if existe:
        # UPDATE — so atualiza campos editaveis (preserva criado_em + enviado_kakashi_em)
        body = {
            "sku_completo": info.get("sku_completo", ""),
            "tipo":         info.get("tipo", ""),
            "descricao":    info.get("descricao", ""),
            "imagem_capa":  info.get("imagem_capa", ""),
            "loja":         info.get("loja", ""),
            "categoria":    info.get("categoria", ""),
        }
        url_patch = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
        resp = requests.patch(
            url_patch,
            headers=_sb_headers({"Prefer": "return=minimal"}),
            json=body,
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return

    # INSERT
    row = {
        "sku_base":     sku_base,
        "sku_completo": info.get("sku_completo", ""),
        "tipo":         info.get("tipo", ""),
        "descricao":    info.get("descricao", ""),
        "imagem_capa":  info.get("imagem_capa", ""),
        "loja":         info.get("loja", ""),
        "categoria":    info.get("categoria", ""),
        # criado_em e enviado_kakashi_em usam defaults do banco
    }
    url_post = f"{_SB_URL}/rest/v1/{_SB_TABLE}"
    resp = requests.post(
        url_post,
        headers=_sb_headers({"Prefer": "return=minimal,resolution=ignore-duplicates"}),
        json=[row],
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()


def _sb_carregar() -> list:
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?select={_SELECT_COLS}"
    resp = requests.get(url, headers=_sb_headers(), timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _sb_marcar_enviado(sku_bases: list) -> int:
    if not sku_bases:
        return 0
    # PostgREST `in.(a,b,c)` filter
    lista = ",".join(sku_bases)
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=in.({lista})"
    hoje = date.today().isoformat()
    resp = requests.patch(
        url,
        headers=_sb_headers({"Prefer": "return=representation"}),
        json={"enviado_kakashi_em": hoje},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return len(resp.json())


def _sb_desmarcar(sku_base: str) -> bool:
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
    resp = requests.patch(
        url,
        headers=_sb_headers({"Prefer": "return=representation"}),
        json={"enviado_kakashi_em": None},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


def _sb_liberar(sku_base: str) -> bool:
    url = f"{_SB_URL}/rest/v1/{_SB_TABLE}?sku_base=eq.{sku_base}"
    resp = requests.delete(
        url,
        headers=_sb_headers({"Prefer": "return=representation"}),
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


# ─────────────────────────── Backend Local (arquivo JSON) ────────────────────

def _local_target() -> Path:
    if os.environ.get("VERCEL"):
        LOCAL_PATH_TMP.parent.mkdir(parents=True, exist_ok=True)
        return LOCAL_PATH_TMP
    return LOCAL_PATH


def _local_carregar_raw() -> dict:
    artes = {}
    for path in (LOCAL_PATH, LOCAL_PATH_TMP):
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    artes.update(json.load(f))
            except json.JSONDecodeError:
                pass
    return artes


def _local_persistir(artes: dict) -> None:
    target = _local_target()
    with open(target, "w", encoding="utf-8") as f:
        json.dump(artes, f, indent=2, ensure_ascii=False, sort_keys=True)


def _local_salvar_arte(sku_base: str, info: dict) -> None:
    if not sku_base:
        return
    artes = _local_carregar_raw()
    if sku_base in artes:
        # update parcial: preserva criado_em + enviado_kakashi_em
        artes[sku_base].update({
            "sku_completo": info.get("sku_completo", ""),
            "tipo":         info.get("tipo", ""),
            "descricao":    info.get("descricao", ""),
            "imagem_capa":  info.get("imagem_capa", ""),
            "loja":         info.get("loja", ""),
            "categoria":    info.get("categoria", ""),
        })
    else:
        artes[sku_base] = {
            "sku_base":          sku_base,
            "sku_completo":      info.get("sku_completo", ""),
            "tipo":              info.get("tipo", ""),
            "descricao":         info.get("descricao", ""),
            "imagem_capa":       info.get("imagem_capa", ""),
            "loja":              info.get("loja", ""),
            "categoria":         info.get("categoria", ""),
            "criado_em":         date.today().isoformat(),
            "enviado_kakashi_em": None,
        }
    _local_persistir(artes)


def _local_carregar() -> list:
    artes = _local_carregar_raw()
    # Normaliza pra lista de dicts
    out = []
    for sku_base, info in artes.items():
        # Garante sku_base no dict
        if "sku_base" not in info:
            info["sku_base"] = sku_base
        out.append(info)
    return out


def _local_marcar_enviado(sku_bases: list) -> int:
    if not sku_bases:
        return 0
    artes = _local_carregar_raw()
    hoje = date.today().isoformat()
    n = 0
    for sku_base in sku_bases:
        if sku_base in artes:
            artes[sku_base]["enviado_kakashi_em"] = hoje
            n += 1
    _local_persistir(artes)
    return n


def _local_desmarcar(sku_base: str) -> bool:
    artes = _local_carregar_raw()
    if sku_base not in artes:
        return False
    if artes[sku_base].get("enviado_kakashi_em") is None:
        return False
    artes[sku_base]["enviado_kakashi_em"] = None
    _local_persistir(artes)
    return True


def _local_liberar(sku_base: str) -> bool:
    artes = _local_carregar_raw()
    if sku_base not in artes:
        return False
    del artes[sku_base]
    _local_persistir(artes)
    return True


# ─────────────────────────── API publica ──────────────────────────────────────

def salvar_arte(sku_base: str, info: dict) -> None:
    if _backend() == "supabase":
        try:
            _sb_salvar_arte(sku_base, info)
            return
        except Exception as e:
            print(f"[AVISO][kakashi_storage] Supabase falhou ({e}), caindo pro local", file=sys.stderr)
    _local_salvar_arte(sku_base, info)


def carregar(loja: str = "", q: str = "", status: str = "todos",
             sort: str = "criado_desc") -> list:
    """Lista artes filtradas/ordenadas pra UI.

    Args:
        loja:   filtra por loja exata (PPJ, iPaper, AllQuadros) ou "" pra todas
        q:      busca substring em sku_base ou descricao (case-insensitive)
        status: 'todos' | 'pendente' (enviado_em IS NULL) | 'enviado'
        sort:   'criado_desc' | 'criado_asc' | 'sku_asc' | 'sku_desc'

    Retorna lista de dicts com keys do schema.
    """
    if _backend() == "supabase":
        try:
            artes = _sb_carregar()
        except Exception as e:
            print(f"[AVISO][kakashi_storage] Supabase falhou ({e}), caindo pro local", file=sys.stderr)
            artes = _local_carregar()
    else:
        artes = _local_carregar()

    q_lower = (q or "").strip().lower()
    resultado = []
    for a in artes:
        if loja and a.get("loja") != loja:
            continue
        if status == "pendente" and a.get("enviado_kakashi_em"):
            continue
        if status == "enviado" and not a.get("enviado_kakashi_em"):
            continue
        if q_lower:
            sku = (a.get("sku_base") or "").lower()
            sku_full = (a.get("sku_completo") or "").lower()
            desc = (a.get("descricao") or "").lower()
            if q_lower not in sku and q_lower not in sku_full and q_lower not in desc:
                continue
        resultado.append(a)

    # Ordena
    if sort == "criado_asc":
        resultado.sort(key=lambda r: (r.get("criado_em") or "", (r.get("sku_base") or "").lower()))
    elif sort == "sku_asc":
        resultado.sort(key=lambda r: (r.get("sku_base") or "").lower())
    elif sort == "sku_desc":
        resultado.sort(key=lambda r: (r.get("sku_base") or "").lower(), reverse=True)
    else:  # criado_desc (default)
        resultado.sort(
            key=lambda r: (r.get("criado_em") or "", (r.get("sku_base") or "").lower()),
            reverse=True,
        )
    return resultado


def marcar_enviado(sku_bases: list) -> int:
    if _backend() == "supabase":
        try:
            return _sb_marcar_enviado(sku_bases)
        except Exception as e:
            print(f"[AVISO][kakashi_storage] Supabase falhou ({e}), caindo pro local", file=sys.stderr)
    return _local_marcar_enviado(sku_bases)


def desmarcar(sku_base: str) -> bool:
    if _backend() == "supabase":
        try:
            return _sb_desmarcar(sku_base)
        except Exception as e:
            print(f"[AVISO][kakashi_storage] Supabase falhou ({e}), caindo pro local", file=sys.stderr)
    return _local_desmarcar(sku_base)


def liberar(sku_base: str) -> bool:
    if _backend() == "supabase":
        try:
            return _sb_liberar(sku_base)
        except Exception as e:
            print(f"[AVISO][kakashi_storage] Supabase falhou ({e}), caindo pro local", file=sys.stderr)
    return _local_liberar(sku_base)
