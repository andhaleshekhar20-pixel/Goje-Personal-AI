@echo off
setlocal
cd /d "%~dp0"
title Goje - Local Brain
where ollama >nul 2>nul
if errorlevel 1 (
  echo Installing official Ollama for Windows...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$u='https://ollama.com/download/OllamaSetup.exe';" ^
    "$o=$env:TEMP+'\OllamaSetup.exe';" ^
    "Invoke-WebRequest -Uri $u -OutFile $o;" ^
    "Start-Process $o -Wait"
)
echo Pulling Qwen3 4B local model...
ollama pull qwen3:4b
if errorlevel 1 (echo Model download failed.&pause&exit /b 1)
echo Creating Goje local reasoning model...
ollama create goje-brain -f "%~dp0local_ai\Goje.Modelfile"
if errorlevel 1 (echo Could not create goje-brain.&pause&exit /b 1)
echo Goje local reasoning brain is ready.
pause
endlocal
