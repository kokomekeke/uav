"""
Seperates the detections in a .csv generated from a .detectrec into separate .csv files by the detections' roiId fields.
[
    detection indecies: the arbitrary index of a detection in the list of detections made from a single measurement packet.
    roi ids: the identifier of the slice of the configured spectrum mask that was used for postprocessing. 
        Currently we assume that 2 detections with the same roiId are made of the same signal. (might  be refined later)
]

Removes the detection index from the headers, 
    so for example: 'detection.frequency' instead of 'detection2.frequency'

"""


import csv
from collections import defaultdict

def main(input_csv):
    # TODO: should've used pandas.
    detection_data = defaultdict(list) #defaultdict to ignore key errors
    
    with open(input_csv, mode='r') as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        
        # Extract general information columns (those that don't start with 'detection')
        general_info_headers = [header for header in headers if not header.startswith('detection')]
        
        
        for row in reader:
            general_info = {header: row[header] for header in general_info_headers}
            
            # Extract detection-related information
            detection_info = defaultdict(dict)
            for header in headers:
                if header.startswith('detection'):
                    parts = header.split('.')
                    detection_index = parts[0]  # e.g. detection0
                    attribute = parts[1]  # subfields of detections, e.g. roiId, azimuth etc.
                    detection_info[detection_index][attribute] = row[header] # values of subfields
            
            # Organize data by detection.roiId
            for detection_index, attributes in detection_info.items():
                if 'roiId' in attributes:
                    detection_id = attributes['roiId']
                    if detection_id:  # Ensure the detection_id is not empty
                        combined_info = {**general_info, **{f'detection.{k}': v for k, v in attributes.items()}}
                        detection_data[int(float(detection_id))].append(combined_info)
    
    # Write separate CSV files for each detection ID
    for detection_id, rows in detection_data.items():
        if rows:
            detection_headers = general_info_headers + [f'{attr}' for attr in rows[0].keys() if attr.startswith('detection.')]
            # print(detection_headers)
            print(detection_id)
            output_csv = f'/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording_roiId_heading_detection#{detection_id}.csv'
            with open(output_csv, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=detection_headers)
                writer.writeheader()
                writer.writerows(rows)

main('/media/rp/data/recordings/240717 Toulouse/detectrec/20240717_151148/spotrecording_roiId_heading.csv')
