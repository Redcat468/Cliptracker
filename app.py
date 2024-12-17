from flask import Flask, request, render_template_string, redirect, url_for, flash
from ale_processor import AleProcessor

app = Flask(__name__)
app.secret_key = "secret_key"

# Template HTML avec Materialize CSS pour un style moderne
template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analyseur ALE</title>
    <!-- Materialize CSS -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css" rel="stylesheet">
    <script>
        function confirmIngest(hasErrors) {
            if (hasErrors) {
                return confirm("Certaines lignes contiennent des erreurs. Voulez-vous continuer ?");
            }
            return true;
        }
    </script>
    <style>
        .error-row { background-color: #ffebee; color: #c62828; font-weight: bold; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
        .table-container { margin-top: 20px; }
    </style>
</head>
<body class="grey lighten-4">

<div class="container">
    <h3 class="center-align">Analyseur ALE</h3>
    
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
        {% if results.global_errors %}
            <div class="card-panel red lighten-4">
                <span class="red-text text-darken-4">
                    <strong>Erreurs globales :</strong>
                    <ul>
                        {% for err in results.global_errors %}
                            <li>{{ err.message }}</li>
                        {% endfor %}
                    </ul>
                </span>
            </div>
        {% endif %}

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
                            <td>{{ row.Name }}</td>
                            <td>{{ row['Source File'] }}</td>
                            <td>{{ row['Source Path'] }}</td>
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
        file = request.files["ale_file"]
        ale_contents = file.read().decode("utf-8")
        processor = AleProcessor()
        processor.process_ale_file(ale_contents)
        results = processor.get_results()
        processor.duplicate_errors()  # Duplication des lignes avec erreurs multiples
        app.config["ale_rows"] = processor.rows
        has_errors = any(row.get("error") for row in processor.rows)
    return render_template_string(template, results=results, has_errors=has_errors)

@app.route("/ingest", methods=["POST"])
def ingest():
    rows = app.config.get("ale_rows", [])
    output_dir = "output_xml"
    processor = AleProcessor()
    for row in rows:
        if not row.get("error"):
            processor.create_xml(row, output_dir)
    flash("XML générés avec succès !")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
