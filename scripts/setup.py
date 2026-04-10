"""
setup.py — Valida ambiente e instala dependencias.
Executar uma vez antes de usar o sistema.
"""
import subprocess, sys, os

DEPS = ["openpyxl", "xlrd", "requests", "python-dotenv"]

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
    print("=== Setup: Agent_NewProductShopee ===\n")
    install_deps()
    check_dirs()
    env_ok = check_env()
    tpl_ok = check_templates()

    print()
    if env_ok and tpl_ok:
        print("Ambiente OK! Pronto para usar.")
    else:
        print("Ambiente com avisos. Resolva os itens acima antes de continuar.")
