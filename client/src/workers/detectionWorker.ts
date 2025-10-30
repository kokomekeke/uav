// ============================================================================
// TYPES
// ============================================================================

interface Quaternion {
  q0: number
  q1: number
  q2: number
  q3: number
}

interface Detection {
  timestamp: number
  frequency: number
  azimuth: number
  elevation: number
  meanAzimuth: number
  meanElevation: number
  coordinate: [number, number]
  quaternion: Quaternion
  heading: number
  gpsLat: number
  gpsLon: number
  altitude: number
  roi_id: number | null
}

interface DetectionItem {
  frequency: number
  azimuth?: number
  elevation?: number
  mean_azimuth?: number  // ✅ snake_case
  mean_elevation?: number // ✅ snake_case
  roi_id?: number
  bandwidth?: number
  strength?: number
  snr?: number
}

interface HeadingData {
  latitude?: number    // ✅ GPS koordináták a heading_data-ból
  longitude?: number
  altitude?: number
  heading?: number
  // További mezők a heading.proto szerint
}

interface MeasurementData {
  time?: number
  stream_id?: number
  config_id?: number
  source_time?: number
  packet_id?: number
  position?: number
  quaternion?: number[]  // ✅ repeated float = tömb
  overflow?: boolean
  peaks?: number[]
  heading_data?: HeadingData  // ✅ snake_case
  sampleIndex?: number
  data?: any[]
  detection?: DetectionItem[]  // ✅ repeated Detection
}

interface StreamPacket {
  id: number
  type?: string
  Measurement?: MeasurementData
  Telemetry?: any
  Event?: any
  Error?: any
}

interface WorkerStats {
  totalReceived: number
  totalProcessed: number
  lastProcessingTime: number
  avgProcessingTime: number
}

type WorkerIncomingMessage =
  | { type: 'uavIds'; uavIds: number[] }
  | { type: 'newDetection'; detection: string }
  | { type: 'updateSettings'; samplingRate?: number; maxLatencyMs?: number }
  | { type: 'clearDetections' }
  | { type: 'getStats' }
  | { type: 'terminate' }

type WorkerOutgoingMessage =
  | { type: 'processedDetection'; detection: Detection; uavId: number; timestamp: number }
  | { type: 'statsUpdated'; stats: WorkerStats }
  | { type: 'error'; message: string; uavId?: number }
  | { type: 'workerStarted'; timestamp: number; version: string }
  | { type: 'uavIdsUpdated'; uavIds: number[] }
  | { type: 'settingsUpdated'; settings: { samplingRate: number; maxLatencyMs: number } }
  | { type: 'terminated' }
  | { type: 'memoryStats'; memory: { usedJSHeapSize: number; totalJSHeapSize: number; limit: number } }

// ============================================================================
// GLOBALS
// ============================================================================

let samplingRate = 0
let uavIds: number[] = []
let lastSampleTime = 0
let maxLatencyMs = 900

let stats: WorkerStats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0,
  avgProcessingTime: 0
}

// Data type constants
const DataType = {
  TELEMETRY: 't',
  MEASUREMENT: 'm',
  EVENT: 'v',
  ERROR: 'e'
} as const

type DataTypeValue = typeof DataType[keyof typeof DataType]

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Koordináta számítás azimut és elevációból
 */
function calculateCoordinate (
  azimuth: number,
  elevation: number,
  gpsLat: number,
  gpsLon: number,
  altitude: number
): [number, number] {
  const R = 6371000
  const elevationRad = elevation
  const azimuthRad = azimuth

  const distance = altitude / Math.tan(Math.abs(elevationRad))
  const clampedDistance = Math.max(0, Math.min(distance, 100000))

  const latRad = (gpsLat * Math.PI) / 180
  const lonRad = (gpsLon * Math.PI) / 180

  const newLatRad = Math.asin(
    Math.sin(latRad) * Math.cos(clampedDistance / R) +
    Math.cos(latRad) * Math.sin(clampedDistance / R) * Math.cos(azimuthRad)
  )

  const newLonRad = lonRad + Math.atan2(
    Math.sin(azimuthRad) * Math.sin(clampedDistance / R) * Math.cos(latRad),
    Math.cos(clampedDistance / R) - Math.sin(latRad) * Math.sin(newLatRad)
  )

  const newLat = (newLatRad * 180) / Math.PI
  const newLon = (newLonRad * 180) / Math.PI

  return [newLat, newLon]
}

/**
 * Quaternion alapú heading számítás
 */
