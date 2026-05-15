#!/bin/bash

# Lê a versão do arquivo VERSION
if [ -f VERSION ]; then
    APP_VERSION=$(cat VERSION | tr -d '\r\n')
else
    APP_VERSION="0.0.9"
fi

APP_NAME="gamelistify_v${APP_VERSION}"
ICON_PATH="icons/app_icon.ico"

echo "Iniciando build para Linux (v${APP_VERSION})..."

# Garante que as dependências estejam instaladas (opcional)
# pip install pyinstaller

uv run --python 3.14 pyinstaller --onefile --windowed \
    --add-data "icons:icons" \
    --name="gamelistify_v${APP_VERSION}" \
    main.py

tar -czvf "dist/${APP_NAME}.tar.gz" -C dist "${APP_NAME}"
    
# pyinstaller --onefile --windowed \
#     --icon="${ICON_PATH}" \
#     --add-data "icons:icons" \
#     --name="${APP_NAME}" \
#     main.py

if [ $? -eq 0 ]; then
    echo "-------------------------------------------"
    echo "Build concluído com sucesso!"
    echo "Executável disponível em: dist/${APP_NAME}"
    echo "-------------------------------------------"
else
    echo "Erro durante o processo de build."
    exit 1
fi

