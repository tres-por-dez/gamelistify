@echo off
set /p APP_VERSION=<VERSION
set APP_NAME=gamelistify_v%APP_VERSION%

uv add --dev pyinstaller

uv run pyinstaller --onefile --windowed ^
    --icon=icons/app_icon.ico ^
    --add-data "icons;icons" ^
    --name=%APP_NAME% ^
    main.py