function getHeadingFromQuaternion (
  q0: number,
  q1: number,
  q2: number,
  q3: number
): number {
  if (q0 === undefined || q1 === undefined || q2 === undefined || q3 === undefined) {
    return 0
  }

  const headingRad = Math.atan2(
    2 * (q0 * q3 + q1 * q2),
    q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
  )

  const deg = headingRad * (180 / Math.PI)
  return deg < 0 ? deg + 360 : deg
}

/**
 * Optimalizált detekció objektum létrehozása
 */
function createOptimizedDetection (
  detectionItem: DetectionItem,
  gpsLat: number,
  gpsLon: number,
  altitude: number,
  quaternion: Quaternion,
  heading: number,
  timestamp: number
): Detection {
  const coordinate = calculateCoordinate(
    detectionItem.azimuth ?? detectionItem.mean_azimuth ?? 0,  // ✅ snake_case
    detectionItem.elevation ?? detectionItem.mean_elevation ?? 0,  // ✅ snake_case
    gpsLat,
    gpsLon,
    altitude
  )

  return {
    timestamp,
    frequency: detectionItem.frequency,
    azimuth: detectionItem.azimuth ?? 0,
    elevation: detectionItem.elevation ?? 0,
    meanAzimuth: detectionItem.mean_azimuth ?? 0,  // ✅ snake_case -> camelCase (frontend)
    meanElevation: detectionItem.mean_elevation ?? 0,  // ✅ snake_case -> camelCase (frontend)
    coordinate,
    quaternion,
    heading,
    gpsLat,
    gpsLon,
    altitude,
    roi_id: detectionItem.roi_id ?? null
  }
}

/**
 * Data type detektálása
 */
function detectDataType (item: StreamPacket): DataTypeValue | null {
  if (item.type) {
    return item.type as DataTypeValue
  }

  if (item.Measurement) return DataType.MEASUREMENT
  if (item.Telemetry) return DataType.TELEMETRY
  if (item.Event) return DataType.EVENT
  if (item.Error) return DataType.ERROR

  return null
}

// ============================================================================
// MAIN PROCESSING FUNCTION
// ============================================================================

function processRawDetection (detectionData: string): void {
  const t0_processStart = performance.now()
  const currentTime = Date.now()

  // Sampling rate ellenőrzés
  if (samplingRate > 0 && currentTime - lastSampleTime < samplingRate) {
    return
  }
  lastSampleTime = currentTime

  if (!detectionData) {
    console.warn('[Worker] No detection data received')
    return
  }

  let parsed: StreamPacket[]
  try {
    parsed = JSON.parse(detectionData) as StreamPacket[]
  } catch (error) {
    console.error('[Worker] JSON parse error:', error)
    return
  }

  if (!Array.isArray(parsed)) {
    console.warn('[Worker] Data is not an array')
    return
  }

  let processedCount = 0

  for (const item of parsed) {
    const backendUavId = item.id
    if (!uavIds.includes(backendUavId)) continue

    const dataType = detectDataType(item)
    if (dataType !== DataType.MEASUREMENT) continue

    const measurement = item.Measurement
    if (!measurement || !measurement.detection || measurement.detection.length === 0) continue

    // ✅ GPS koordináták és altitude a heading_data-ból (snake_case!)
    const headingData = measurement.heading_data || {}
    const gpsLat = headingData.latitude ?? 47.355520  // fallback Budapest
    const gpsLon = headingData.longitude ?? 19.268900
    const altitude = headingData.altitude ?? 100.0

    // ✅ Quaternion közvetlenül a Measurement-ből (repeated float = tömb)
    const quaternionArray = measurement.quaternion || []
    let q0 = 1, q1 = 0, q2 = 0, q3 = 0

    if (Array.isArray(quaternionArray) && quaternionArray.length === 4) {
      [q0, q1, q2, q3] = quaternionArray
    }

    const quaternion: Quaternion = { q0, q1, q2, q3 }
    const heading = getHeadingFromQuaternion(q0, q1, q2, q3)

    const timestamp = performance.now()

    // ✅ Latency ellenőrzés
    const processingLatency = timestamp - t0_processStart
    if (processingLatency > maxLatencyMs) {
      console.warn(`[Worker] ⚠️ Processing too slow: ${processingLatency.toFixed(2)}ms`)
    }

    // ✅ Detection-ok feldolgozása (repeated Detection = tömb)
    measurement.detection.forEach((detectionItem: DetectionItem) => {
      try {
        const detection = createOptimizedDetection(
          detectionItem,
          gpsLat,
          gpsLon,
          altitude,
          quaternion,
          heading,
          timestamp
        )

        stats.totalReceived++
        stats.totalProcessed++
        processedCount++

        const message: WorkerOutgoingMessage = {
          type: 'processedDetection',
          detection,
          uavId: backendUavId,
          timestamp: measurement.time || currentTime
        }
        self.postMessage(message)
      } catch (error) {
        console.error('[Worker] Detection processing error:', error)
        const errorMessage: WorkerOutgoingMessage = {
          type: 'error',
          message: `Detection processing failed: ${(error as Error).message}`,
          uavId: backendUavId
        }
        self.postMessage(errorMessage)
      }
    })
  }

  const processingTime = performance.now() - t0_processStart
  stats.lastProcessingTime = processingTime
  stats.avgProcessingTime = (stats.avgProcessingTime * 0.9) + (processingTime * 0.1)

  if (processedCount > 0) {
    console.log(
      `[Worker] ✅ Processed ${processedCount} detections in ${processingTime.toFixed(2)}ms ` +
      `(avg: ${stats.avgProcessingTime.toFixed(2)}ms)`
    )
  }

  if (stats.totalProcessed % 100 === 0) {
    const statsMessage: WorkerOutgoingMessage = {
      type: 'statsUpdated',
      stats: { ...stats }
    }
    self.postMessage(statsMessage)
  }
}

