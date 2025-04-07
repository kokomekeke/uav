import {ComintDetection} from './comintDetection';

export interface Sensor {
    uav_id: number; // Primary Key
    uav_label?: string | null;
    uav_address?: string | null;
    active: boolean;
    conf_id?: number | null; // Foreign Key referencing configuration table
    last_seen?: Date | null;
    last_pos_lat?: number | null; // Precision (10,6) -> Floating-point
    last_pos_lon?: number | null; // Precision (10,6) -> Floating-point
    last_pos_altitude?: number | null; // Precision (10,3) -> Floating-point
    last_pos_q0?: number | null; // Quaternion component
    last_pos_q1?: number | null;
    last_pos_q2?: number | null;
    last_pos_q3?: number | null;
    health_report?: string | null;
    detections?: ComintDetection[];
}
