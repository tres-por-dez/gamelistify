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

uv run pyinstaller --onefile --windowed \
    --name="${APP_NAME}" \
    --add-data "icons:icons" \
    --collect-all tkinter \
    --collect-all _tkinter \
    --hidden-import=tkinter \
    --add-binary "${LIB_PATH}/libtcl9.0.so:." \
    --add-binary "${LIB_PATH}/libtk9.0.so:." \
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

