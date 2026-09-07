@echo off
rem Сборка автономного exe: dist\WinThemeSwitcher.exe
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python tools\make_icon.py || exit /b 1
python -m PyInstaller --noconsole --onefile --name WinThemeSwitcher ^
  --icon assets\icon.ico --add-data "assets;assets" main.py || exit /b 1
echo.
echo Готово: dist\WinThemeSwitcher.exe
