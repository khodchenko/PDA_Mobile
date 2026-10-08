@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || goto no_python
if not exist bridge\.data mkdir bridge\.data
set "GAMEDIR="
if exist bridge\.data\game_dir.txt set /p GAMEDIR=<bridge\.data\game_dir.txt
if defined GAMEDIR goto have_dir
echo Укажите папку, куда установлена GAMMA: ту, в которой лежат папки Anomaly и GAMMA.
echo Например: C:\GAMMA
set /p GAMEDIR=Папка: 
:have_dir
set "GAMEDIR=%GAMEDIR:"=%"
>bridge\.data\game_dir.txt echo %GAMEDIR%
echo Ищу снимки игры в %GAMEDIR%
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
