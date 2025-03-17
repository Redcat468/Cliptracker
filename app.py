from flask import Flask, request, render_template_string, redirect, url_for, flash, get_flashed_messages
from ale_processor import AleProcessor
import re
import sys
import os
import threading
import webbrowser
from pystray import Icon, MenuItem, Menu
from PIL import Image
from flask import send_file


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
        .container { margin: 20px auto; padding: 20px; max-width: 1000px; background: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); }
        .volume { text-align: center; font-weight: bold; color: #2e7d32; margin-bottom: 20px; }
        .flash-message { padding: 10px; margin-bottom: 20px; border-radius: 5px; font-weight: bold; }
        .flash-error { background-color: #ffebee; color: #c62828; }
        .flash-success { background-color: #e8f5e9; color: #2e7d32; }
        .btn { 
            display: inline-block; 
            padding: 10px 20px; 
            font-size: 16px; 
            color: #fff; 
            background-color: #4CAF50; 
            border: none; 
            border-radius: 15px; 
            cursor: pointer; 
            box-shadow: 0 2px 2px rgba(0, 0, 0, 0.3); 
            transition: background-color 0.2s ease, transform 0.2s ease; 
        }
        .btn:hover { 
            background-color: #45a049; 
            transform: translateY(-2px); 
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 20px; 
            background: #fff; 
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); 
            border-radius: 8px; 
            overflow: hidden; 
        }
        th, td { 
            padding: 12px; 
            border-bottom: 1px solid #ddd; 
            text-align: left; 
            transition: background-color 0.3s ease; 
        }
        th { 
            background-color: #4CAF50; 
            color: #fff; 
            cursor: pointer; 
            position: sticky; 
            top: 0; 
            z-index: 1; 
        }
        th:hover { 
            background-color: #45a049; 
        }
        tr:hover td { 
            background-color: #f1f1f1; 
        }
        .error-row { background-color: #ffebee; color: #c62828; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
        .file-input-container { display: flex; justify-content: center; margin-top: 20px; }
        .file-input { padding: 10px; border: 2px dashed #ccc; border-radius: 5px; background-color: #f9f9f9; cursor: pointer; transition: background-color 0.3s ease; }
        .file-input:hover { background-color: #e0e0e0; }
    </style>
    <script>
        function confirmIngest(hasErrors) {
            if (hasErrors) {
                return confirm("Certaines elements contiennent des erreurs et les clips associés ne seront pas traités. Voulez-vous continuer ?");
            }
            return true;
        }

        document.addEventListener('DOMContentLoaded', function() {
            const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
            const comparer = (idx, asc) => (a, b) => ((v1, v2) => 
                v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
            )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));

            document.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {
                const table = th.closest('table');
                Array.from(table.querySelectorAll('tr:nth-child(n+2)'))
                    .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
                    .forEach(tr => table.appendChild(tr) );
            })));
        });
    </script>
</head>
<body>
<div class="logo-container" style="display: flex; justify-content: center; margin-top: 20px;">
    <img src="{{ url_for('static', filename='images/cliptracker.svg') }}" alt="ClipTracker Logo" style="width: 40%; height: auto;">
</div>
<div class="container">
    <!-- Affichage des messages flash -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-message">
                {% for category, message in messages %}
                    <span class="{{ 'flash-' + category }}">{{ message }}</span><br>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Volume de rushes -->
    {% if duration_total %}
        <div class="volume">
            Volume de rushes à traiter = {{ duration_total }}
            <br>
            Temps de traitement nécéssaire = {{ duration_process }}
        </div>
    {% endif %}

    <!-- Formulaire -->
    <form method="POST" enctype="multipart/form-data">
        <div class="file-input-container">
            <input type="file" name="ale_file" class="file-input" required>
        </div>
        <div style="text-align: center; margin-top: 10px;">
            <button type="submit" class="btn">Analyser</button>
        </div>
    </form>

    {% if results %}
        <!-- Bouton d'Ingest avec confirmation -->
        <div style="text-align: center; margin-top: 20px;"> <!-- Ajout d'espace entre les boutons -->
            <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirmIngest({{ has_errors|tojson }})">
                <button type="submit" class="btn">Envoyer en traitement</button>
            </form>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Source File</th>
                    <th>Erreur</th>
                </tr>
            </thead>
            <tbody>
                {% for row in results.rows %}
                    <tr class="{% if row.error %}error-row{% else %}success-row{% endif %}">
                        <td>{{ row.Name }}</td>
                        <td>{{ row['Source File'] }}</td>
                        <td>{{ row.error if row.error else 'OK' }}</td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    {% endif %}
</div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    duration_total = None
    duration_process = None
    has_errors = False

    if request.method == "POST":
        file = request.files.get("ale_file")
        if not file:
            flash("Aucun fichier sélectionné.", "error")
        else:
            try:
                ale_contents = file.read().decode("utf-8")
                processor = AleProcessor()
                processor.process_ale_file(ale_contents)
                results = processor.get_results()

                # Calcul de la durée totale
                duration_total = processor.calculate_total_duration()
                duration_process = processor.calculate_adjusted_duration()

                # Vérification des erreurs globales
                if processor.global_errors:
                    for error in processor.global_errors:
                        flash(error["message"], "error")

                # Dupliquer les lignes avec erreurs multiples
                processor.duplicate_errors()
                app.config["ale_rows"] = processor.rows
                has_errors = any(row.get("error") for row in processor.rows)

            except Exception as e:
                flash(f"Erreur : {str(e)}", "error")

    return render_template_string(template, results=results, duration_total=duration_total, duration_process=duration_process, has_errors=has_errors)

@app.route("/ingest", methods=["POST"])
def ingest():
    rows = app.config.get("ale_rows", [])
    processor = AleProcessor()

    print(f"📊 Nombre de lignes reçues par /ingest : {len(rows)}")

    if rows:
        processor.rows = rows
        csv_path = processor.create_csv()

        if csv_path:
            flash(f"Fichier CSV généré avec succès dans : {csv_path}", "success")
            print(f"🎯 CSV sauvegardé à : {csv_path}")
        else:
            flash("⚠️ Échec de la création du CSV.", "error")
            print("⚠️ Échec de la création du CSV.")

    else:
        flash("Aucune donnée disponible pour générer le CSV.", "error")
        print("⚠️ Aucun rush disponible pour la génération du CSV.")

    return redirect(url_for("index"))

def run_server():
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == "__main__":
    run_server()

    
