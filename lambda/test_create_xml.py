#!/usr/bin/env python3
"""
Test script to generate MusicXML output from a prediction TSV file.

Usage:
    python test_create_xml.py                          # uses default hardcoded path
    python test_create_xml.py /path/to/prediction.tsv  # explicit input file
    python test_create_xml.py /path/to/prediction.tsv /path/to/out.xml  # explicit in + out
"""
from create_xml import preprocess_input, process_tied_notes, create_musicxml
import xml.etree.ElementTree as ET
import sys
import os
import ast

# Resolve input and output paths from CLI args or fall back to defaults
_default_input = os.path.join(
    os.path.dirname(__file__),
    'output/full_tech_prediction/idea-20250609_note_level_final_tech_full_prediction_segment_00.tsv'
)
prediction_file = sys.argv[1] if len(sys.argv) > 1 else _default_input
_default_output = os.path.join(os.path.dirname(os.path.abspath(prediction_file)),
                               os.path.splitext(os.path.basename(prediction_file))[0] + '_output.xml')
output_file = sys.argv[2] if len(sys.argv) > 2 else _default_output

print("="*60)
print("GENERATING MUSICXML FROM ACTUAL PREDICTION FILE")
print("="*60)
print(f"\nInput file: {prediction_file}")

# Parse the TSV file
sample_notes = []
with open(prediction_file, 'r') as f:
    for line in f:
        line = line.strip()
        if line:
            # Each line is like: [0, 6, 74, 3, 7, 19] (6 fields)
            # or [0, 6, 74, 3, 7] (5 fields, no technique — pad with 19)
            note = list(ast.literal_eval(line))
            if len(note) == 5:
                note.append(19)
            sample_notes.append(note)

print(f"Loaded: {len(sample_notes)} notes")

# Process the notes
print("\nStep 1: Preprocessing input...")
preprocessed = preprocess_input(sample_notes)
print(f"  ✅ Preprocessed {len(preprocessed)} notes")

print("\nStep 2: Processing tied notes...")
output_notes = process_tied_notes(preprocessed)
print(f"  ✅ Processed {len(output_notes)} output notes")

print("\nStep 3: Creating MusicXML...")
tree = create_musicxml(output_notes)
ET.indent(tree, space="  ", level=0)
print(f"  ✅ MusicXML tree created")

# Save to file
tree.write(output_file, encoding='utf-8', xml_declaration=True)

print(f"\nStep 4: Saving to file...")
print(f"  ✅ File saved: {output_file}")

# Calculate some stats
measures = max(note[0] for note in output_notes) // 48 + 1
print(f"\n📊 Statistics:")
print(f"  - Total notes: {len(output_notes)}")
print(f"  - Measures: {measures}")
print(f"  - File size: {os.path.getsize(output_file)} bytes")

# Print preview of XML content
print("\n" + "="*60)
print("PREVIEW OF XML CONTENT (first 80 lines):")
print("="*60 + "\n")

with open(output_file, 'r') as f:
    content = f.read()
    lines = content.split('\n')
    for i, line in enumerate(lines[:80], 1):
        print(f"{i:3d} | {line}")
    
    if len(lines) > 80:
        print(f"\n... ({len(lines) - 80} more lines)")
        print(f"\nTotal lines: {len(lines)}")

print("\n" + "="*60)
print("✅ DONE! You can open this file in MuseScore or Guitar Pro")
print("="*60)
print(f"\nTo view in MuseScore:")
print(f"  open -a MuseScore {output_file}")
print(f"\nOr view the full XML:")
print(f"  cat {output_file}")
