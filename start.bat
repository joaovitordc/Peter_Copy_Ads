@echo off
REM Inicia o servidor web Etsy -> Shopee localmente.
REM Acesse em http://localhost:8000 apos o servidor subir.
REM Pressione Ctrl+C para parar.

cd /d "%~dp0"
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
