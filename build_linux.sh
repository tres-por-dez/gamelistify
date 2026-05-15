#!/bin/bash
set -e

APP_VERSION=$(cat VERSION 2>/dev/null || echo "000")
APP_NAME="gamelistify_v${APP_VERSION}"

uv pip install -r requirements.txt
uv add --dev pyinstaller

UV_PYTHON_BASE=$(uv run python3 -c "import sys; print(sys._base_executable)")
UV_PYTHON_ROOT=$(dirname $(dirname $(dirname "${UV_PYTHON_BASE}")))
TCL_LIB=$(find "${UV_PYTHON_ROOT}" -name "libtcl9.0.so" | head -1)
TK_LIB=$(find "${UV_PYTHON_ROOT}" -name "libtcl9tk9.0.so" | head -1)

if [ -z "${TCL_LIB}" ] || [ -z "${TK_LIB}" ]; then
    echo "Erro: libtcl9.0.so ou libtcl9tk9.0.so não encontradas em ${UV_PYTHON_ROOT}"
    exit 1
fi

uv run pyinstaller --onefile \
    --add-data "icons:icons" \
    --add-binary "${TCL_LIB}:." \
    --add-binary "${TK_LIB}:." \
    --collect-all tkinter \
    --collect-all customtkinter \
    --hidden-import _tkinter \
    --hidden-import PIL._tkinter_finder \
    --name="${APP_NAME}" \
    main.py