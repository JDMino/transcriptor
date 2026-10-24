import subprocess
import sys
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / "venv"
REQ = RAIZ / "requirements.txt"
MARCA = VENV / ".instalado"


def python_del_venv():
    sub = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    return VENV / sub


def main():
    if sys.version_info < (3, 10):
        sys.exit("Se necesita Python 3.10 o superior.")

    py = python_del_venv()
    if not py.exists():
        print("Creando entorno virtual…")
        venv.create(VENV, with_pip=True)

    # Instala si es la primera vez o si requirements.txt cambió
    if not MARCA.exists() or MARCA.stat().st_mtime < REQ.stat().st_mtime:
        print("Instalando dependencias (solo la primera vez)…")
        subprocess.check_call(
            [str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call(
            [str(py), "-m", "pip", "install", "-r", str(REQ)])
        MARCA.touch()

    subprocess.call([str(py), str(RAIZ / "transcriptor.py")])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\nFalló la instalación (código {e.returncode}).")
        print("Probá con Python 3.12 o 3.13 y borrá la carpeta 'venv'.")
        input("Presioná Enter para salir…")
