This folder contains analyzing tools that I used with .csv recordings created by spotclient. The exact format of these files changed over time, so the tools are not entirely backward compatible.

### Merging tools:
merging .csv spotclient recordings with aaronia logs.

### plotters:
Angle plotter: for stationary transmitter and rotated or stationary receiver
Driving angle plotter: for stationary RX device, and moving transmitter (Ócsa driving measurements)
Triangulated: Measurements made by 2 RX devices, geolocating a transmitter

### Triangulation steps:
* merge_by_tyme_for_triangulation.py: merging the two spotclient recordings and the gps logs of the transmitter by time
* triangulate.py: calculate the measured TX location
* triangulation_plotter.py: plot the error between the measured TX location and the ground-truth location

### other
trim_aggregated_recording: only keeps the rows of the spotclient recording where the DF mean value changes.
