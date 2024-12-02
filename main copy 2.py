import os
import argparse
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
import re

def extract_ep_num(name):
    """Extract the EP_NUM from the 'Name' field using regex."""
    match = re.search(r"LGS-(\d+)-", name)
    return match.group(1) if match else None

def ale_to_xml_fixed(ale_path, output_dir):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
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
    name_idx = headers.index("Name")
    src_file_idx = headers.index("Source File")
    src_path_idx = headers.index("Source Path")
    
    # Parse each data row
    for row in lines[data_start_index:]:
        columns = row.strip().split("\t")
        if len(columns) <= max(name_idx, src_file_idx, src_path_idx):
            continue  # Skip incomplete rows
        
        # Extract required data
        name = columns[name_idx]
        src_filename = columns[src_file_idx]
        native_folderpath = columns[src_path_idx]
        ep_num = extract_ep_num(name)
        
        # Create XML structure
        root = ET.Element("Clip")
        ET.SubElement(root, "NAME").text = name
        ET.SubElement(root, "SRC_FILENAME").text = src_filename
        ET.SubElement(root, "NATIVE_FOLDERPATH").text = native_folderpath
        ET.SubElement(root, "EP_NUM").text = ep_num
        
        # Convert to a formatted XML string
        raw_xml = ET.tostring(root, encoding='unicode', method='xml')
        pretty_xml = parseString(raw_xml).toprettyxml(indent="  ")
        
        # Write the XML file
        output_file = os.path.join(output_dir, f"{os.path.splitext(src_filename)[0]}.xml")
        with open(output_file, 'w', encoding='utf-8') as xml_file:
            xml_file.write(pretty_xml)

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Convert an ALE file into multiple XML files.")
    parser.add_argument("ale_file", help="Path to the ALE file to process")
    parser.add_argument(
        "-o", "--output", default="output_xml", help="Directory to save the generated XML files"
    )
    args = parser.parse_args()
    
    # Process the ALE file
    ale_to_xml_fixed(args.ale_file, args.output)
    print(f"XML files generated in directory: {args.output}")

if __name__ == "__main__":
    main()
