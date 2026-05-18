"""
app.py — Servidor FastAPI para o frontend Etsy → Shopee.

Rotas:
  GET  /                               — Serve index.html
  GET  /api/lojas                      — Lista lojas disponíveis
  POST /api/processar                  — Inicia job (campo: arquivo, loja, modo)
  GET  /api/status/{job_id}            — Consulta status do job
  GET  /api/download/{job_id}/{tipo}   — Download do arquivo gerado (shopee|erp|kakashi)
  GET  /api/modelo/{tipo}              — Download do modelo de planilha de entrada

Executar:
  python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
"""
import io
import os
import sys
import json
import uuid
import asyncio
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Carregar .env
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts"))  # pra importar build_discount_template etc direto

CONFIG_PATH = BASE_DIR / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"

IS_VERCEL = bool(os.environ.get("VERCEL"))
JOBS_DIR = Path("/tmp/jobs") if IS_VERCEL else WEB_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Etsy → Shopee")


# ── Gerenciamento de jobs ──────────────────────────────────────────────────

@dataclass
class JobState:
    job_id: str
    status: str = "aguardando"
    mensagem: str = "Aguardando início..."
    percent: int = 0
    shopee_path: Optional[str] = None
    erp_path: Optional[str] = None
    kakashi_path: Optional[str] = None
    rejeitados_path: Optional[str] = None
    produtos: int = 0
    rejeitados: int = 0
    avisos: list = field(default_factory=list)
    erro: Optional[str] = None
    criado_em: datetime = field(default_factory=datetime.now)
    # Pra suportar /api/descartar — operador revisa thumbnails e exclui produtos
    # com capa cortada antes de cadastrar na Shopee. Precisa do input_json
    # original (lista de produtos OK + loja) pra poder regenerar planilhas.
    loja: Optional[str] = None
    input_json: Optional[dict] = None
    output_dir: Optional[str] = None
    descartados: list = field(default_factory=list)  # SKUs descartados


jobs: dict[str, JobState] = {}


def _state_path(job_id: str) -> Path:
    """Caminho do arquivo de estado persistido pra recuperar entre warm starts
    do mesmo container Lambda. NAO resolve multi-container — pra isso seria
    necessario Vercel Blob/KV (follow-up)."""
    return JOBS_DIR / job_id / "_state.json"


def _salvar_estado(job: JobState) -> None:
    """Persiste JobState como JSON. Idempotente, chamado a cada atualizacao.

    Em Vercel: /tmp/jobs/<id>/_state.json (sobrevive warm starts no mesmo container).
    Em local: web/jobs/<id>/_state.json.
    """
    try:
        path = _state_path(job.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "job_id":          job.job_id,
                "status":          job.status,
                "mensagem":        job.mensagem,
                "percent":         job.percent,
                "shopee_path":     job.shopee_path,
                "erp_path":        job.erp_path,
                "kakashi_path":    job.kakashi_path,
                "rejeitados_path": job.rejeitados_path,
                "produtos":        job.produtos,
                "rejeitados":      job.rejeitados,
                "avisos":          job.avisos,
                "erro":            job.erro,
                "criado_em":       job.criado_em.isoformat(),
                "loja":            job.loja,
                "input_json":      job.input_json,
                "output_dir":      job.output_dir,
                "descartados":     job.descartados,
            }, f, ensure_ascii=False)
    except Exception as e:
        # Persistencia e best-effort — falha aqui nao pode quebrar o pipeline
        print(f"[AVISO] Falha ao persistir JobState {job.job_id}: {e}", file=sys.stderr)


