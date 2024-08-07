This folder contains scripts that I used for processing and visualizing results primarily generated during field tests.

**Disclaimer!** Most of these scripts are constantly evolving quick hacks for specific tasks. Think of them as rough drafts.

Contact Áron Szabó for QGIS related tools.

---
#### Analyzing field recordings

These steps were used to analyze the results from the 240717 French test flights. This should definitely become more streamlined over time.

-1. **Make spectrogram recirding:** run pysagax-uav in spectrogram-recording mode
0. **Find ideal ROI mask for the spectrogram:** using `tools/spectrogram_recordings/spectrogram_viewer.py` decide which frequencies and thresholds are ideal
1. **Make detection recording:**  Using detection demo tool (`tools/spectrogram_recordings/detection_demo.py`) 
    1. Modify the file: add the desired ROI mask to the list of predefined masks (TODO: read mask from a file or something)
    1. To make detection recording, run it with: `-r, --recording_file_path TEXT`. Also use the `-id NUMBER` option to use the newly defined spectrum mask.
    1. I used **`.detectrec`** extension for the recording files that include detections. 
2. **Turn the detection recordings into .csv files:** 
    1. **.detectrec to .csv:** use the `protorec_to_csv.py` tool that turns any sequence of protobuf packets to csv. You can exclude fields from or message types from the output. Since we don't need Telemetry messages now, I used `-i Telemetry` to ignore that message type.
    1. **Correct ROI id:** run `add_roi_id_0_to_detectrec.py`. (It's necessary since protobuf messages don't differentiate between empty fields and 0 values.)
    1. **[IF NEEDED] Merge with heading data:** if the detections don't come with correct heading data, than we have to update them based on timestamps:
        1. **Parse Magellium's .txt:** use `tools/Heading/magellium_flight_info_to_csv.txt`
        1. **Merge:** use `tools/update_heading_by_timestamp.py`
3. **Separate by ROIid:** use `filter_detections_by_roi_id.py` to make separate .csv files of separate detections
4. **Fill in the table with correct DF values:** use `apply_yaw_and_stationary_transmitter.py`to calculate compensated DF measurement values and ground-truth values based on transmitter coordinates.
5. **Plot the results:** `plot.py`
