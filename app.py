from flask import Flask, request, render_template_string, redirect, url_for, flash
from ale_processor import AleProcessor

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
        /* Styles généraux */
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            margin: 20px auto;
            padding: 20px;
            max-width: 1000px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        h3 {
            text-align: center;
            margin-bottom: 20px;
            color: #2c3e50;
        }

        /* Messages flash */
        .flash-message {
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 5px;
            font-weight: bold;
        }
        .flash-error {
            background-color: #ffebee;
            color: #c62828;
        }
        .flash-success {
            background-color: #e8f5e9;
            color: #2e7d32;
        }

        /* Formulaire et boutons */
        .form-container {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            margin-bottom: 20px;
        }
        .file-input {
            margin-bottom: 20px;
            text-align: center;
        }
        input[type="file"] {
            display: inline-block;
            font-size: 16px;
            padding: 10px;
        }
        .btn-container {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 10px;
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            font-size: 16px;
            color: #fff;
            background-color: #4CAF50;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        .btn:hover {
            background-color: #45a049;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        }
        .btn-red {
            background-color: #e74c3c;
        }
        .btn-red:hover {
            background-color: #c0392b;
        }
        .btn-blue {
            background-color: #3498db;
        }
        .btn-blue:hover {
            background-color: #2980b9;
        }

        /* Tableau */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: #fff;
            border-radius: 5px;
            overflow: hidden;
        }
        th, td {
            padding: 12px;
            border: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: #fff;
            font-weight: bold;
        }
        .error-row { background-color: #ffebee; color: #c62828; }
        .success-row { background-color: #e8f5e9; color: #2e7d32; }
    </style>

</head>
<body>
<div class="container">
    <h3>Analyseur ALE</h3>

    <!-- Messages flash -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash-message {% if category == 'error' %}flash-error{% elif category == 'success' %}flash-success{% endif %}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <!-- Formulaire d'upload -->
    <div class="form-container">
        <div class="file-input">
            <form method="POST" enctype="multipart/form-data">
                <input type="file" name="ale_file" required>
                <div class="btn-container">
                    <button type="submit" class="btn btn-blue">Analyser</button>
                </div>
            </form>
        </div>
    </div>

    {% if results %}
        <!-- Bouton d'Ingest -->
        <div class="btn-container">
            <form method="POST" action="{{ url_for('ingest') }}" onsubmit="return confirm('Voulez-vous procéder à l\'ingest ?')">
                <button type="submit" class="btn">Ingest</button>
            </form>
        </div>

        <!-- Tableau des résultats -->
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
                        <td data-label="Name">{{ row.Name }}</td>
                        <td data-label="Source File">{{ row['Source File'] }}</td>
                        <td data-label="Erreur">{{ row.error if row.error else 'OK' }}</td>
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
    has_errors = False
    if request.method == "POST":
        file = request.files.get("ale_file")
        if not file:
            flash("Aucun fichier sélectionné.", "error")
        else:
            try:
                ale_contents = file.read().decode("utf-8")
                if "Column" not in ale_contents or "Data" not in ale_contents:
                    raise ValueError("Fichier ALE invalide : sections manquantes.")

                processor = AleProcessor()
                processor.process_ale_file(ale_contents)
                results = processor.get_results()

                if processor.global_errors:
                    for error in processor.global_errors:
                        flash(error["message"], "error")

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
