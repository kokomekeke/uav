export interface ComintDetection {
  detection_id?: number; // Primary Key
  uav_id: number; // Foreign Key referencing UAV table
  uav_event_id?: number | null; // Foreign Key referencing UAV event table
  frequency?: bigint; // Large integer
  signal_strength?: number; // Precision (8,3) -> Floating-point
  bandwidth?: bigint; // Large integer
  snr?: number; // Precision (8,3) -> Floating-point
  lob_azim_deg: number; // Precision (6,3) -> Floating-point
  lob_elev_deg: number; // Precision (6,3) -> Floating-point
  precision: number; // Precision (4,3) -> Floating-point
  timestamp: Date;
  uav_pos_lat?: number | null; // Precision (10,6) -> Floating-point
  uav_pos_lon?: number | null; // Precision (10,6) -> Floating-point
  uav_pos_altitude?: number | null; // Precision (10,3) -> Floating-point
  uav_pos_q0?: number | null; // Quaternion component
  uav_pos_q1?: number | null;
  uav_pos_q2?: number | null;
  uav_pos_q3?: number | null;
  roi_identifier?: number | null;
}
