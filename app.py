from flask import Flask, request, render_template_string, redirect, url_for, flash, get_flashed_messages
from ale_processor import AleProcessor
import re
import os

app = Flask(__name__)
app.secret_key = "secret_key"

# Template HTML
template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analyseur ALE</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; color: #333; }
        .container { margin: 20px auto; padding: 20px; max-width: 1000px; background: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); }
        .volume { text-align: center; font-weight: bold; color: #2e7d32; margin-bottom: 20px; }
        .flash-message { padding: 10px; margin-bottom: 20px; border-radius: 5px; font-weight: bold; }
        .flash-error { background-color: #ffebee; color: #c62828; }
        .flash-success { background-color: #e8f5e9; color: #2e7d32; }
        .btn { display: inline-block; padding: 10px 20px; font-size: 16px; color: #fff; background-color: #4CAF50; border: none; border-radius: 5px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #fff; }
        th, td { padding: 12px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #4CAF50; color: #fff; }
        .error-row { background-color: #ffebee; color: #c62828; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
    </style>
    <script>
        function confirmIngest(hasErrors) {
            if (hasErrors) {
                return confirm("Certaines elements contiennent des erreurs et les clips associés ne seront pas traités. Voulez-vous continuer ?");
            }
            return true;
        }
    </script>
</head>
<body>
<div class="logo-container" style="display: flex; justify-content: center;">
    <img src="{{ url_for('static', filename='images/cliptracker.svg') }}" alt="ClipTracker Logo" style="width: 50%; height: auto;">
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
        <input type="file" name="ale_file" required>
        <div style="text-align: center; margin-top: 10px;">
            <button type="submit" class="btn">Analyser</button>
        </div>
    </form>

    {% if results %}
        <!-- Bouton d'Ingest avec confirmation -->
        <div style="text-align: center; margin-top: 20px;"> <!-- Ajout d'espace entre les boutons -->
            <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirmIngest({{ has_errors|tojson }})">
                <button type="submit" class="btn">Envoyer à Vantage</button>
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
    output_dir = "output_xml"
    processor = AleProcessor()
    ale_generated = False
    for row in rows:
        if not row.get("error"):
            processor.create_xml(row, output_dir)
            ale_generated = True
    if ale_generated:
        from datetime import datetime

        current_time = datetime.now().strftime("%H:%M:%S")
        flash(f"Fichiers envoyés en traitement avec succès !", "success")
    else:
        flash("Aucun fichier envoyé", "error")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
