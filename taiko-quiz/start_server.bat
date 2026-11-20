@echo off
rem Start a local web server for the quiz and open it in the browser.
rem (YouTube playback does not work when index.html is opened directly as a file.)
rem The browser is started with autoplay allowed, so the BGM plays without clicking the page.
rem It uses its own profile folder (%LOCALAPPDATA%\taiko-quiz-browser) so the setting works
rem even while your normal Chrome/Edge is already open.
rem Close this window to stop the server.
cd /d "%~dp0"
if "%~1"=="open" goto open

set "URL=http://localhost:8000/index.html"
set "BROWSER="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "BROWSER=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

rem open the browser (this same file with "open") after the server has had a moment to start
start "" /b cmd /c ""%~f0" open"
python -m http.server 8000 --bind 127.0.0.1
if errorlevel 1 echo.
if errorlevel 1 echo Python was not found or port 8000 is in use.
if errorlevel 1 pause
goto :eof

:open
ping -n 2 127.0.0.1 >nul
if not defined BROWSER start "" "%URL%"
if not defined BROWSER goto :eof
start "" "%BROWSER%" --user-data-dir="%LOCALAPPDATA%\taiko-quiz-browser" --autoplay-policy=no-user-gesture-required --no-first-run --no-default-browser-check "%URL%"
