@echo off
echo ================================================
echo   Building MapHelper Executable
echo ================================================
echo.

echo [1/4] Installing PyInstaller...
pip install pyinstaller
echo.

echo [2/4] Building executable with PyInstaller...
pyinstaller --clean build.spec
echo.

echo [3/4] Creating release package...
if exist release rmdir /s /q release
mkdir release
xcopy dist\MapHelper.exe release\ /Y
copy config.json.example release\config.json
copy settings.json.example release\settings.json
copy README.md release\
copy LICENSE release\
echo # MapHelper - Standalone Executable > release\README.txt
echo. >> release\README.txt
echo All maps and fonts are embedded in MapHelper.exe >> release\README.txt
echo. >> release\README.txt
echo To run: >> release\README.txt
echo 1. Double-click MapHelper.exe >> release\README.txt
echo 2. Press M to toggle map overlay >> release\README.txt
echo 3. Press R to reset cache >> release\README.txt
echo 4. Press ESC twice to exit >> release\README.txt
echo. >> release\README.txt
echo First run will ask you to select the map area (ROI). >> release\README.txt
echo Settings are saved in config.json and settings.json >> release\README.txt
echo.

echo [4/4] Creating zip archive...
powershell Compress-Archive -Path release\* -DestinationPath MapHelper-Local-Windows.zip -Force
echo.

echo ================================================
echo   Build complete!
echo ================================================
echo.
echo   Executable: dist\MapHelper.exe
echo   Package:    MapHelper-Local-Windows.zip
echo   Test dir:   release\
echo.
echo   To test: cd release && MapHelper.exe
echo ================================================

pause
