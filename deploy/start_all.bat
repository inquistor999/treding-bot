@echo off
rem Windows'ga kirganda MT5 ni ochadi, 90 soniya kutadi (EA ishga tushsin), keyin botni ishga tushiradi.
rem Agar MT5 boshqa papkada o'rnatilgan bo'lsa, quyidagi yo'lni o'zgartiring.
set MT5="C:\Program Files\XM Global MT5\terminal64.exe"
start "" %MT5%
timeout /t 90 /nobreak >nul
call "%~dp0run_bot.bat"
