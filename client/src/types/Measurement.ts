export interface HeadingData {
  timestamp: string
  gpsTime: string
  gpsLat: number
  gpsLon: number
  altitude: number
  quaternion: [number, number, number, number]
}

export interface Detection {
  frequency: number
  azimuth: number
  elevation: number
  meanAzimuth: number
  meanElevation: number
}

export interface Measurement {
  time: string
  peaks: number[]
  headingData: HeadingData
  detection: Detection[]
}

export interface SensorItem {
  id: number
  Measurement: Measurement
  server_time: number
}
