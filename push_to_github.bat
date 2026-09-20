@echo off
echo ============================================
echo   Push to GitHub: pillow758/ruanzhu_test1
echo ============================================
echo.

cd /d "%~dp0"

echo [1/6] Init git repo...
git init
git checkout -b main

echo [2/6] Add all files...
git add .

echo [3/6] Commit...
git commit -m "init: logistics scheduling system based on Clark-Wright algorithm"

echo [4/6] Set remote...
git remote remove origin 2>nul
git remote add origin https://github.com/pillow758/ruanzhu_test1.git

echo [5/6] Pull remote if exists...
git pull origin main --allow-unrelated-histories 2>nul

echo [6/6] Push to GitHub...
git push -u origin main --force

echo.
echo ============================================
echo   Done! Visit: https://github.com/pillow758/ruanzhu_test1
echo ============================================
pause
