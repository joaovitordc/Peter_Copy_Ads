"""
setup.py — Valida ambiente e instala dependencias.
Executar uma vez antes de usar o sistema.
"""
import subprocess, sys, os

DEPS = [
    "openpyxl",
    "xlrd",
    "requests",
    "python-dotenv",
    "fastapi",
    "uvicorn[standard]",
    "python-multipart",
    "opencv-python-headless",
    "numpy",
    "google-genai",
]

def install_deps():
    print("Instalando dependencias...")
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + DEPS, stdout=subprocess.DEVNULL)
    print(f"  OK: {', '.join(DEPS)}")

def check_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        print("\n[AVISO] Arquivo .env nao encontrado.")
        print("  Crie o arquivo .env na raiz do projeto com o conteudo:")
        print("  IMGBB_API_KEY=sua_chave_aqui")
        print("  Obtenha a chave gratuita em: https://api.imgbb.com/")
        return False

    with open(env_path) as f:
        content = f.read()

    if "IMGBB_API_KEY" not in content or "sua_chave_aqui" in content:
        print("\n[AVISO] IMGBB_API_KEY nao configurada no .env")
        print("  Edite o .env e insira sua chave real do ImgBB.")
        return False

    print("  OK: .env com IMGBB_API_KEY encontrado")

    # Modo "So Links" precisa de Firecrawl OU Etsy API. Modo "Links + Imagens" nao precisa.
    has_firecrawl = "FIRECRAWL_API_KEY=fc-" in content and "fc-..." not in content
    has_etsy      = "ETSY_API_KEY=" in content and "keystring:shared_secret" not in content
    if has_firecrawl:
        print("  OK: FIRECRAWL_API_KEY configurada (modo 'So Links' habilitado)")
    elif has_etsy:
        print("  OK: ETSY_API_KEY configurada (modo 'So Links' usara Etsy Open API)")
    else:
        print("  [INFO] Sem FIRECRAWL_API_KEY nem ETSY_API_KEY - modo 'So Links' indisponivel.")
        print("         Modo 'Links + Imagens' continua funcionando normalmente.")
        print("         Para habilitar 'So Links', crie chave em: https://www.firecrawl.dev/")

    has_gemini = "GEMINI_API_KEY=" in content and not content.split("GEMINI_API_KEY=")[1].startswith(("\n", "..."))
    if has_gemini:
        print("  OK: GEMINI_API_KEY configurada (filtro de imagens sem quadro ativo)")
    else:
        print("  [INFO] GEMINI_API_KEY ausente - filtro de imagens DESATIVADO.")
        print("         Imagens de texto/video do anuncio Etsy podem aparecer na Shopee.")
        print("         Para ativar, crie chave em: https://aistudio.google.com/apikey")

    return True

def check_dirs():
    base = os.path.join(os.path.dirname(__file__), "..")
    dirs = [
        "planilhas_padrao",
        "planilhas_links_artes",
        "planilhas_geradas_shopee",
        "planilhas_geradas_erp",
    ]
    for d in dirs:
        path = os.path.join(base, d)
        os.makedirs(path, exist_ok=True)
    print(f"  OK: pastas de trabalho existem")

def check_templates():
    base = os.path.join(os.path.dirname(__file__), "..")
    templates = [
        ("planilhas_padrao", "Shopee_mass_upload", ".xlsx"),
        ("planilhas_padrao", "cadastrar_produtos_erp", ".xls"),
    ]
    ok = True
    for folder, name_part, ext in templates:
        folder_path = os.path.join(base, folder)
        if os.path.exists(folder_path):
            found = [f for f in os.listdir(folder_path) if name_part in f and f.endswith(ext)]
            if found:
                print(f"  OK: template encontrado: {found[0]}")
            else:
                print(f"  [AVISO] Template nao encontrado: *{name_part}*{ext} em {folder}/")
                ok = False
    return ok

if __name__ == "__main__":
    print("=== Setup: Peter_Copy_Ads ===\n")
    install_deps()
    check_dirs()
    env_ok = check_env()
    tpl_ok = check_templates()

    print()
    if env_ok and tpl_ok:
        print("Ambiente OK! Pronto para usar.")
    else:
        print("Ambiente com avisos. Resolva os itens acima antes de continuar.")