// ============================================================================
// MESSAGE HANDLER
// ============================================================================

self.onmessage = function (e: MessageEvent<WorkerIncomingMessage>) {
  const message = e.data

  try {
    switch (message.type) {
      case 'uavIds': {
        if (!message.uavIds || !Array.isArray(message.uavIds)) return
        uavIds = message.uavIds
        console.log('[Worker] ✅ UAV IDs updated:', uavIds)
        self.postMessage({ type: 'uavIdsUpdated', uavIds })
        break
      }

      case 'newDetection': {
        processRawDetection(message.detection)
        break
      }

      case 'updateSettings': {
        if (message.samplingRate !== undefined) {
          samplingRate = Math.max(0, message.samplingRate)
        }
        if (message.maxLatencyMs !== undefined) {
          maxLatencyMs = message.maxLatencyMs
          console.log(`[Worker] Max latency updated: ${maxLatencyMs}ms`)
        }
        const response: WorkerOutgoingMessage = {
          type: 'settingsUpdated',
          settings: { samplingRate, maxLatencyMs }
        }
        self.postMessage(response)
        break
      }

      case 'clearDetections': {
        stats = {
          totalReceived: 0,
          totalProcessed: 0,
          lastProcessingTime: 0,
          avgProcessingTime: 0
        }
        console.log('[Worker] Statistics cleared')
        self.postMessage({ type: 'statsUpdated', stats: { ...stats } })
        break
      }

      case 'getStats': {
        self.postMessage({ type: 'statsUpdated', stats: { ...stats } })
        break
      }

      case 'terminate': {
        console.log('[Worker] Terminating...')
        self.postMessage({ type: 'terminated' })
        self.close()
        break
      }

      default: {
        console.warn('[Worker] Unknown message type:', (message as any).type)
        self.postMessage({
          type: 'error',
          message: `Unknown message type: ${(message as any).type}`
        })
      }
    }
  } catch (error) {
    console.error('[Worker] Message handling error:', error)
    self.postMessage({
      type: 'error',
      message: `Message handling failed: ${(error as Error).message}`
    })
  }
}

// ============================================================================
// WORKER INITIALIZATION
// ============================================================================

const initMessage: WorkerOutgoingMessage = {
  type: 'workerStarted',
  timestamp: Date.now(),
  version: '5.0-protobuf-corrected'
}
self.postMessage(initMessage)
console.log('✅ Detection Worker v5.0 initialized - Protobuf Corrected Mode')

// ============================================================================
// ERROR HANDLER
// ============================================================================

self.onerror = function (error: ErrorEvent) {
  console.error('[Worker] Uncaught error:', error)
  self.postMessage({
    type: 'error',
    message: `Worker uncaught error: ${error.message}`
  })
}

// ============================================================================
// PERFORMANCE MONITORING
// ============================================================================

if (typeof performance !== 'undefined' && (performance as any).memory) {
  setInterval(() => {
    const memory = (performance as any).memory
    self.postMessage({
      type: 'memoryStats',
      memory: {
        usedJSHeapSize: memory.usedJSHeapSize,
        totalJSHeapSize: memory.totalJSHeapSize,
        limit: memory.jsHeapSizeLimit
      }
    })
  }, 30000)
}