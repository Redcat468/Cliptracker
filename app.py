from flask import Flask, request, render_template_string, redirect, url_for, flash
from ale_processor import AleProcessor
import re

app = Flask(__name__)
app.secret_key = "secret_key"


def sum_durations(rows):
    total_frames = 0
    fps = 25  # Assumption : 25 images par seconde

    for row in rows:
        duration = row.get("Duration", "").strip()  # Durée au format HH:MM:SS:II
        source_file = row.get("Source File", "").strip()

        # Ignorer les fichiers .WAV
        if source_file.lower().endswith(".wav"):
            continue

        # Vérifier si la durée est au bon format
        if duration and re.match(r"^\d{2}:\d{2}:\d{2}:\d{2}$", duration):
            hh, mm, ss, ff = map(int, duration.split(":"))
            total_frames += (hh * 3600 + mm * 60 + ss) * fps + ff

    # Conversion des frames en HH:MM:SS
    total_seconds, frames = divmod(total_frames, fps)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02} heures {minutes:02} min {seconds:02} secondes"


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
        h3 { text-align: center; color: #2c3e50; }
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
</head>
<body>
<div class="container">
    <h3>Analyseur ALE</h3>

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

            except Exception as e:
                flash(f"Erreur : {str(e)}", "error")

    return render_template_string(template, results=results, duration_total=duration_total, duration_process=duration_process)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
