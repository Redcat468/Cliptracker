from flask import Flask, request, render_template_string, redirect, url_for, flash, get_flashed_messages
from ale_processor import AleProcessor

app = Flask(__name__)
app.secret_key = "secret_key"

# Template HTML avec Materialize CSS
template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analyseur ALE</title>
    <!-- Materialize CSS -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css" rel="stylesheet">
    <style>
        .error-row { background-color: #ffebee; color: #c62828; font-weight: bold; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
        .small-text { font-size: 0.9em; word-wrap: break-word; white-space: pre-line; }
        .table-container { margin-top: 20px; }
    </style>
    <script>
        function confirmIngest(hasErrors) {
            if (hasErrors) {
                return confirm("Certaines lignes contiennent des erreurs. Voulez-vous continuer ?");
            }
            return true;
        }
    </script>
</head>
<body class="grey lighten-4">

<div class="container">
    <h3 class="center-align">Analyseur ALE</h3>

    <!-- Affichage des messages flash -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="card-panel red lighten-4">
                {% for category, message in messages %}
                    <span class="red-text text-darken-4">{{ message }}</span><br>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <!-- Formulaire d'upload -->
    <form method="POST" enctype="multipart/form-data" class="card-panel">
        <div class="file-field input-field">
            <div class="btn">
                <span>Fichier ALE</span>
                <input type="file" name="ale_file" required>
            </div>
            <div class="file-path-wrapper">
                <input class="file-path validate" type="text" placeholder="Téléchargez un fichier ALE">
            </div>
        </div>
        <button type="submit" class="waves-effect waves-light btn">Analyser</button>
    </form>

    {% if results %}
        <!-- Bouton d'Ingest avec confirmation -->
        <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirmIngest({{ has_errors|tojson }})">
            <button type="submit" class="waves-effect waves-light btn green">Ingest</button>
        </form>

        <!-- Tableau des résultats -->
        <div class="table-container">
            <table class="highlight responsive-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Source File</th>
                        <th>Source Path</th>
                        <th>Erreur</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in results.rows %}
                        <tr class="{% if row.error %}error-row{% else %}success-row{% endif %}">
                            <td style="white-space: nowrap;">{{ row.Name }}</td>
                            <td>{{ row['Source File'] }}</td>
                            <td class="small-text">{{ row['Source Path'] }}</td>
                            <td>{{ row.error if row.error else 'OK' }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% endif %}
</div>

<!-- Materialize JS -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js"></script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    has_errors = False
    if request.method == "POST":
        file = request.files.get("ale_file")  # Récupérer le fichier uploadé
        if not file:
            flash("Aucun fichier sélectionné.", "error")
        else:
            try:
                # Tentative de décodage du fichier
                ale_contents = file.read().decode("utf-8")
                if "Column" not in ale_contents or "Data" not in ale_contents:
                    raise ValueError("Fichier ALE invalide : sections manquantes.")

                # Traiter le fichier ALE
                processor = AleProcessor()
                processor.process_ale_file(ale_contents)
                results = processor.get_results()

                # Vérification des erreurs globales
                if processor.global_errors:
                    for error in processor.global_errors:
                        flash(error["message"], "error")

                # Dupliquer les lignes avec erreurs multiples
                processor.duplicate_errors()
                app.config["ale_rows"] = processor.rows
                has_errors = any(row.get("error") for row in processor.rows)

            except (UnicodeDecodeError, ValueError) as e:
                flash("Fichier ALE invalide. Veuillez vérifier le format.", "error")
            except Exception as e:
                flash(f"Une erreur est survenue : {str(e)}", "error")

    return render_template_string(template, results=results, has_errors=has_errors)

@app.route("/ingest", methods=["POST"])
def ingest():
    rows = app.config.get("ale_rows", [])
    output_dir = "output_xml"
    processor = AleProcessor()
    for row in rows:
        if not row.get("error"):
            processor.create_xml(row, output_dir)
    flash("XML générés avec succès !", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
