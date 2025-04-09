
import { ComintDetection } from './comintDetection'

export interface Sensor {
  is_selected?: boolean
  uav_id: number
  uav_label?: string | null
  uav_address?: string | null
  active: boolean
  conf_id?: number | null
  last_seen?: Date | null
  last_pos_lat?: number | null
  last_pos_lon?: number | null
  last_pos_altitude?: number | null
  last_pos_q0?: number | null
  last_pos_q1?: number | null
  last_pos_q2?: number | null
  last_pos_q3?: number | null
  health_report?: string | null
  detections?: ComintDetection[] // ← ez lehet undefined is, ha nem inicializálod
}

