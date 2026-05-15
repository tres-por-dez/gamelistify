#!/bin/bash

if [ -f VERSION ]; then
    APP_VERSION=$(cat VERSION)
else
    APP_VERSION="000"
fi

APP_NAME="gamelistify_v${APP_VERSION}"
ICON_PATH="icons/app_icon.ico"

uv add nuitka --dev
uv run python -m nuitka \
    --standalone \
    --onefile \
    --plugin-enable=tk-inter \
    --include-data-dir=icons=icons \
    --output-filename="${APP_NAME}" \
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

