@echo off
setlocal
call cif2xrd_venv\Scripts\activate.bat

if exist dist rmdir /s /q dist

call python -m build .

:: Read token from file
set /p PYPI_TOKEN=<cif2xrd_venv\PyPI_token.txt

:: Optional: verify it loaded
echo Loaded token: %PYPI_TOKEN:~0,6%******

:: Upload using Twine
twine upload dist/* -u __token__ -p %PYPI_TOKEN% --verbose

endlocal
