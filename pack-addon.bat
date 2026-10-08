@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || goto no_python
python tools\pack_addon.py || goto failed
echo.
echo Готово. Архив для MO2 лежит в папке dist, она сейчас откроется.
explorer dist
pause
exit /b 0

:no_python
echo Python не найден. Установите Python с https://www.python.org/downloads/
echo и при установке отметьте галочку "Add python.exe to PATH".
pause
exit /b 1

:failed
echo Не получилось собрать архив, сообщение об ошибке выше.
pause
exit /b 1
