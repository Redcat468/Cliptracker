import os
import argparse
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
import re

def extract_ep_num(name):
    """Extract the EP_NUM from the 'Name' field using regex."""
    match = re.search(r"LGS-(\d{4})-", name)  # Ensure EP_NUM is exactly 4 digits
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

def ale_to_xml_with_errors(ale_path, output_dir):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    error_report = []
    # Read the ALE file
    with open(ale_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Locate the "Column" section and extract headers
    column_start_index = None
    for i, line in enumerate(lines):
        if line.strip() == "Column":
            column_start_index = i + 1  # The headers are on the next line
            break
    
    if column_start_index is None:
        raise ValueError("No 'Column' section found in the ALE file.")
    
    headers = lines[column_start_index].strip().split("\t")
    
    # Locate the "Data" section
    data_start_index = None
    for i, line in enumerate(lines):
        if line.strip() == "Data":
            data_start_index = i + 1
            break
    
    if data_start_index is None:
        raise ValueError("No 'Data' section found in the ALE file.")
    
    # Relevant column indices
    required_columns = ["Name", "Source File", "Source Path", "Session"]
    column_indices = {col: headers.index(col) if col in headers else None for col in required_columns}
    if None in column_indices.values():
        missing_columns = [col for col, idx in column_indices.items() if idx is None]
        raise ValueError(f"Missing required columns in ALE file: {', '.join(missing_columns)}")
    
    esta_idx = headers.index("Esta") if "Esta" in headers else None
    
    # Parse each data row
    for row_idx, row in enumerate(lines[data_start_index:], start=data_start_index + 1):
        columns = row.strip().split("\t")
        if len(columns) <= max(column_indices.values()):
            error_report.append(f"Line {row_idx}: Incomplete data row.")
            continue  # Skip incomplete rows
        
        # Extract required data
        data = {col: columns[idx] if idx is not None and idx < len(columns) else "" for col, idx in column_indices.items()}
        esta = columns[esta_idx] if esta_idx is not None and esta_idx < len(columns) else "0"
        ep_num = extract_ep_num(data["Name"])
        file_name = extract_file_name(data["Source File"])
        
        # Check for missing or invalid data
        error_message = []
        if any(not data[col] for col in required_columns):
            error_message.append("Missing data in required columns.")
        if ep_num is None:
            error_message.append("Invalid EP_NUM in Name field.")
        
        if error_message:
            # Add additional information (Name, Source Path, Source File, and File Name if available)
            additional_info = []
            if data.get("Name"):
                additional_info.append(f"Name: {data['Name']}")
            if data.get("Source Path"):
                additional_info.append(f"Source Path: {data['Source Path']}")
            if data.get("Source File"):
                additional_info.append(f"Source File: {data['Source File']}")
            error_report.append(
                f"Line {row_idx}: {', '.join(error_message)} {' | '.join(additional_info)}"
            )
            continue
        
        # Generate paths
        storage_folderpath = compute_storage_folderpath(ep_num)
        amf_folderpath = compute_amf_folderpath(ep_num)
        esta_value = "TRUE" if esta == "1" else "FALSE"
        
        # Create XML structure
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
        
        # Convert to a formatted XML string
        raw_xml = ET.tostring(root, encoding='unicode', method='xml')
        pretty_xml = parseString(raw_xml).toprettyxml(indent="  ")
        
        # Write the XML file
        output_file = os.path.join(output_dir, f"{os.path.splitext(data['Source File'])[0]}.xml")
        with open(output_file, 'w', encoding='utf-8') as xml_file:
            xml_file.write(pretty_xml)
    
    # Write error report if any errors occurred
    if error_report:
        error_file_path = os.path.join(output_dir, "error_report.txt")
        with open(error_file_path, 'w', encoding='utf-8') as error_file:
            error_file.write("\n".join(error_report))
        print(f"Errors found. Report written to: {error_file_path}")
    else:
        print("No errors found.")

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Convert an ALE file into multiple XML files.")
    parser.add_argument("ale_file", help="Path to the ALE file to process")
    parser.add_argument(
        "-o", "--output", default="output_xml", help="Directory to save the generated XML files"
    )
    args = parser.parse_args()
    
    # Process the ALE file with error handling
    ale_to_xml_with_errors(args.ale_file, args.output)
    print(f"XML files generated in directory: {args.output}")

if __name__ == "__main__":
    main()
