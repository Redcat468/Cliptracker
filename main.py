import os
import argparse
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
import re
import traceback
from datetime import datetime

def log_message(log_file, level, message, context=None, terminal_fallback=False):
    """Write a message (ERROR/WARNING) to the log file with improved formatting and timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n--- {level} ---\nTimestamp: {timestamp}\n{message}\n"

    if context:
        log_entry += "Context:\n"
        for key, value in context.items():
            log_entry += f"{key}: {value}\n"
        log_entry += "\n"

    if terminal_fallback:
        print(log_entry)
    else:
        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(log_entry + "\n")
        except Exception as e:
            print(f"Failed to write to log file '{log_file}': {str(e)}")
            print(log_entry)

def extract_ep_num(name):
    """Extract the EP_NUM from the 'Name' field using regex."""
    match = re.search(r"LGS-(\d{4})-", name)  # Ensure EP_NUM is exactly 4 digits TEST
    return match.group(1) if match else None

def compute_amf_folderpath(ep_num):
    """Compute the AMF_FOLDERPATH based on the EP_NUM."""
    group_index = ((int(ep_num) - 1) // 10) + 1  # Calculate the group index (1-based)
    return f"\\\\nexis\\LGS_MTG_{group_index}\\Avid MediaFiles\\MXF\\EP{ep_num}"

def compute_storage_folderpath(ep_num):
    """Compute the STORAGE_FOLDERPATH based on the EP_NUM."""
    return f"\\\\facilis\\LGS_RUSHES\\NATIFS\\LGS_EP_{ep_num}\\"

def extract_file_name(source_file):
    """Extract the file name from the source file path."""
    return os.path.basename(source_file) if source_file else None

def contains_special_characters(filename):
    """Check if the filename contains characters other than a-z, A-Z, 0-9, '=', '-', '_', or space. 
    Do not count the dot in the file extension as an invalid character."""
    # Split the filename to separate the extension
    name, ext = os.path.splitext(filename)
    # Check for invalid characters in the name part only
    return bool(re.search(r"[^a-zA-Z0-9=_\-\s]", name))

def process_ale_file(ale_path, output_dir, log_file):
    # Ensure the output directory exists
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        log_message(
            log_file,
            "ERROR",
            f"Failed to create output directory '{output_dir}': {str(e)}",
            context={"Output Directory": output_dir},
            terminal_fallback=True
        )
        return

    if not os.path.isfile(ale_path):
        log_message(
            log_file,
            "ERROR",
            "Input file does not exist.",
            context={"File": ale_path},
            terminal_fallback=True
        )
        return

    try:
        with open(ale_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except Exception as e:
        log_message(
            log_file,
            "ERROR",
            f"Failed to read file: {str(e)}",
            context={"File": ale_path},
            terminal_fallback=True
        )
        return

    column_start_index = None
    for i, line in enumerate(lines):
        if line.strip() == "Column":
            column_start_index = i + 1
            break

    if column_start_index is None:
        log_message(
            log_file,
            "ERROR",
            "Missing 'Column' section in ALE file.",
            context={"File": ale_path},
            terminal_fallback=True
        )
        return

    headers = lines[column_start_index].strip().split("\t")

    if "Data" not in [line.strip() for line in lines]:
        log_message(
            log_file,
            "ERROR",
            "Missing 'Data' section in ALE file.",
            context={"File": ale_path},
            terminal_fallback=True
        )
        return

    data_start_index = None
    for i, line in enumerate(lines):
        if line.strip() == "Data":
            data_start_index = i + 1
            break

    required_columns = ["Name", "Source File", "Source Path", "Session"]
    column_indices = {col: headers.index(col) if col in headers else None for col in required_columns}

    for col, idx in column_indices.items():
        if idx is None:
            log_message(
                log_file,
                "ERROR",
                f"Missing required column: {col}",
                context={"File": ale_path},
                terminal_fallback=True
            )
            return

    esta_idx = headers.index("Esta") if "Esta" in headers else None

    for row_idx, row in enumerate(lines[data_start_index:], start=data_start_index + 1):
        try:
            columns = row.strip().split("\t")
            if len(columns) <= max(column_indices.values()):
                log_message(
                    log_file,
                    "ERROR",
                    f"Incomplete data row at line {row_idx}.",
                    context={"File": ale_path, "Row Content": row.strip()},
                    terminal_fallback=False
                )
                continue

            data = {col: columns[idx] if idx is not None and idx < len(columns) else "" for col, idx in column_indices.items()}
            esta = columns[esta_idx] if esta_idx is not None and esta_idx < len(columns) else "0"
            ep_num = extract_ep_num(data["Name"])
            file_name = extract_file_name(data["Source File"])

            # Check for special characters in SRC_FILENAME
            if contains_special_characters(data["Source File"]):
                log_message(
                    log_file,
                    "ERROR",
                    f"Source file name contains special characters at line {row_idx}.",
                    context={
                        "File": ale_path,
                        "Name": data["Name"],
                        "Source File": data["Source File"],
                        "Source Path": data["Source Path"]
                    },
                    terminal_fallback=False
                )

            if not all(data[col] for col in required_columns):
                log_message(
                    log_file,
                    "ERROR",
                    f"Missing data in required columns at line {row_idx}.",
                    context={
                        "File": ale_path,
                        "Name": data["Name"],
                        "Source File": data["Source File"],
                        "Source Path": data["Source Path"]
                    },
                    terminal_fallback=False
                )
                continue

            if ep_num is None:
                log_message(
                    log_file,
                    "ERROR",
                    f"Invalid EP_NUM in 'Name' field at line {row_idx}.",
                    context={
                        "File": ale_path,
                        "Name": data["Name"],
                        "Source File": data["Source File"],
                        "Source Path": data["Source Path"]
                    },
                    terminal_fallback=False
                )
                continue

            storage_folderpath = compute_storage_folderpath(ep_num)
            amf_folderpath = compute_amf_folderpath(ep_num)
            esta_value = "TRUE" if esta == "1" else "FALSE"

            root = ET.Element("Clip")
            ET.SubElement(root, "NAME").text = data["Name"]
            ET.SubElement(root, "EP_NUM").text = ep_num
            ET.SubElement(root, "SRC_FILENAME").text = data["Source File"]
            ET.SubElement(root, "FILE_NAME").text = file_name
            ET.SubElement(root, "BASE_FOLDERPATH").text = data["Source Path"]
            ET.SubElement(root, "STORAGE_FOLDERPATH").text = storage_folderpath
            ET.SubElement(root, "AMF_FOLDERPATH").text = amf_folderpath
            ET.SubElement(root, "SESSION").text = data["Session"]
            ET.SubElement(root, "ESTA").text = esta_value

            raw_xml = ET.tostring(root, encoding='unicode', method='xml')
            pretty_xml = parseString(raw_xml).toprettyxml(indent="  ")

            output_file = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.xml")
            with open(output_file, 'w', encoding='utf-8') as xml_file:
                xml_file.write(pretty_xml)
        except Exception as e:
            log_message(
                log_file,
                "ERROR",
                f"Unexpected error at line {row_idx}: {traceback.format_exc()}",
                context={"File": ale_path, "Row Content": row.strip()},
                terminal_fallback=False
            )

def main():
    parser = argparse.ArgumentParser(description="Convert an ALE file into multiple XML files.")
    parser.add_argument("ale_file", help="Path to the ALE file to process")
    parser.add_argument("-o", "--output", default="output_xml", help="Directory to save the generated XML files")
    parser.add_argument("-l", "--log", default="error_log.txt", help="Path to save the error log file")
    args = parser.parse_args()

    log_file_path = os.path.join(args.output, args.log)

    process_ale_file(args.ale_file, args.output, log_file_path)
    print(f"Processing complete. Errors and warnings logged to: {log_file_path}")

if __name__ == "__main__":
    main()
