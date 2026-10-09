@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || goto no_python
if not exist bridge\.data mkdir bridge\.data
set "GAMEDIR="
if exist bridge\.data\game_dir.txt set /p GAMEDIR=<bridge\.data\game_dir.txt
if defined GAMEDIR goto have_dir
echo По инструкции GAMMA папки Anomaly и GAMMA лежат рядом в корне диска, а не одна внутри другой.
echo Например: C:\Anomaly и C:\GAMMA. Можно указать любую из них.
set /p GAMEDIR=Папка: 
:have_dir
set "GAMEDIR=%GAMEDIR:"=%"
>bridge\.data\game_dir.txt echo %GAMEDIR%
echo Ищу снимки в %GAMEDIR% и во второй папке установки в корне того же диска.
echo Чтобы остановить ПДА, закройте это окно.
cd bridge
python -m pda_bridge --find-in "%GAMEDIR%" --open
if errorlevel 1 del .data\game_dir.txt
pause
exit /b 0

:no_python
echo Python не найден. Установите Python с https://www.python.org/downloads/
echo и при установке отметьте галочку "Add python.exe to PATH".
pause
exit /b 1
