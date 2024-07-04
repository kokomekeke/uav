import os
import pandas as pd

# Set the directory path where the CSV files are located
directory_path = 'C:\\Users\\p\\Documents\\measurments\\ocsa_231113\\moving_drones_1_2merged\\New folder'
csv_files = [file for file in os.listdir(directory_path) if file.endswith('.csv')]
merged_data = pd.DataFrame()

for file in sorted(csv_files):  # Sorting files alphabetically (by timestamps in filename)
    file_path = os.path.join(directory_path, file)
    current_data = pd.read_csv(file_path)
    merged_data = pd.concat([merged_data, current_data], ignore_index=True)


# Save the merged data to a new CSV file
merged_data.to_csv(f"{directory_path}\\from_{csv_files[0][:-4]}_to_{csv_files[-1][:-4]}.csv")

print("DONE")