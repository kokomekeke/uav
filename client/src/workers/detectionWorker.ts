// workers/detectionWorker.ts - OPTIMALIZÁLT VERZIÓ
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
  mean_azimuth?: number
  mean_elevation?: number
  roi_id?: number
  bandwidth?: number
  strength?: number
  snr?: number
}

interface HeadingData {
  latitude?: number
  longitude?: number
  altitude?: number
  heading?: number
  gpsLat?: number
  gpsLon?: number
}

interface MeasurementData {
  time?: number
  stream_id?: number
  config_id?: number
  source_time?: number
  packet_id?: number
  position?: number
  quaternion?: number[]
  overflow?: boolean
  peaks?: number[]
  heading_data?: HeadingData
  headingData?: HeadingData | string
  sampleIndex?: number
  data?: any[]
  detection?: DetectionItem[]
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
  | { type: 'newDetection'; detection: string; timestamp?: number }
  | { type: 'updateSettings'; samplingRate?: number; maxLatencyMs?: number }
  | { type: 'clearDetections' }
  | { type: 'getStats' }
  | { type: 'terminate' }

type WorkerOutgoingMessage =
  | { type: 'processedDetection'; detection: Detection; uavId: number; timestamp: number }
  | { type: 'processedMeasurement'; measurement: MeasurementData; uavId: number; timestamp: number } // ✅ ÚJ!
  | { type: 'processedTelemetry'; telemetry: any; uavId: number; timestamp: number } // ✅ ÚJ (opcionális)
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

// ✅ OBJECT POOL - Újrahasználható Detection objektumok
const DETECTION_POOL_SIZE = 50
const detectionPool: Detection[] = []
let poolIndex = 0

// ✅ Inicializálás: pool létrehozása
for (let i = 0; i < DETECTION_POOL_SIZE; i++) {
  detectionPool.push({
    timestamp: 0,
    frequency: 0,
    azimuth: 0,
    elevation: 0,
    meanAzimuth: 0,
    meanElevation: 0,
    coordinate: [0, 0],
    quaternion: { q0: 1, q1: 0, q2: 0, q3: 0 },
    heading: 0,
    gpsLat: 0,
    gpsLon: 0,
    altitude: 0,
    roi_id: null
  })
}

// ============================================================================
// HELPER FUNCTIONS - ✅ OPTIMALIZÁLT
// ============================================================================

/**
 * ✅ OPTIMALIZÁLT: Koordináta számítás (jelenleg identity function)
 */
function calculateCoordinate (
  azimuth: number,
  elevation: number,
  gpsLat: number,
  gpsLon: number,
  altitude: number,
  outCoord: [number, number]
): void {
  // A matematikailag korrigált verzió ki van kommentelve
  // Most egyszerűen visszaadjuk a GPS koordinátákat
  outCoord[0] = gpsLat
  outCoord[1] = gpsLon
}

/**
 * ✅ OPTIMALIZÁLT: Quaternion alapú heading (inline math)
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
 * ✅ OPTIMALIZÁLT: Detection objektum pool-ból, mutáció
 */
function getDetectionFromPool (
  detectionItem: DetectionItem,
  gpsLat: number,
  gpsLon: number,
  altitude: number,
  quaternion: Quaternion,
  heading: number,
  timestamp: number
): Detection {
  // ✅ Pool-ból vesszük a következő objektumot (circular)
  const detection = detectionPool[poolIndex]
  poolIndex = (poolIndex + 1) % DETECTION_POOL_SIZE

  // ✅ Mutáljuk az objektumot (ne új allokáció)
  detection.timestamp = timestamp
  detection.frequency = detectionItem.frequency
  detection.azimuth = detectionItem.azimuth ?? 0
  detection.elevation = detectionItem.elevation ?? 0
  detection.meanAzimuth = detectionItem.mean_azimuth ?? 0
  detection.meanElevation = detectionItem.mean_elevation ?? 0
  detection.roi_id = detectionItem.roi_id ?? null

  // ✅ Koordináta számítás in-place
  calculateCoordinate(
    detection.azimuth,
    detection.elevation,
    gpsLat,
    gpsLon,
    altitude,
    detection.coordinate
  )

  // ✅ Quaternion mutáció
  detection.quaternion.q0 = quaternion.q0
  detection.quaternion.q1 = quaternion.q1
  detection.quaternion.q2 = quaternion.q2
  detection.quaternion.q3 = quaternion.q3

  detection.heading = heading
  detection.gpsLat = gpsLat
  detection.gpsLon = gpsLon
  detection.altitude = altitude

  return detection
}

/**
 * ✅ OPTIMALIZÁLT: Data type detektálás (inline)
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
// MAIN PROCESSING FUNCTION - ✅ OPTIMALIZÁLT
// ============================================================================

function processRawDetection (detectionData: string): void {
  const t0_processStart = performance.now()
  const currentTime = Date.now()

  // ✅ Sampling rate ellenőrzés
  if (samplingRate > 0 && currentTime - lastSampleTime < samplingRate) {
    return
  }
  lastSampleTime = currentTime

  if (!detectionData) {
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
  let spectrumCount = 0

  for (let i = 0; i < parsed.length; i++) {
    const item = parsed[i]
    const backendUavId = item.id

    if (!uavIds.includes(backendUavId)) continue

    const dataType = detectDataType(item)

    // ✅ TELEMETRY kezelése
    if (dataType === DataType.TELEMETRY && item.Telemetry) {
      const telemetryMessage: WorkerOutgoingMessage = {
        type: 'processedTelemetry',
        telemetry: item.Telemetry,
        uavId: backendUavId,
        timestamp: currentTime
      }
      self.postMessage(telemetryMessage)
      continue
    }

    // ✅ MEASUREMENT kezelése
    if (dataType !== DataType.MEASUREMENT) continue

    const measurement = item.Measurement
    if (!measurement) continue

    // ✅ 1. SPEKTRUM ADATOK - array access!
    if (measurement.data && Array.isArray(measurement.data) && measurement.data.length > 0) {
      const dataItem = measurement.data[0] // ✅ Első elem

      if (dataItem.dataType === 'FLOAT16') {
        const measurementMessage: WorkerOutgoingMessage = {
          type: 'processedMeasurement',
          measurement, // ✅ Teljes measurement
          uavId: backendUavId,
          timestamp: measurement.time || currentTime
        }

        self.postMessage(measurementMessage)
        spectrumCount++

        // ✅ Ritkább logging
        if (spectrumCount % 50 === 0) {
          console.log(`[Worker] 📊 Sent ${spectrumCount} spectrum measurements`)
        }
      }
    }

    // ✅ 2. DETECTION feldolgozása
    if (!measurement.detection || measurement.detection.length === 0) continue

    let headingData: HeadingData
    if (typeof measurement.headingData === 'string') {
      try {
        headingData = JSON.parse(measurement.headingData)
      } catch {
        headingData = {}
      }
    } else {
      headingData = measurement.headingData || {}
    }

    if (headingData.gpsLat === undefined || headingData.gpsLon === undefined) {
      continue
    }

    const gpsLat = headingData.gpsLat
    const gpsLon = headingData.gpsLon
    const altitude = headingData.altitude ?? 100.0

    const quaternionArray = measurement.quaternion || []
    let q0 = 1; let q1 = 0; let q2 = 0; let q3 = 0

    if (Array.isArray(quaternionArray) && quaternionArray.length === 4) {
      [q0, q1, q2, q3] = quaternionArray
    }

    const quaternion: Quaternion = { q0, q1, q2, q3 }
    const heading = getHeadingFromQuaternion(q0, q1, q2, q3)
    const timestamp = performance.now()

    const detections = measurement.detection
    for (let j = 0; j < detections.length; j++) {
      const detectionItem = detections[j]

      try {
        const detection = getDetectionFromPool(
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
    }
  }

  const processingTime = performance.now() - t0_processStart
  stats.lastProcessingTime = processingTime
  stats.avgProcessingTime = (stats.avgProcessingTime * 0.9) + (processingTime * 0.1)

  if (processedCount > 0 && stats.totalProcessed % 100 === 0) {
    console.log(
      `[Worker] ✅ Processed ${stats.totalProcessed} detections + ${spectrumCount} spectrum | ` +
      `Last batch in ${processingTime.toFixed(2)}ms`
    )
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
        // Silent mode - ne spameljük a console-t
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
  version: '6.0-optimized-pool'
}
self.postMessage(initMessage)
console.log('✅ Detection Worker v6.0 initialized - OPTIMIZED with Object Pool')

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
// PERFORMANCE MONITORING - ✅ RITKÁBB (30s helyett 60s)
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
  }, 60000) // ✅ 60s helyett 30s
}
