@echo off
chcp 65001 >nul
cd /d "%~dp0bridge"
where python >nul 2>nul || goto no_python
echo ПДА в демо-режиме, без игры. Чтобы остановить, закройте это окно.
python -m pda_bridge --demo --open
pause
exit /b 0

:no_python
echo Python не найден. Установите Python с https://www.python.org/downloads/
echo и при установке отметьте галочку "Add python.exe to PATH".
pause
exit /b 1
