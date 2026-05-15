#!/bin/bash

if [ -f VERSION ]; then
    APP_VERSION=$(cat VERSION)
else
    APP_VERSION="000"
fi

APP_NAME="gamelistify_v${APP_VERSION}"
ICON_PATH="icons/app_icon.ico"

uv add pyinstaller --dev

PYTHON_BIN=$(uv run which python)
PYTHON_HOME=$(uv run python -c "import sys; from pathlib import Path; print(Path(sys.executable).parent.parent)")
LIB_PATH="${PYTHON_HOME}/lib"

export LD_LIBRARY_PATH="$LIB_PATH:$LD_LIBRARY_PATH"

# Localiza o diretório de bibliotecas real do Python 3.14
PYTHON_LIB_DIR=$(uv run python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
TCL_V="9.0"

echo "Buscando libs em: ${PYTHON_LIB_DIR}"

uv run pyinstaller --onefile --windowed \
    --name="${APP_NAME}" \
    --add-data "icons:icons" \
    --collect-all tkinter \
    --add-binary "${PYTHON_LIB_DIR}/libtcl${TCL_V}.so:." \
    --add-binary "${PYTHON_LIB_DIR}/libtk${TCL_V}.so:." \
    main.py

if [ $? -eq 0 ]; then
    echo "-------------------------------------------"
    echo "Build success!"
    echo "dist/${APP_NAME}"
    echo "-------------------------------------------"
else
    echo "Error occurred.."
    exit 1
fi

