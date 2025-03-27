import os
import re
import csv
from datetime import datetime

class AleProcessor:
    def __init__(self):
        self.global_errors = []  # Erreurs globales
        self.rows = []  # Toutes les lignes avec erreurs ou non
        # Lire la valeur de rtfactor à partir du fichier rtfactor.conf
        try:
            with open("rtfactor.conf", "r", encoding="utf-8") as file:
                line = file.readline().strip()
                self.rtfactor = float(line.replace('O', '0'))
        except FileNotFoundError:
            self.log_global_error("Fichier rtfactor.conf non trouvé, création du fichier avec la valeur par défaut.")
            with open("rtfactor.conf", "w", encoding="utf-8") as file:
                file.write("10.0")
            self.rtfactor = 10.0
        except ValueError as e:
            self.log_global_error(f"Erreur lors de la lecture de rtfactor.conf : {str(e)}")
            self.rtfactor = 10.0  # Valeur par défaut en cas d'erreur

    def log_global_error(self, message):
        """Ajoute une erreur globale."""
        self.global_errors.append({"level": "ERROR", "message": message})

    def contains_special_characters(self, filename):
        """Vérifie les caractères spéciaux dans un nom de fichier."""
        name, _ = os.path.splitext(filename)
        return bool(re.search(r"[^a-zA-Z0-9=_\-\s]", name))

    def contains_special_characters_in_path(self, path):
        """Vérifie les caractères spéciaux dans le chemin. Autorise /, \\, _, -, :, ., et les espaces"""
        return bool(re.search(r"[^a-zA-Z0-9=_\-\s/:\\\\]", path))

    def contains_invalid_characters_in_name(self, name):
        """Vérifie si le champ 'Name' contient des caractères invalides."""
        return bool(re.search(r"[^a-zA-Z0-9\-]", name))

    def extract_ep_num(self, name):
        """Extrait le numéro d'épisode."""
        match = re.search(r"NJ-(\d{4})", name)
        return match.group(1) if match else None

    def compute_storage_folderpath(self, ep_num):
        """Calcule le chemin de stockage."""
        return f"\\\\facilis\\LGS_RUSHES\\NATIFS\\LGS_EP_{ep_num}\\"

    def compute_amf_folderpath(self, ep_num):
        """Calcule le chemin AMF."""
        group_index = ((int(ep_num) - 1) // 10) + 1
        return f"\\\\nexis\\LGS_MTG_{group_index}\\Avid MediaFiles\\MXF\\EP{ep_num}"

    def process_ale_file(self, ale_contents):
        """Analyse un fichier ALE."""
        
        lines = ale_contents.splitlines()
        column_start_index = None

        for i, line in enumerate(lines):
            if line.strip() == "Column":
                column_start_index = i + 1
                break

        if column_start_index is None:
            self.log_global_error("Section 'Column' manquante.")
            return
        headers = lines[column_start_index].strip().split("\t")
        required_columns = ["Name", "Start", "Esta", "Session", "End", "Ingestator", "Ingest_manuel", "Duration", "Source File", "Source Path"]
        
        # Vérification de la présence de toutes les colonnes requises
        if not all(col in headers for col in required_columns):
            self.log_global_error("Colonnes manquantes dans le fichier ALE.")
            return

        headers = lines[column_start_index].strip().split("\t")
        required_columns = ["Name", "Source File", "Source Path", "Session", "Duration"]
        column_indices = {col: headers.index(col) if col in headers else None for col in required_columns}
        ingestator_idx = headers.index("Ingestator") if "Ingestator" in headers else None
        ingest_manuel_idx = headers.index("Ingest_manuel") if "Ingest_manuel" in headers else None

        if any(idx is None for idx in column_indices.values()):
            self.log_global_error("Colonnes manquantes dans le fichier ALE.")
            return

        data_start_index = lines.index("Data") + 1 if "Data" in lines else None
        if not data_start_index:
            self.log_global_error("Section 'Data' manquante.")
            return

        for row_idx, row in enumerate(lines[data_start_index:], start=data_start_index + 1):
            columns = row.strip().split("\t")
            data = {col: columns[idx] if idx < len(columns) else "" for col, idx in column_indices.items()}
            errors = []

            if not all(data[col] for col in required_columns):
                erreurs = [col for col in required_columns if not data[col]]
                errors.append(f"Données manquantes ({', '.join(erreurs)}) à la ligne {row_idx}.")
            if self.contains_special_characters(data["Source File"]):
                errors.append("Caractères spéciaux dans le nom du fichier.")
            if self.contains_special_characters_in_path(data["Source Path"]):
                errors.append("Caractères spéciaux dans le chemin du fichier.")
            if self.contains_invalid_characters_in_name(data["Name"]):
                errors.append("Caractère invalide dans la colonne 'Name'.")
            if not self.extract_ep_num(data["Name"]):
                errors.append("Numéro d'épisode invalide dans 'Name'.")
            
            data["Fullpath"] = os.path.join(data["Source Path"], data["Source File"])

            # Récupérer la durée
            duration_value = data.get("Duration", "")

            # Traitement propre de la colonne ESTA_DECORNAME
            esta_decorname = ""
            if "ESTA_DECORNAME" in headers:
                esta_decorname_idx = headers.index("ESTA_DECORNAME")
                raw_value = columns[esta_decorname_idx] if esta_decorname_idx < len(columns) else ""
                # Nettoyer : uniquement lettres majuscules sans caractère spécial ni espace
                esta_decorname = re.sub(r"[^A-Z]", "", raw_value.upper())


            # Récupérer les valeurs des colonnes Ingest_manuel et Ingestator
            ingest_manuel_value = "FALSE"  # Par défaut
            if ingest_manuel_idx is not None and columns[ingest_manuel_idx] == "1":
                ingest_manuel_value = "TRUE"

            ingestator_value = "FALSE"  # Par défaut
            if ingestator_idx is not None and columns[ingestator_idx] == "1":
                ingestator_value = "TRUE"

            data["ESTA_DECORNAME"] = esta_decorname
            data["Duration"] = duration_value
            data["INGEST_MANUEL"] = ingest_manuel_value
            data["INGESTATOR"] = ingestator_value

            data["errors"] = errors
            self.rows.append(data)

        self.duplicate_errors()

    def duplicate_errors(self):
        """Duplique les lignes avec plusieurs erreurs pour chaque erreur individuelle."""
        new_rows = []
        for row in self.rows:
            errors = row.get("errors", [])
            if errors:
                for error in errors:
                    new_row = row.copy()
                    new_row["error"] = error
                    new_rows.append(new_row)
            else:
                row["error"] = ""
                new_rows.append(row)
        self.rows = sorted(new_rows, key=lambda x: bool(x.get("error")), reverse=True)

    def create_csv(self):
        """Crée un fichier CSV avec un timestamp dans le nom et l'enregistre dans le dossier défini par 'out_folder.ini'."""
        
        # Lire le chemin de sortie depuis out_folder.ini
        try:
            with open("out_folder.ini", "r", encoding="utf-8") as file:
                output_dir = file.readline().strip()
                if not output_dir:
                    raise ValueError("Chemin de sortie vide dans 'out_folder.ini' !")
        except FileNotFoundError:
            print(" ERREUR : Le fichier 'out_folder.ini' est introuvable !")
            return None
        except ValueError as e:
            print(f"ERREUR : {e}")
            return None

        # Vérifier et créer le dossier de sortie s'il n'existe pas
        if not os.path.exists(output_dir):
            print(f"Création du dossier de sortie : {output_dir}")
            os.makedirs(output_dir, exist_ok=True)

        # Ajouter un timestamp au nom du CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format YYYYMMDD_HHMMSS
        output_file = f"output_{timestamp}.csv"
        output_path = os.path.join(output_dir, output_file)

        # Vérifier que les données existent
        if not self.rows:
            print("Aucun rush à enregistrer dans le CSV.")
            return None

        # Récupérer les headers depuis la première ligne
        headers = list(self.rows[0].keys())
        print(f"Colonnes du CSV avant réorganisation : {headers}")

        # Réorganiser les colonnes pour que FORCE_PROCESS apparaisse après Session
        if "Session" in headers:
            if "FORCE_PROCESS" in headers:
                headers.remove("FORCE_PROCESS")
            session_index = headers.index("Session")
            headers.insert(session_index + 1, "FORCE_PROCESS")
        else:
            if "FORCE_PROCESS" not in headers:
                headers.append("FORCE_PROCESS")

        print(f"Colonnes du CSV après réorganisation : {headers}")

        # Écriture du fichier CSV
        try:
            with open(output_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.rows)

            print(f"CSV écrit avec succès : {output_path}")
            return output_path

        except Exception as e:
            print(f"ERREUR lors de la création du CSV : {e}")
            return None

    # Ajout de la méthode calculate_total_duration
    def calculate_total_duration(self):
        """Additionne les durées des fichiers non .WAV et retourne un format lisible."""
        total_frames = 0
        fps = 25  # Images par seconde (frames per second)


        for row in self.rows:
            source_file = row.get("Source File", "")
            duration = row.get("Duration", "")

            # Ignorer les fichiers .WAV
            if source_file.lower().endswith(".wav"):
                continue

            # Vérifier si la durée est au bon format HH:MM:SS:FF
            if duration and re.match(r"^\d{2}:\d{2}:\d{2}:\d{2}$", duration):
                hh, mm, ss, ff = map(int, duration.split(":"))
                total_frames += (hh * 3600 + mm * 60 + ss) * fps + ff

        # Conversion des frames en HH:MM:SS
        total_seconds, remaining_frames = divmod(total_frames, fps)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02} heures {minutes:02} min {seconds:02} secondes"

    def calculate_adjusted_duration(self):
        """Calcule la durée ajustée en divisant la durée totale par le facteur rtfactor."""
        total_duration = self.calculate_total_duration()
        total_seconds = self._convert_duration_to_seconds(total_duration)
        
        # Diviser par le facteur rtfactor
        adjusted_seconds = total_seconds / self.rtfactor
        
        # Conversion des secondes ajustées en HH:MM:SS
        hours, remainder = divmod(int(adjusted_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{hours:02} heures {minutes:02} min {seconds:02} secondes"

    def _convert_duration_to_seconds(self, duration):
        """Convertit une durée au format 'HH heures MM min SS secondes' en secondes."""
        match = re.match(r"(\d{2}) heures (\d{2}) min (\d{2}) secondes", duration)
        if match:
            hh, mm, ss = map(int, match.groups())
            return hh * 3600 + mm * 60 + ss
        return 0  # Retourne 0 si la conversion échoue


    def get_results(self):
        """Retourne les erreurs globales et les lignes traitées."""
        return {"global_errors": self.global_errors, "rows": self.rows}