def _carregar_estado(job_id: str) -> Optional[JobState]:
    """Recupera JobState do disco quando nao esta em memoria (cold start no
    mesmo container, ou simplesmente outra requisicao). Retorna None se nao
    existir ou estiver corrompido."""
    try:
        path = _state_path(job_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return JobState(
            job_id=d["job_id"],
            status=d.get("status", "aguardando"),
            mensagem=d.get("mensagem", ""),
            percent=d.get("percent", 0),
            shopee_path=d.get("shopee_path"),
            erp_path=d.get("erp_path"),
            kakashi_path=d.get("kakashi_path"),
            rejeitados_path=d.get("rejeitados_path"),
            produtos=d.get("produtos", 0),
            rejeitados=d.get("rejeitados", 0),
            avisos=d.get("avisos", []),
            erro=d.get("erro"),
            criado_em=datetime.fromisoformat(d["criado_em"]) if d.get("criado_em") else datetime.now(),
            loja=d.get("loja"),
            input_json=d.get("input_json"),
            output_dir=d.get("output_dir"),
            descartados=d.get("descartados", []),
        )
    except Exception as e:
        print(f"[AVISO] Falha ao carregar JobState {job_id}: {e}", file=sys.stderr)
        return None


def _limpar_jobs_antigos():
    limite = datetime.now() - timedelta(hours=2)
    para_remover = [jid for jid, j in jobs.items() if j.criado_em < limite]
    for jid in para_remover:
        job_dir = JOBS_DIR / jid
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        del jobs[jid]


# ── Rotas ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/lojas")
async def get_lojas():
    descricoes = {
        "PPJ":        "Quadros religiosos e minimalistas",
        "iPaper":     "Arte, Bauhaus e design moderno",
        "AllQuadros": "Moderno, minimalista, boho",
        "DecorKids":  "Quadros para decoração infantil",
    }
    lojas = [
        {"id": nome, "nome": nome, "descricao": descricoes.get(nome, "")}
        for nome in CONFIG["lojas"]
    ]
    return {"lojas": lojas}


@app.post("/api/processar")
async def processar(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(...),
    loja: str = Form(...),
    modo: str = Form("links_com_imagens"),
):
    """Inicia o processamento. modo: 'links' ou 'links_com_imagens'."""

    ext = Path(arquivo.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, detail=f"Formato inválido '{ext}'. Use .xlsx, .xls ou .csv")

    if loja not in CONFIG["lojas"]:
        raise HTTPException(400, detail=f"Loja '{loja}' inválida.")

    if modo not in ("links", "links_com_imagens"):
        raise HTTPException(400, detail="Modo inválido. Use 'links' ou 'links_com_imagens'.")

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir()

    input_path = job_dir / f"input{ext}"
    conteudo = await arquivo.read()
    with open(input_path, "wb") as f:
        f.write(conteudo)

    jobs[job_id] = JobState(job_id=job_id, loja=loja, output_dir=str(job_dir))
    _salvar_estado(jobs[job_id])  # persistencia imediata pra polling pegar mesmo em outra request
    background_tasks.add_task(_executar_pipeline, job_id, str(input_path), loja, modo, str(job_dir))
    _limpar_jobs_antigos()

    return {"job_id": job_id}


async def _executar_pipeline(job_id: str, filepath: str, loja: str, modo: str, output_dir: str):
    from web.core import processar, ProcessamentoError

    job = jobs.get(job_id)
    if not job:
        return

    job.status = "processando"
    _salvar_estado(job)

    def progresso(msg: str, pct: int):
        if job_id in jobs:
            jobs[job_id].mensagem = msg
            jobs[job_id].percent = pct
            _salvar_estado(jobs[job_id])  # cada tick de progresso persiste

    try:
        resultado = await asyncio.to_thread(
            processar, filepath, loja, output_dir, modo, progresso
        )
        job.status = "concluido"
        n_ok = resultado["produtos"]
        n_rej = resultado.get("rejeitados", 0)
        if n_rej > 0:
            job.mensagem = f"{n_ok} produtos OK + {n_rej} rejeitados (veja a planilha 'Rejeitados')."
        else:
            job.mensagem = f"{n_ok} produtos processados com sucesso!"
        job.percent = 100
        job.shopee_path = resultado["shopee_path"]
        job.erp_path = resultado["erp_path"]
        job.kakashi_path = resultado.get("kakashi_path")
        job.rejeitados_path = resultado.get("rejeitados_path")
        job.produtos = n_ok
        job.rejeitados = n_rej
        job.avisos = resultado.get("avisos", [])
        # Snapshot do input_json pra suportar /api/descartar — operador pode
        # marcar produtos com capa cortada pra remover; regeneramos as
        # planilhas com a lista filtrada.
        job.input_json = resultado.get("input_json")

    except ProcessamentoError as e:
        job.status = "erro"
        job.erro = str(e)
        job.mensagem = str(e)
        job.avisos = getattr(e, "avisos", []) or []
    except Exception as e:
        job.status = "erro"
        job.erro = f"Erro inesperado: {e}"
        job.mensagem = "Ocorreu um erro inesperado. Tente novamente."
    finally:
        _salvar_estado(job)  # estado final (concluido OU erro)


def _get_job(job_id: str) -> Optional[JobState]:
    """Retorna JobState do dict em memoria OU fallback do disco (/tmp/jobs/<id>/_state.json).
    Cobre o cenario onde o request HTTP cai em container Lambda warm que ja
    rodou o pipeline mas perdeu o dict (modulo recarregado). Cross-container
    100% ainda requer storage compartilhado (Vercel Blob/KV — follow-up)."""
    job = jobs.get(job_id)
    if job is None:
        job = _carregar_estado(job_id)
        if job is not None:
            jobs[job_id] = job  # cache de volta no dict pra reqs subsequentes
    return job


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job não encontrado")
    return {
        "job_id":          job_id,
        "status":          job.status,
        "mensagem":        job.mensagem,
        "percent":         job.percent,
        "produtos":        job.produtos,
        "rejeitados":      job.rejeitados,
        "tem_rejeitados":  bool(job.rejeitados_path),
        "avisos":          job.avisos,
        "erro":            job.erro,
    }


@app.get("/api/download/{job_id}/{tipo}")
async def download(job_id: str, tipo: str):
    if tipo not in ("shopee", "erp", "kakashi", "rejeitados"):
        raise HTTPException(400, detail="Tipo deve ser 'shopee', 'erp', 'kakashi' ou 'rejeitados'")

    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job não encontrado")
    if job.status != "concluido":
        raise HTTPException(400, detail="Processamento ainda não concluído")

    caminho = {
        "shopee":     job.shopee_path,
        "erp":        job.erp_path,
        "kakashi":    job.kakashi_path,
        "rejeitados": job.rejeitados_path,
    }[tipo]
    if not caminho or not Path(caminho).exists():
        raise HTTPException(404, detail="Arquivo não encontrado")

    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{Path(caminho).name}"'},
    )


