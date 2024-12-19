@echo off
echo Creation de l'executable...
pyinstaller --onefile --windowed --name "cliptracker" ^
--icon "static/images/cliptracker.ico" ^
--add-data "static/images/cliptracker.svg;static/images" ^
--add-data "static/images/cliptracker.ico;static/images" ^
--add-data "static;static" ^
--collect-all "pystray" ^
--collect-all "PIL" ^
--hidden-import "pystray._win32" ^
--hidden-import "pystray._base" ^
app.py
echo Build terminé. Verifiez le dossier 'dist'.
pause
