@echo off
set /p APP_VERSION=<VERSION
set APP_NAME=gamelistify_windows_v%APP_VERSION%

uv add --dev pyinstaller

uv run pyinstaller --onefile ^
    --icon=icons/app_icon.ico ^
    --add-data "icons;icons" ^
    --name=%APP_NAME% ^
    main.py