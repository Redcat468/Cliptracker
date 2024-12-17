@echo off
echo Creation de l'executable...
pyinstaller --onefile --add-data "rtfactor.conf;." app.py
echo Build terminé. Verifiez le dossier 'dist'.
pause