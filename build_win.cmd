@echo off
set /p APP_VERSION=<VERSION
set APP_NAME=gamelistify_v%APP_VERSION%

pyinstaller --onefile --windowed ^
    --icon=icons/app_icon.ico ^
    --add-data "icons;icons" ^
    --name=%APP_NAME% ^
    main.py