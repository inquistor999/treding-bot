@echo off
rem Botni ishga tushiradi va biror sabab bilan to'xtab qolsa, 30 soniyadan keyin o'zi qayta ishga tushiradi.
cd /d "%~dp0.."
:loop
echo [%date% %time%] Bot ishga tushmoqda...
python main.py xm --mode demo
echo [%date% %time%] Bot to'xtadi. 30 soniyadan keyin qayta ishga tushadi (to'xtatish uchun oynani yoping).
timeout /t 30 /nobreak >nul
goto loop
