This folder contains scripts that I used for processing and visualizing results primarily generated during field tests.

**Disclaimer!** Most of these scripts are constantly evolving quick hacks for specific tasks. Think of them as rough drafts.

Contact Péter Rigó if you have questions.

*****************************************

###  The following files are here (**incomplete**): #TODO 
The more important ones are marked with bold
- **`analyze_field_recordings`**: processing the recordings made on field tests. Might be obsolete and need changes. See details later in this readme.
    - `add_roi_id_0_to_detectrec.py`: 
    - `apply_yaw_and_stationary_transmitter.py`: 
    - `detection_demo.py`: 
    - `filter_detections_by_roi_id.py`: 
    - `plot.py`: 
    - `update_heading_by_timestamp.py`: 
- `heading`: 
    - **`flight_info_test_server.py`**: Mock Magellium's flight-info server for pysagax-heading. Can be used to **simulate heading data** for a straight and a circling flight path.
    - `magellium_flight_info_txt_to_csv.py`: convert Magellium's .txt flight logs to .csv
    - `yawpitchroll.py`: GUI program converting aircraft attitude (yaw, pitch, roll) to quaternions and target location from Earth coordinates to body coordinates. Test the error of different heading-compensation methods (eg not accounting for pitch and roll)
- `mock`: 
- `old`: tools that will probably not be used again in their current form
    - `spotclient_recordings`: working with .csv recordings made by earlier SPOTclient versions
        - `merging_data`: 
            - `merg_by_time.py`: 
            - `merg_by_time_for_triangulation.py`: 
            - `merge_csv_files_in_a_folder.py`: 
            - `merge_stationary_transmitter.py`: 
        - `angle_plotter.py`: 
        - `driving_angle_plotter.py`: 
        - `nautipy.py`: 
        - `triangulate.py`: 
        - `triangulation_plotter.py`: 
        - `trim_aggregated_recording.py`: 
- `sigmf`: tools used to interact with sigmf iq recordings
    - `sigmf_spectrogram`: 
        - `gen_spectrograms.py`: 
        - `mag_comint_plotter.py`: 
        - `snr.py`: 
        - `spectogram_viewer.py`: 
- `spectrogram_recordings`: for .protorec (and .detectrec) files
    - `extract_heading_from_protorec.py`: 
    - `mock_scan.protorec`: 
    - `spectrogram_packet_by_packet.py`: 
- **`calculate_df_angle.py`**: IN PROGRESS GUI program to calculate the correct df angle given the sensor and the target location 
- **`detectrec_to_csv.py`**: convert .detectrec to .csv with lots of extras such as calculating errors for given transmitter locations. 
- **`plot_peaks_and_df_angles.py`**: for rotated RX tests, to see if DF angle changes linearly
- **`plot_results.py`**: 
- **`protorec_to_csv.py`**: convert any .protorec files to .csv. For .detectrec files consider using `detectrec_to_csv.py`
- **`spectrogram_viewer.py`**:  plot spectrograms from .protorec files
- `trim_detection_csv.py`: 


---
#### Analyzing field recordings

These steps were used to analyze the results from the 240717 French test flights. This should definitely become more streamlined over time.

-1. **Make spectrogram recording:** run pysagax-uav in spectrogram-recording mode
0. **Find ideal ROI mask for the spectrogram:** using `spectrogram_viewer.py` decide which frequencies and thresholds are ideal
1. **Make detection recording:**  Using detection demo tool (`analyze_field_recordings/detection_demo.py`) 
    1. Modify the file: add the desired ROI mask to the list of predefined masks (TODO: read mask from a file or something)
    1. To make detection recording, run it with: `-r, --recording_file_path TEXT`. Also use the `-id NUMBER` option to use the newly defined spectrum mask.
    1. I used **`.detectrec`** extension for the recording files that include detections. 
2. **Turn the detection recordings into .csv files:** 
    1. **.detectrec to .csv:** use the `protorec_to_csv.py` tool that turns any sequence of protobuf packets to csv. You can exclude fields from or message types from the output. Since we don't need Telemetry messages now, I used `-i Telemetry` to ignore that message type.
    1. **Correct ROI id:** run `analyze_field_recordings/add_roi_id_0_to_detectrec.py`. (It's necessary since protobuf messages don't differentiate between empty fields and 0 values.)
    1. **[IF NEEDED] Merge with heading data:** if the detections don't come with correct heading data, than we have to update them based on timestamps:
        1. **Parse Magellium's .txt:** use `heading/magellium_flight_info_to_csv.txt`
        1. **Merge:** use `analyze_field_recordings/update_heading_by_timestamp.py`
3. **Separate by ROIid:** use `filter_detections_by_roi_id.py` to make separate .csv files of separate detections
4. **Fill in the table with correct DF values:** use `apply_yaw_and_stationary_transmitter.py`to calculate compensated DF measurement values and ground-truth values based on transmitter coordinates.
5. **Plot the results:** `analyze_field_recordings/plot.py`

