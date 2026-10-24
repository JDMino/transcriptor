@echo off
chcp 65001 >nul
cd /d "%~dp0"
for %%V in (3.12 3.13 3.11 3.10) do (
    py -%%V --version >nul 2>nul && (py -%%V iniciar.py & goto fin)
)
python iniciar.py
:fin
pause