@app.get("/api/produtos/{job_id}")
async def produtos(job_id: str):
    """Lista produtos processados com SKU + display + URL capa pra revisao
    visual de capas cortadas antes da ativacao na Shopee."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job não encontrado")
    if job.status != "concluido":
        raise HTTPException(400, detail="Processamento ainda não concluído")
    if not job.input_json:
        # Job antigo (de antes do JobState.input_json existir) — sem suporte
        return {"produtos": [], "loja": job.loja, "suporte_descarte": False}

    lista = []
    for p in job.input_json.get("produtos", []):
        tipo = p.get("tipo", "Q1")
        sku_base = p.get("nome_arte_sku", "")
        lista.append({
            "sku_completo": f"{tipo}_{sku_base}",  # ex: KIT3_AnimaisOceano
            "sku_base":     sku_base,              # ex: AnimaisOceano
            "tipo":         tipo,
            "display":      p.get("nome_arte_display", ""),
            "titulo":       p.get("titulo_shopee", ""),
            "imagem_capa":  p.get("imagem_capa", ""),
            "descartado":   sku_base in job.descartados,
        })
    return {
        "produtos":         lista,
        "loja":             job.loja,
        "suporte_descarte": True,
    }


@app.post("/api/descartar")
async def descartar(payload: dict):
    """Filtra produtos descartados (operador marcou capa ruim), regenera
    as planilhas Shopee/ERP/Kakashi com a lista limpa, e remove os SKUs
    descartados do skus_em_uso.json (libera reuso futuro).

    Body: { "job_id": str, "skus_base": ["AnimaisOceano", "AstronautaFofo"] }
    """
    job_id = payload.get("job_id")
    skus_base = payload.get("skus_base", [])
    if not job_id:
        raise HTTPException(400, detail="job_id obrigatório")
    if not isinstance(skus_base, list):
        raise HTTPException(400, detail="skus_base deve ser lista")

    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job não encontrado")
    if job.status != "concluido":
        raise HTTPException(400, detail="Processamento ainda não concluído")
    if not job.input_json:
        raise HTTPException(400, detail="Job antigo (sem snapshot do input_json) — refaça o processamento.")
    if not skus_base:
        return {"produtos_ativos": job.produtos, "descartados": 0, "mensagem": "Nenhum SKU marcado pra descarte."}

    skus_descartados_set = set(skus_base)

    # 1. Filtra produtos_ok removendo descartados
    produtos_originais = job.input_json.get("produtos", [])
    produtos_filtrados = [p for p in produtos_originais if p.get("nome_arte_sku") not in skus_descartados_set]
    n_descartados = len(produtos_originais) - len(produtos_filtrados)

    if n_descartados == 0:
        return {"produtos_ativos": job.produtos, "descartados": 0,
                "mensagem": "Nenhum SKU listado bateu com produtos do job."}

    if not produtos_filtrados:
        raise HTTPException(400, detail="Você descartou TODOS os produtos. Operação cancelada.")

    # 2. Remove SKUs descartados do skus_em_uso.json (libera reuso)
    import build_shopee_template as _bs
    skus_db = _bs.carregar_skus()
    removidos_db = []
    for sku_base in skus_base:
        if sku_base in skus_db:
            skus_db.pop(sku_base)
            removidos_db.append(sku_base)
    if removidos_db:
        _bs.salvar_skus(skus_db)

    # 3. Regenera planilhas com a lista filtrada
    novo_input = {"loja": job.loja, "produtos": produtos_filtrados}
    output_dir = job.output_dir or str(JOBS_DIR / job.job_id)

    try:
        import build_erp_template as _berp
        import export_kakashi as _ekak
        job.shopee_path = _bs.gerar_shopee(novo_input, output_dir)
        job.erp_path = _berp.gerar_erp(novo_input, output_dir, loja=job.loja)
        kakashi_path, _ = _ekak.gerar_kakashi(novo_input, output_dir)
        job.kakashi_path = kakashi_path
    except Exception as e:
        raise HTTPException(500, detail=f"Erro ao regenerar planilhas: {e}")

    # 4. Atualiza estado
    job.input_json = novo_input
    job.descartados = list(set(job.descartados or []) | skus_descartados_set)
    job.produtos = len(produtos_filtrados)
    job.mensagem = f"{len(produtos_filtrados)} produtos ativos ({n_descartados} descartados nesta sessão)"
    _salvar_estado(job)

    return {
        "produtos_ativos":  len(produtos_filtrados),
        "descartados":      n_descartados,
        "removidos_do_db":  len(removidos_db),
        "mensagem":         f"{n_descartados} produtos descartados. Planilhas regeneradas. SKUs liberados pra reuso: {len(removidos_db)}.",
    }


@app.get("/api/modelo/{tipo}")
async def modelo(tipo: str):
    """
    Gera e serve um modelo de planilha de entrada para download.
    tipo: 'links' | 'links_com_imagens'
    """
    if tipo not in ("links", "links_com_imagens"):
        raise HTTPException(400, detail="Tipo deve ser 'links' ou 'links_com_imagens'")

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.comments import Comment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilha"

    header_fill = PatternFill("solid", fgColor="4F46E5")
    header_font = Font(color="FFFFFF", bold=True)

    if tipo == "links":
        ws.title = "Links Etsy"
        headers = ["QUANTIDADE", "LINK DO ANÚNCIO"]
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 70
        # Linha de exemplo
        ws.append([3, "https://www.etsy.com/pt/listing/123456789/nome-do-produto"])
        example_row = ws[2]
        for cell in example_row:
            cell.font = Font(color="9CA3AF", italic=True)
        filename = "modelo_links_etsy.xlsx"
    else:
        ws.title = "Links + Imagens"
        headers = ["QUANTIDADE", "LINK DO ANÚNCIO", "IMAGEM CAPA", "IMAGEM 1", "IMAGEM 2", "IMAGEM 3"]
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 60
        for col in ["C", "D", "E", "F"]:
            ws.column_dimensions[col].width = 45
        ws.append([
            3,
            "https://www.etsy.com/pt/listing/123456789/nome-do-produto",
            "https://i.etsystatic.com/xxx/capa.jpg",
            "https://i.etsystatic.com/xxx/img1.jpg",
            "https://i.etsystatic.com/xxx/img2.jpg",
            "https://i.etsystatic.com/xxx/img3.jpg",
        ])
        example_row = ws[2]
        for cell in example_row:
            cell.font = Font(color="9CA3AF", italic=True)
        filename = "modelo_links_com_imagens.xlsx"

    # Inserir cabeçalho na linha 1 (deslocar exemplo para linha 2)
    ws.insert_rows(1)
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Tooltip explicando os valores aceitos na coluna QUANTIDADE
    quantidade_comment = Comment(
        "Coluna QUANTIDADE:\n"
        "  1 = Solo (Q1)\n"
        "  2 = Kit 2 quadros (KIT2)\n"
        "  3 = Kit 3 quadros (KIT3)\n"
        "  Vazio = Detecção automática pelo LLM",
        "Peter",
    )
    quantidade_comment.width = 280
    quantidade_comment.height = 90
    ws["A1"].comment = quantidade_comment

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/desconto")
async def desconto(arquivo: UploadFile = File(...)):
    """
    Recebe um mass_update_sales_info.xlsx exportado da Shopee Seller Center
    e devolve o template-discount.xlsx preenchido com (Preço original, Preço
    de desconto) baseados na tabela canônica do config.json (Q1/KIT2/KIT3).

    Operação síncrona — sem job system. Retorno direto pra download.
    """
    ext = Path(arquivo.filename or "").suffix.lower()
    if ext not in (".xlsx",):
        raise HTTPException(400, detail=f"Formato inválido '{ext}'. Use .xlsx exportado pela Shopee.")

    # Salvar upload em /tmp pra ler com openpyxl
    tmp_dir = JOBS_DIR / f"desconto_{uuid.uuid4()}"
    tmp_dir.mkdir()
    input_path = tmp_dir / arquivo.filename
    conteudo = await arquivo.read()
    with open(input_path, "wb") as f:
        f.write(conteudo)

    try:
        import build_discount_template as _bd
        caminho, avisos = _bd.gerar_discount(str(input_path), str(tmp_dir))
    except Exception as e:
        # cleanup parcial e bubble up
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(400, detail=f"Erro ao gerar planilha de desconto: {e}")

    # Stream da resposta a partir de buffer (pra poder limpar o tmp_dir depois)
    with open(caminho, "rb") as f:
        buf = io.BytesIO(f.read())
    shutil.rmtree(tmp_dir, ignore_errors=True)
    buf.seek(0)

    # X-Avisos: warnings agregados (SKUs sem lookup) — frontend pode mostrar
    avisos_header = "|".join(avisos[:5])  # limitar tamanho do header
    if len(avisos) > 5:
        avisos_header += f"|... e mais {len(avisos) - 5}"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{Path(caminho).name}"',
            "X-Avisos": avisos_header[:2000],
            "X-Avisos-Count": str(len(avisos)),
            "Access-Control-Expose-Headers": "X-Avisos, X-Avisos-Count, Content-Disposition",
        },
    )


# ── Estáticos ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
