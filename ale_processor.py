import os
import re
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

class AleProcessor:
    def __init__(self):
        self.global_errors = []  # Erreurs globales
        self.rows = []  # Toutes les lignes avec erreurs ou non

    def log_global_error(self, message):
        """Ajoute une erreur globale."""
        self.global_errors.append({"level": "ERROR", "message": message})

    def log_row_error(self, row_data, message):
        """Ajoute une erreur à une ligne."""
        if "errors" not in row_data:
            row_data["errors"] = []
        row_data["errors"].append(message)

    def contains_special_characters(self, filename):
        """Vérifie les caractères spéciaux dans un nom de fichier."""
        name, _ = os.path.splitext(filename)
        return bool(re.search(r"[^a-zA-Z0-9=_\-\s]", name))

    def extract_ep_num(self, name):
        """Extrait le numéro d'épisode."""
        match = re.search(r"LGS-(\d{4})-", name)
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
        required_columns = ["Name", "Source File", "Source Path", "Session"]

        column_indices = {col: headers.index(col) if col in headers else None for col in required_columns}

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

            # Validation des champs
            if not all(data[col] for col in required_columns):
                errors.append(f"Données manquantes à la ligne {row_idx}.")
            if self.contains_special_characters(data["Source File"]):
                errors.append("Caractères spéciaux dans le nom du fichier.")
            if not self.extract_ep_num(data["Name"]):
                errors.append("Numéro d'épisode invalide.")

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

    def create_xml(self, row, output_dir):
        """Crée un fichier XML pour une ligne valide."""
        os.makedirs(output_dir, exist_ok=True)
        ep_num = self.extract_ep_num(row["Name"])
        file_name = os.path.splitext(row["Source File"])[0] + ".xml"

        root = ET.Element("Clip")
        ET.SubElement(root, "NAME").text = row["Name"]
        ET.SubElement(root, "EP_NUM").text = ep_num
        ET.SubElement(root, "SRC_FILENAME").text = row["Source File"]
        ET.SubElement(root, "BASE_FOLDERPATH").text = row["Source Path"]
        ET.SubElement(root, "STORAGE_FOLDERPATH").text = self.compute_storage_folderpath(ep_num)
        ET.SubElement(root, "AMF_FOLDERPATH").text = self.compute_amf_folderpath(ep_num)
        ET.SubElement(root, "SESSION").text = row["Session"]

        pretty_xml = parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
        with open(os.path.join(output_dir, file_name), "w", encoding="utf-8") as f:
            f.write(pretty_xml)

    def get_results(self):
        """Retourne les erreurs globales et les lignes traitées."""
        return {"global_errors": self.global_errors, "rows": self.rows}
