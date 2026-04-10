"""
app.py — Servidor FastAPI para o frontend Etsy → Shopee.

Rotas:
  GET  /                          — Serve index.html
  GET  /api/lojas                 — Lista lojas disponíveis
  POST /api/processar             — Inicia job de processamento
  GET  /api/status/{job_id}       — Consulta status do job
  GET  /api/download/{job_id}/{tipo} — Download do arquivo gerado

Executar:
  python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import sys
import json
import uuid
import asyncio
import shutil
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Carregar .env
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# Adicionar raiz do projeto ao path para importar web.core
sys.path.insert(0, str(BASE_DIR))

CONFIG_PATH = BASE_DIR / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"

# No Vercel o filesystem e read-only; usar /tmp para armazenamento temporario
IS_VERCEL = bool(os.environ.get("VERCEL"))
JOBS_DIR = Path("/tmp/jobs") if IS_VERCEL else WEB_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Etsy → Shopee")


# ── Gerenciamento de jobs ──────────────────────────────────────────────────

@dataclass
class JobState:
    job_id: str
    status: str = "aguardando"        # aguardando | processando | concluido | erro
    mensagem: str = "Aguardando início..."
    percent: int = 0
    shopee_path: Optional[str] = None
    erp_path: Optional[str] = None
    produtos: int = 0
    avisos: list = field(default_factory=list)
    erro: Optional[str] = None
    criado_em: datetime = field(default_factory=datetime.now)


jobs: dict[str, JobState] = {}


def _limpar_jobs_antigos():
    """Remove jobs criados ha mais de 2 horas."""
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
    """Serve o frontend."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/lojas")
async def get_lojas():
    """Retorna as lojas configuradas."""
    lojas = []
    descricoes = {
        "PPJ": "Quadros religiosos e minimalistas",
        "iPaper": "Arte, Bauhaus e design moderno",
        "AllQuadros": "Kits e conjuntos decorativos",
    }
    for nome in CONFIG["lojas"]:
        lojas.append({
            "id": nome,
            "nome": nome,
            "descricao": descricoes.get(nome, ""),
        })
    return {"lojas": lojas}


@app.post("/api/processar")
async def processar(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(...),
    loja: str = Form(...),
):
    """Inicia o processamento de uma planilha."""

    # Validar extensao
    ext = Path(arquivo.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido '{ext}'. Use .xlsx, .xls ou .csv"
        )

    # Validar loja
    if loja not in CONFIG["lojas"]:
        raise HTTPException(
            status_code=400,
            detail=f"Loja '{loja}' inválida. Use: {', '.join(CONFIG['lojas'].keys())}"
        )

    # Criar job
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir()

    # Salvar arquivo
    input_path = job_dir / f"input{ext}"
    conteudo = await arquivo.read()
    with open(input_path, "wb") as f:
        f.write(conteudo)

    # Registrar job
    jobs[job_id] = JobState(job_id=job_id)

    # Iniciar processamento em background
    background_tasks.add_task(_executar_pipeline, job_id, str(input_path), loja, str(job_dir))

    # Limpar jobs antigos (oportunisticamente)
    _limpar_jobs_antigos()

    return {"job_id": job_id}


async def _executar_pipeline(job_id: str, filepath: str, loja: str, output_dir: str):
    """Executa o pipeline em background."""
    from web.core import processar, ProcessamentoError

    job = jobs.get(job_id)
    if not job:
        return

    job.status = "processando"

    def progresso(msg: str, pct: int):
        if job_id in jobs:
            jobs[job_id].mensagem = msg
            jobs[job_id].percent = pct

    try:
        resultado = await asyncio.to_thread(
            processar, filepath, loja, output_dir, progresso
        )
        job.status = "concluido"
        job.mensagem = f"{resultado['produtos']} produtos processados com sucesso!"
        job.percent = 100
        job.shopee_path = resultado["shopee_path"]
        job.erp_path = resultado["erp_path"]
        job.produtos = resultado["produtos"]
        job.avisos = resultado.get("avisos", [])

    except ProcessamentoError as e:
        job.status = "erro"
        job.erro = str(e)
        job.mensagem = str(e)
    except Exception as e:
        job.status = "erro"
        job.erro = f"Erro inesperado: {e}"
        job.mensagem = "Ocorreu um erro inesperado. Tente novamente."


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    """Retorna o status atual de um job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    return {
        "job_id": job_id,
        "status": job.status,
        "mensagem": job.mensagem,
        "percent": job.percent,
        "produtos": job.produtos,
        "avisos": job.avisos,
        "erro": job.erro,
    }


@app.get("/api/download/{job_id}/{tipo}")
async def download(job_id: str, tipo: str):
    """Download da planilha gerada (tipo: shopee ou erp)."""
    if tipo not in ("shopee", "erp"):
        raise HTTPException(status_code=400, detail="Tipo deve ser 'shopee' ou 'erp'")

    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status != "concluido":
        raise HTTPException(status_code=400, detail="Processamento ainda não concluído")

    caminho = job.shopee_path if tipo == "shopee" else job.erp_path
    if not caminho or not Path(caminho).exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    nome_arquivo = Path(caminho).name
    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


# ── Arquivos estáticos (servir depois das rotas API) ──────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
