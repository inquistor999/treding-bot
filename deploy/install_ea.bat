@echo off
rem BridgeEA ni XM MT5 papkasiga nusxalaydi va kompilyatsiya qiladi. MT5 kamida bir marta ochilgan bo'lishi kerak.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_ea.ps1"
pause
