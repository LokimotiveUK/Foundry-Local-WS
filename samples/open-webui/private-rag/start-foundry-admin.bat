@echo off
:: Start Foundry Local Service (Run as Administrator)
:: This script must be run with admin privileges

echo Starting Foundry Local service...
foundry service start
timeout /t 3 /nobreak > nul
foundry service status
echo.
echo Press any key to close...
pause > nul
