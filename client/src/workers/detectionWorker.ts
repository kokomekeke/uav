// detectionWorker.js - Real-time verzió (TELJES KÓD)
// Batch feldolgozás nélkül, azonnali detekció küldés

let assignedUavId = null
let samplingRate = 0
let lastSampleTime = 0

// Statisztikák
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0
}

// Optimalizált detekció létrehozás
function createOptimizedDetection(detectionItem, headingData, timestamp) {
  const detection = {
    coordinate: [headingData.gpsLat, headingData.gpsLon],
    azimuth: detectionItem.azimuth || 0,
    elevation: detectionItem.elevation || 0,
    uavId: assignedUavId,
    timestamp
  }

  if (detectionItem.frequency) detection.frequency = detectionItem.frequency
  if (headingData.altitude) detection.altitude = headingData.altitude
  if (headingData.gpsTime) detection.gpsTime = headingData.gpsTime

  // Quaternion
  if (headingData.quaternion && Array.isArray(headingData.quaternion)) {
    detection.quaternion = {
      q0: headingData.quaternion[0] || 0,
      q1: headingData.quaternion[1] || 0,
      q2: headingData.quaternion[2] || 0,
      q3: headingData.quaternion[3] || 0
    }
  }

  detection.roi_id = detectionItem.roi_id !== undefined ? detectionItem.roi_id : null

  return detection
}

// Azonnali feldolgozás - NINCS BATCH!
function processRawDetection(measurementData) {
  const startTime = performance.now()
  const currentTime = Date.now()

  // Sampling rate ellenőrzés (opcionális)
  if (samplingRate > 0 && currentTime - lastSampleTime < samplingRate) {
    return
  }
  lastSampleTime = currentTime

  // Validáció
  if (!measurementData || typeof measurementData !== 'object') {
    console.warn('Invalid detection format')
    return
  }

  if (!measurementData.headingData) {
    console.warn('Missing headingData')
    return
  }

  if (!measurementData.detection || !Array.isArray(measurementData.detection)) {
    console.warn('Missing or invalid detection array')
    return
  }

  const headingData = measurementData.headingData

  // GPS fallback
  if (headingData.gpsLat == null || headingData.gpsLon == null) {
    headingData.gpsLat = 47.355520
    headingData.gpsLon = 19.268900
  }

  // UAV ID auto-assign
  if (!assignedUavId) {
    assignedUavId = 1
    self.postMessage({
      type: 'uavIdAssigned',
      uavId: assignedUavId
    })
  }

  const timestamp = currentTime

  // ⚡ KRITIKUS: Minden detekciót AZONNAL feldolgozunk és AZONNAL küldünk
  measurementData.detection.forEach((detectionItem) => {
    const detection = createOptimizedDetection(detectionItem, headingData, timestamp)

    stats.totalReceived++
    stats.totalProcessed++

    // ⚡ AZONNAL küldjük vissza - NINCS BUFFER, NINCS VÁRAKOZÁS
    self.postMessage({
      type: 'processedDetection',
      detection,
      uavId: assignedUavId,
      timestamp: Date.now()
    })
  })

  stats.lastProcessingTime = performance.now() - startTime
}

// Message handler
self.onmessage = function(e) {
  const message = e.data

  switch (message.type) {
    case 'newDetection':
      if (message.uavId !== undefined && !assignedUavId) {
        assignedUavId = message.uavId
      }
      // ⚡ AZONNAL feldolgozzuk
      processRawDetection(message.measurement)
      break

    case 'updateSettings':
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId
      }
      if (message.samplingRate !== undefined) {
        samplingRate = Math.max(0, message.samplingRate)
      }
      self.postMessage({
        type: 'settingsUpdated',
        settings: {
          uavId: assignedUavId,
          samplingRate
        }
      })
      break

    case 'clearDetections':
      stats = {
        totalReceived: 0,
        totalProcessed: 0,
        lastProcessingTime: 0
      }
      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      })
      break

    case 'getStats':
      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      })
      break

    case 'terminate':
      self.postMessage({ type: 'terminated' })
      self.close()
      break

    default:
      console.warn('Unknown message type:', message.type)
  }
}

// Inicializálás
self.postMessage({
  type: 'workerStarted',
  timestamp: Date.now(),
  version: '3.0-realtime'
})

console.log('Detection worker v3.0 initialized - REAL-TIME MODE (NO BATCH)')