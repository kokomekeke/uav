// workers/detectionWorker.ts
import type {
  WorkerStats,
  Detection,
  HeadingData,
  DetectionItem,
  MeasurementData,
  StreamPacket,
  WorkerIncomingMessage,
  WorkerOutgoingMessage
} from '@/types/worker'

// ============================================================================
// GLOBALS
// ============================================================================

let samplingRate = 0
let uavIds: number[] = []
let lastSampleTime = 0
let maxLatencyMs = 900 // ✨ ÚJ CONFIG

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
  headingData: HeadingData,
  timestamp: number
): Detection {
  const { gpsLat = 47.355520, gpsLon = 19.268900, altitude = 100, quaternion } = headingData

  // Quaternion parse
  let q0 = 1; let q1 = 0; let q2 = 0; let q3 = 0

  if (Array.isArray(quaternion) && quaternion.length === 4) {
    [q0, q1, q2, q3] = quaternion
  } else if (quaternion && typeof quaternion === 'object') {
    q0 = quaternion.q0 ?? quaternion[0] ?? 1
    q1 = quaternion.q1 ?? quaternion[1] ?? 0
    q2 = quaternion.q2 ?? quaternion[2] ?? 0
    q3 = quaternion.q3 ?? quaternion[3] ?? 0
  }

  const heading = getHeadingFromQuaternion(q0, q1, q2, q3)

  const coordinate = calculateCoordinate(
    detectionItem.azimuth ?? detectionItem.meanAzimuth ?? 0,
    detectionItem.elevation ?? detectionItem.meanElevation ?? 0,
    gpsLat,
    gpsLon,
    altitude
  )

  return {
    timestamp,
    frequency: detectionItem.frequency,
    azimuth: detectionItem.azimuth,
    elevation: detectionItem.elevation,
    meanAzimuth: detectionItem.meanAzimuth,
    meanElevation: detectionItem.meanElevation,
    coordinate,
    quaternion: { q0, q1, q2, q3 },
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
    if (!dataType) continue

    switch (dataType) {
      case DataType.MEASUREMENT: {
        const measurement = item.Measurement
        if (!measurement || !measurement.detection) break

        const headingData: HeadingData = measurement.headingData || {}
        headingData.gpsLat = headingData.gpsLat ?? 47.355520
        headingData.gpsLon = headingData.gpsLon ?? 19.268900
        headingData.altitude = headingData.altitude ?? 100.0

        const timestamp = performance.now()

        // ✅ Latency ellenőrzés már itt a worker-ben
        const processingLatency = timestamp - t0_processStart
        if (processingLatency > maxLatencyMs) {
          console.warn(`[Worker] ⚠️ Processing too slow: ${processingLatency.toFixed(2)}ms`)
        }

        measurement.detection.forEach((detectionItem: DetectionItem) => {
          try {
            const detection = createOptimizedDetection(
              detectionItem,
              headingData,
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
        break
      }

      case DataType.TELEMETRY:
      case DataType.EVENT:
      case DataType.ERROR:
        // későbbi implementáció
        break
    }
  }

  const processingTime = performance.now() - t0_processStart
  stats.lastProcessingTime = processingTime
  stats.avgProcessingTime = (stats.avgProcessingTime * 0.9) + (processingTime * 0.1)

  if (processedCount > 0) {
    console.log(
      `[Worker] Processed ${processedCount} detections in ${processingTime.toFixed(2)}ms ` +
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
        // ✨ ÚJ: Max latency config
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
  version: '4.0-typescript-unified'
}
self.postMessage(initMessage)
console.log('✅ Detection Worker v4.0 initialized - TypeScript Unified Mode')

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
