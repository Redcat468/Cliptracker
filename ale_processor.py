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
            self.log_global_error(
                "Fichier rtfactor.conf non trouvé, création du fichier avec la valeur par défaut."
            )
            with open("rtfactor.conf", "w", encoding="utf-8") as file:
                file.write("10.0")
            self.rtfactor = 10.0
        except ValueError as e:
            self.log_global_error(f"Erreur lors de la lecture de rtfactor.conf : {e}")
            self.rtfactor = 10.0

    def log_global_error(self, message):
        """Ajoute une erreur globale."""
        self.global_errors.append({"level": "ERROR", "message": message})

    def contains_special_characters(self, filename):
        """Vérifie les caractères spéciaux dans un nom de fichier."""
        name, _ = os.path.splitext(filename)
        return bool(re.search(r"[^a-zA-Z0-9=_\-\s]", name))

    def contains_special_characters_in_path(self, path):
        """Vérifie les caractères spéciaux dans le chemin."""
        return bool(re.search(r"[^a-zA-Z0-9=_\-\s/:\\\\]", path))

    def contains_invalid_characters_in_name(self, name):
        """Vérifie si le champ 'Name' contient des caractères invalides."""
        return bool(re.search(r"[^a-zA-Z0-9\-]", name))

    def extract_ep_num(self, name):
        """Extrait le numéro d'épisode."""
        m = re.search(r"NJ-(\d{4})", name)
        return m.group(1) if m else None

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
        col_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "Column":
                col_idx = i + 1
                break
        if col_idx is None:
            self.log_global_error("Section 'Column' manquante.")
            return
        headers = lines[col_idx].split("\t")
        required = [
            "Name", "Start", "Esta_decorname", "Session",
            "End", "Ingestator", "Ingest_manuel",
            "Duration", "Source File", "Source Path"
        ]
        if not all(c in headers for c in required):
            self.log_global_error("Colonnes manquantes dans le fichier ALE.")
            return

        essential = ["Name", "Source File", "Source Path", "Session", "Duration"]
        col_idx_map = {c: headers.index(c) for c in essential}
        idx_ing = headers.index("Ingestator") if "Ingestator" in headers else None
        idx_man = headers.index("Ingest_manuel") if "Ingest_manuel" in headers else None

        data_start = None
        if "Data" in lines:
            data_start = lines.index("Data") + 1
        if data_start is None:
            self.log_global_error("Section 'Data' manquante.")
            return

        for r_idx, line in enumerate(lines[data_start:], start=data_start+1):
            cols = line.split("\t")
            data = {c: cols[col_idx_map[c]] if col_idx_map[c] < len(cols) else "" for c in essential}
            errors = []
            # Manquantes
            missing = [c for c in essential if not data[c]]
            if missing:
                errors.append(f"Données manquantes ({', '.join(missing)}) à la ligne {r_idx}.")
            # Spéciaux
            if self.contains_special_characters(data["Source File"]):
                errors.append("Caractères spéciaux dans le nom du fichier.")
            if self.contains_special_characters_in_path(data["Source Path"]):
                errors.append("Caractères spéciaux dans le chemin du fichier.")
            # Odio
            if "Odio" in data["Name"] and not data["Source File"].lower().endswith(".wav"):
                errors.append("Verifier le nommage car cela semble ne pas etre un son")
            # ESTA_DECORNAME
            esta = ""
            if "Esta_decorname" in headers:
                i_decor = headers.index("Esta_decorname")
                raw = cols[i_decor] if i_decor < len(cols) else ""
                esta = re.sub(r"[^A-Z-]", "", raw.upper())
            # Name / EP
            if not esta:
                if self.contains_invalid_characters_in_name(data["Name"]):
                    errors.append("Caractère invalide dans la colonne 'Name'.")
                if not self.extract_ep_num(data["Name"]):
                    errors.append("Numéro d'épisode invalide dans 'Name'.")
                pos = data["Name"].find("NJ-")
                if pos != -1:
                    seq = data["Name"][pos+3:pos+9]
                    if not seq.isdigit():
                        errors.append("Vérifiez le nommage EPISODE SEQUENCE")
                else:
                    errors.append("Vérifiez le nommage EPISODE SEQUENCE")
            # Session
            sess = data.get("Session", "")
            if not re.match(r"^[0-9]{6}_EQ[1-4]_(?:AM|PM)$", sess):
                errors.append(f"La session semble mal nommée ({sess})")
            # Fields add
            data["Fullpath"] = os.path.join(data["Source Path"], data["Source File"])
            data["Duration"] = data.get("Duration", "")
            ingest_man = "FALSE"
            if idx_man is not None and cols[idx_man] == "1":
                ingest_man = "TRUE"
            ingestator = cols[idx_ing] if idx_ing is not None and idx_ing < len(cols) else ""
            data["ESTA_DECORNAME"] = esta
            data["INGEST_MANUEL"] = ingest_man
            data["INGESTATOR"] = ingestator
            data["errors"] = errors
            self.rows.append(data)

        # Fusionner toutes les erreurs par ligne
        self.duplicate_errors()

    def duplicate_errors(self):
        """Combine toutes erreurs sur chaque ligne en un seul champ."""
        new_rows = []
        for row in self.rows:
            combined = " |  ".join(row.get("errors", []))
            new_row = row.copy()
            new_row["error"] = combined
            new_rows.append(new_row)
        # Trier : erreurs en premier
        self.rows = sorted(new_rows, key=lambda x: bool(x["error"]), reverse=True)

    def create_csv(self):
        try:
            with open("out_folder.ini", "r", encoding="utf-8") as f:
                out_dir = f.readline().strip()
                if not out_dir:
                    raise ValueError("Chemin de sortie vide dans 'out_folder.ini' !")
        except Exception as e:
            print(f"ERREUR: {e}")
            return None
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"output_{ts}.csv")
        if not self.rows:
            print("Aucun rush à enregistrer.")
            return None
        headers = list(self.rows[0].keys())
        if "Session" in headers:
            if "FORCE_PROCESS" in headers:
                headers.remove("FORCE_PROCESS")
            idx = headers.index("Session")
            headers.insert(idx+1, "FORCE_PROCESS")
        else:
            headers.append("FORCE_PROCESS")
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.rows)
            return path
        except Exception as e:
            print(f"ERREUR CSV: {e}")
            return None

    def calculate_total_duration(self):
        total_frames = 0
        fps = 25
        for row in self.rows:
            sf = row.get("Source File", "").lower()
            dur = row.get("Duration", "")
            if sf.endswith(".wav"): continue
            if re.match(r"^\d{2}:\d{2}:\d{2}:\d{2}$", dur):
                hh, mm, ss, ff = map(int, dur.split(':'))
                total_frames += (hh*3600 + mm*60 + ss)*fps + ff
        sec, _ = divmod(total_frames, fps)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02} heures {m:02} min {s:02} secondes"

    def calculate_adjusted_duration(self):
        td = self.calculate_total_duration()
        secs = self._convert_duration_to_seconds(td)
        adj = secs / self.rtfactor
        h, rem = divmod(int(adj), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02} heures {m:02} min {s:02} secondes"

    def _convert_duration_to_seconds(self, duration):
        m = re.match(r"(\d{2}) heures (\d{2}) min (\d{2}) secondes", duration)
        if m:
            hh, mm, ss = map(int, m.groups())
            return hh*3600 + mm*60 + ss
        return 0

    def get_results(self):
        return {"global_errors": self.global_errors, "rows": self.rows}
