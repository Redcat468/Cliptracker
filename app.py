from flask import Flask, request, render_template_string, redirect, url_for, flash, get_flashed_messages
from ale_processor import AleProcessor
import sys
import os
import threading
import webbrowser
from pystray import Icon, MenuItem, Menu
from PIL import Image

app = Flask(__name__)
app.secret_key = "secret_key"

# Template HTML
template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cliptracker</title>
    <link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='images/cliptracker.ico') }}">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; color: #333; }
        .container { margin: 20px auto; padding: 20px; max-width: 1000px; background: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .volume { text-align: center; font-weight: bold; color: #2e7d32; margin-bottom: 20px; }
        .flash-message { padding: 10px; margin-bottom: 20px; border-radius: 5px; font-weight: bold; }
        .flash-error { background-color: #ffebee; color: #c62828; }
        .flash-success { background-color: #e8f5e9; color: #2e7d32; }
        .flash-warning { background-color: #fff3e0; color: #ef6c00; }
        .btn { display: inline-block; padding: 10px 20px; font-size: 16px; color: #fff; background-color: #4CAF50; border: none; border-radius: 15px; cursor: pointer; box-shadow: 0 2px 2px rgba(0,0,0,0.3); transition: background-color 0.2s ease, transform 0.2s ease; }
        .btn:hover { background-color: #45a049; transform: translateY(-2px); }
        .btn-red { background-color: #d32f2f; }
        .btn-red:hover { background-color: #c62828; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #fff; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; transition: background-color 0.3s ease; }
        th { background-color: #4CAF50; color: #fff; cursor: pointer; position: sticky; top: 0; z-index: 1; }
        th:hover { background-color: #45a049; }
        tr:hover td { background-color: #f1f1f1; }
        .error-row { background-color: #ffebee; color: #c62828; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
        .file-input-container { display: flex; justify-content: center; margin-top: 20px; }
        .file-input { padding: 10px; border: 2px dashed #ccc; border-radius: 5px; background-color: #f9f9f9; cursor: pointer; transition: background-color 0.3s ease; }
        .file-input:hover { background-color: #e0e0e0; }
    </style>
    <script>
        function onFileSelected() {
            document.getElementById('analyze-btn').style.display = 'inline-block';
        }
        function confirmIngest(hasErrors) {
            if (hasErrors) return confirm("Certaines éléments contiennent des erreurs et les clips associés ne seront pas traités. Voulez-vous continuer ?");
            return true;
        }
        function confirmForce() {
            return confirm("ATTENTION, cette action peut créer des médias en double, ne faire cela que si l'envoi précédent a été correctement nettoyé auparavant !");
        }
        document.addEventListener('DOMContentLoaded', function() {
            Array.from(document.querySelectorAll('th')).forEach(function(th) {
                th.addEventListener('click', function() {
                    var table = th.closest('table');
                    var rows = Array.from(table.querySelectorAll('tr:nth-child(n+2)'));
                    var idx = Array.from(th.parentNode.children).indexOf(th);
                    var asc = !th.asc;
                    rows.sort(function(a, b) {
                        var v1 = a.children[idx].innerText || a.children[idx].textContent;
                        var v2 = b.children[idx].innerText || b.children[idx].textContent;
                        if (v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2)) return asc ? v1 - v2 : v2 - v1;
                        return asc ? v1.localeCompare(v2) : v2.localeCompare(v1);
                    });
                    rows.forEach(function(row) { table.appendChild(row); });
                    th.asc = asc;
                });
            });
        });
    </script>
</head>
<body>
<div class="logo-container" style="display:flex;justify-content:center;margin-top:20px;">
    <img src="{{ url_for('static', filename='images/cliptracker.svg') }}" alt="ClipTracker Logo" style="width:40%;height:auto;">
</div>
<div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-message">
        {% for category,message in messages %}
          <span class="flash-{{category}}">{{message}}</span><br>
        {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    {% if duration_total %}
    <div class="volume">
      Volume de rushes à traiter = {{ duration_total }}<br>
      Temps de traitement nécessaire = {{ duration_process }}<br>
      Total Clips : {{ total_count }}<br>
      Clips audio : {{ audio_count }}<br>
      Clips vidéo : {{ video_count }}
    </div>
    {% endif %}

    <!-- Choix de fichier et analyse -->
    <form method="POST" action="{{ url_for('index') }}" enctype="multipart/form-data" style="text-align:center;margin-top:10px;">
      <div class="file-input-container">
        <input type="file" name="ale_file" class="file-input" onchange="onFileSelected()" required>
      </div>
      <button id="analyze-btn" type="submit" class="btn" style="display:none;">Analyser</button>
    </form>

    {% if results and show_ingest_buttons %}
    <div style="text-align:center;margin-top:20px;">
      <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirmIngest({{has_errors|tojson}})" style="display:inline-block;margin-right:10px;">
        <button class="btn">Envoyer en traitement</button>
      </form>
      <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirmForce()" style="display:inline-block;">
        <input type="hidden" name="force" value="true">
        <button class="btn btn-red">Forcer le traitement</button>
      </form>
    </div>
    {% endif %}

    {% if results %}
    <table>
      <thead><tr><th>Name</th><th>Source File</th><th>Erreur</th></tr></thead>
      <tbody>
      {% for row in results.rows %}
        <tr class="{% if row.error %}error-row{% else %}success-row{% endif %}">
          <td>{{row.Name}}</td><td>{{row['Source File']}}</td><td>{{row.error or 'OK'}}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    {% endif %}
</div>
</body>
</html>
"""

@app.route("/", methods=["GET","POST"])
def index():
    results = None
    duration_total = None
    duration_process = None
    total_count = audio_count = video_count = 0
    has_errors = False
    show_ingest = False

    if request.method == "POST":
        file = request.files.get("ale_file")
        if not file:
            flash("Aucun fichier sélectionné.", "error")
        else:
            ale_contents = file.read().decode("utf-8")
            processor = AleProcessor()
            processor.process_ale_file(ale_contents)
            results = processor.get_results()
            duration_total = processor.calculate_total_duration()
            duration_process = processor.calculate_adjusted_duration()
            for e in processor.global_errors:
                flash(e['message'], 'error')
            processor.duplicate_errors()
            rows = processor.rows
            app.config['ale_rows'] = rows
            has_errors = any(r.get('error') for r in rows)
            total_count = len(rows)
            audio_count = sum(1 for r in rows if r['Source File'].lower().endswith('.wav'))
            video_count = total_count - audio_count
            show_ingest = True

    return render_template_string(template,
        results=results,
        duration_total=duration_total,
        duration_process=duration_process,
        total_count=total_count,
        audio_count=audio_count,
        video_count=video_count,
        has_errors=has_errors,
        show_ingest_buttons=show_ingest
    )

@app.route("/ingest", methods=["POST"])
def ingest():
    rows = app.config.get('ale_rows', [])
    processor = AleProcessor()
    force_flag = request.form.get('force') == 'true'
    for r in rows: r['FORCE_PROCESS'] = 'TRUE' if force_flag else 'FALSE'
    processor.rows = rows
    path = processor.create_csv()
    if path:
        flash(f"Fichier CSV généré avec succès dans : {path}", 'success')
    else:
        flash("Échec de la création du CSV.", 'error')
    # stats
    duration_total = processor.calculate_total_duration()
    duration_process = processor.calculate_adjusted_duration()
    total_count = len(rows)
    audio_count = sum(1 for r in rows if r['Source File'].lower().endswith('.wav'))
    video_count = total_count - audio_count
    results = processor.get_results()
    has_errors = any(r.get('error') for r in rows)
    return render_template_string(template,
        results=results,
        duration_total=duration_total,
        duration_process=duration_process,
        total_count=total_count,
        audio_count=audio_count,
        video_count=video_count,
        has_errors=has_errors,
        show_ingest_buttons=False
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)