@echo off
set /p APP_VERSION=<VERSION
set APP_NAME=gamelistify_v%APP_VERSION%

:: Obtém o caminho do site-packages do seu venv
set VENV_PACKAGES=.venv\Lib\site-packages

uv run pyinstaller --onefile --windowed ^
    --paths=%VENV_PACKAGES% ^
    --add-data "icons;icons" ^
    --add-data "%VENV_PACKAGES%\customtkinter;customtkinter" ^
    --icon=icons/app_icon.ico ^
    --name=%APP_NAME% ^
    main.py