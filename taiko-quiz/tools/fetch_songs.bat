@echo off
rem Fetch song pages from the wiki slowly (about 1 page / 20 sec).
rem In parallel, a second window converts new chart images into chart data (charts/*.js)
rem every 5 minutes and rebuilds ..\data.js, so the number of charts grows while fetching.
rem Safe to close at any time; run again to resume from the cache.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
start "parse_charts" cmd /c "set WATCH=300&& python -I parse_charts.py"
python -I scrape_songs.py cache\songs lists.json details.json
python -I build_data.py
pause
