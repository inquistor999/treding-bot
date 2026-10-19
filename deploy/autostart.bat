@echo off
rem Windows'ga kirganda start_all.bat avtomatik ishga tushishi uchun Startup papkasiga yorliq qo'yadi.
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
echo @echo off> "%STARTUP%\trading_bot_start.bat"
echo call "%~dp0start_all.bat">> "%STARTUP%\trading_bot_start.bat"
echo Tayyor: "%STARTUP%\trading_bot_start.bat"
pause
