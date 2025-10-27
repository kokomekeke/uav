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
  const R = 6371000 // Föld sugara méterben
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

/**
 * Nyers detekció feldolgozása
 */
function processRawDetection (detectionData: string): void {
  const t0_processStart = performance.now()
  const currentTime = Date.now()

  // Sampling rate ellenőrzés
  if (samplingRate > 0 && currentTime - lastSampleTime < samplingRate) {
    return
  }
  lastSampleTime = currentTime

  // Validáció
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

  // Feldolgozás
  for (const item of parsed) {
    const backendUavId = item.id

    // ✅ FILTERING: Csak a kiválasztott UAV-ok
    if (!uavIds.includes(backendUavId)) {
      continue
    }

    const dataType = detectDataType(item)

    if (!dataType) {
      console.warn(`[Worker] Unknown data type for UAV ${backendUavId}`)
      continue
    }

    switch (dataType) {
      case DataType.MEASUREMENT: {
        const measurement = item.Measurement

        if (!measurement || !measurement.detection) {
          console.warn(`[Worker] Invalid measurement data for UAV ${backendUavId}`)
          break
        }

        const headingData: HeadingData = measurement.headingData || {}

        // Default GPS koordináták
        headingData.gpsLat = headingData.gpsLat ?? 47.355520
        headingData.gpsLon = headingData.gpsLon ?? 19.268900
        headingData.altitude = headingData.altitude ?? 100.0

        const timestamp = performance.now()

        // Detekciók feldolgozása
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

            // Küldés vissza a main thread-nek
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

      case DataType.TELEMETRY: {
        // Telemetria kezelés (későbbre)
        break
      }

      case DataType.EVENT: {
        // Event kezelés (későbbre)
        break
      }

      case DataType.ERROR: {
        console.error(`[Worker] Error data received for UAV ${backendUavId}:`, item.Error)
        break
      }
    }
  }

  // Teljesítmény mérés
  const processingTime = performance.now() - t0_processStart
  stats.lastProcessingTime = processingTime
  stats.avgProcessingTime = (stats.avgProcessingTime * 0.9) + (processingTime * 0.1)

  // Debug log (csak ha voltak feldolgozott detekciók)
  if (processedCount > 0) {
    console.log(
      `[Worker] Processed ${processedCount} detections in ${processingTime.toFixed(2)}ms ` +
      `(avg: ${stats.avgProcessingTime.toFixed(2)}ms)`
    )
  }

  // Periodikus statisztika update
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
        if (!message.uavIds || !Array.isArray(message.uavIds)) {
          console.warn('[Worker] Invalid UAV IDs received')
          return
        }
        uavIds = message.uavIds
        console.log('[Worker] ✅ UAV IDs updated:', uavIds)

        const response: WorkerOutgoingMessage = {
          type: 'uavIdsUpdated',
          uavIds
        }
        self.postMessage(response)
        break
      }

      case 'newDetection': {
        processRawDetection(message.detection)
        break
      }

      case 'updateSettings': {
        if (message.samplingRate !== undefined) {
          samplingRate = Math.max(0, message.samplingRate)
          console.log(`[Worker] Sampling rate updated: ${samplingRate}ms`)
        }

        const response: WorkerOutgoingMessage = {
          type: 'settingsUpdated',
          settings: { samplingRate }
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

        const response: WorkerOutgoingMessage = {
          type: 'statsUpdated',
          stats: { ...stats }
        }
        self.postMessage(response)
        break
      }

      case 'getStats': {
        const response: WorkerOutgoingMessage = {
          type: 'statsUpdated',
          stats: { ...stats }
        }
        self.postMessage(response)
        break
      }

      case 'terminate': {
        console.log('[Worker] Terminating...')
        const response: WorkerOutgoingMessage = {
          type: 'terminated'
        }
        self.postMessage(response)
        self.close()
        break
      }

      default: {
        console.warn('[Worker] Unknown message type:', (message as any).type)
        const errorResponse: WorkerOutgoingMessage = {
          type: 'error',
          message: `Unknown message type: ${(message as any).type}`
        }
        self.postMessage(errorResponse)
      }
    }
  } catch (error) {
    console.error('[Worker] Message handling error:', error)
    const errorResponse: WorkerOutgoingMessage = {
      type: 'error',
      message: `Message handling failed: ${(error as Error).message}`
    }
    self.postMessage(errorResponse)
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
  const errorMessage: WorkerOutgoingMessage = {
    type: 'error',
    message: `Worker uncaught error: ${error.message}`
  }
  self.postMessage(errorMessage)
}

// ============================================================================
// PERFORMANCE MONITORING
// ============================================================================

if (typeof performance !== 'undefined' && (performance as any).memory) {
  setInterval(() => {
    const memory = (performance as any).memory
    const memoryMessage: WorkerOutgoingMessage = {
      type: 'memoryStats',
      memory: {
        usedJSHeapSize: memory.usedJSHeapSize,
        totalJSHeapSize: memory.totalJSHeapSize,
        limit: memory.jsHeapSizeLimit
      }
    }
    self.postMessage(memoryMessage)
  }, 30000) // 30 másodpercenként
}
