// types/worker.ts

export interface WorkerStats {
  totalReceived: number
  totalProcessed: number
  lastProcessingTime: number
  avgProcessingTime: number
}

export interface Detection {
  timestamp: number
  frequency?: number
  azimuth?: number
  elevation?: number
  meanAzimuth?: number
  meanElevation?: number
  coordinate: [number, number]
  quaternion: {
    q0: number
    q1: number
    q2: number
    q3: number
  }
  heading: number
  gpsLat: number
  gpsLon: number
  altitude: number
  roi_id: number | null
}

export interface HeadingData {
  gpsLat?: number
  gpsLon?: number
  altitude?: number
  quaternion?: number[] | {
    q0?: number
    q1?: number
    q2?: number
    q3?: number
    [key: number]: number
  }
}

export interface DetectionItem {
  frequency?: number
  azimuth?: number
  elevation?: number
  meanAzimuth?: number
  meanElevation?: number
  roi_id?: number | null
}

export interface MeasurementData {
  time?: number
  headingData?: HeadingData
  detection: DetectionItem[]
}

export interface StreamPacket {
  id: number
  type?: 't' | 'm' | 'v' | 'e'
  Telemetry?: any
  Measurement?: MeasurementData
  Event?: any
  Error?: any
  server_time?: number
}

// Worker message types
export interface WorkerMessage {
  type: string
  [key: string]: any
}

export interface UavIdsMessage extends WorkerMessage {
  type: 'uavIds'
  uavIds: number[]
}

export interface NewDetectionMessage extends WorkerMessage {
  type: 'newDetection'
  detection: string
  timestamp?: number
}

export interface ProcessedDetectionMessage extends WorkerMessage {
  type: 'processedDetection'
  detection: Detection
  uavId: number
  timestamp: number
}

export interface StatsUpdatedMessage extends WorkerMessage {
  type: 'statsUpdated'
  stats: WorkerStats
}

export interface ErrorMessage extends WorkerMessage {
  type: 'error'
  message: string
  uavId?: number
}

export interface WorkerStartedMessage extends WorkerMessage {
  type: 'workerStarted'
  timestamp: number
  version: string
}

export interface MemoryStatsMessage extends WorkerMessage {
  type: 'memoryStats'
  memory: {
    usedJSHeapSize: number
    totalJSHeapSize: number
    limit: number
  }
}

export type WorkerIncomingMessage =
  | UavIdsMessage
  | NewDetectionMessage
  | { type: 'updateSettings'; samplingRate?: number }
  | { type: 'clearDetections' }
  | { type: 'getStats' }
  | { type: 'terminate' }

export type WorkerOutgoingMessage =
  | ProcessedDetectionMessage
  | StatsUpdatedMessage
  | ErrorMessage
  | WorkerStartedMessage
  | MemoryStatsMessage
  | { type: 'uavIdsUpdated'; uavIds: number[] }
  | { type: 'settingsUpdated'; settings: { samplingRate: number } }
  | { type: 'terminated' }