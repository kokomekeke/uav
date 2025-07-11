// detectionWorker.js - Optimalizált verzió memory leak és teljesítmény javításokkal
// detectionWorker.js - Frissített verzió JSON parsing-gal
let detectionBuffer = []
let processThrottle = 10 // Drastikusan csökkentve 10ms-re
let samplingRate = 1 // Gyakorlatilag minden detekció (1ms)
let lastProcessTime = 0
let assignedUavId = null
let isProcessing = false // Prevent overlapping processes

// Statisztikák
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0
}

// Optimalizált buffer feldolgozás - blocking műveletek nélkül
function processDetectionBuffer() {
  if (isProcessing || detectionBuffer.length === 0) return

  isProcessing = true
  const processStart = performance.now()

  try {
    // Mintavételezés optimalizálva - egyszerű időellenőrzés
    let lastTimestamp = 0
    const newDetections = []

    // Egyszerű loop a filter helyett
    for (let i = 0; i < detectionBuffer.length; i++) {
      const detection = detectionBuffer[i]
      const now = detection.timestamp

      if (now - lastTimestamp >= samplingRate) {
        lastTimestamp = now
        newDetections.push(detection)
      }
    }

    stats.totalProcessed += newDetections.length

    if (newDetections.length > 0) {
      const detectionsByUavId = {}
      detectionsByUavId[assignedUavId] = newDetections

      // Azonnali küldés
      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats: { ...stats }
      })
    }

    // Buffer gyors törlése
    detectionBuffer.length = 0

  } catch (e) {
    console.error('Processing error:', e)
    self.postMessage({
      type: 'error',
      message: 'Processing error: ' + e.message
    })
  } finally {
    stats.lastProcessingTime = performance.now() - processStart
    isProcessing = false
  }
}

// RequestAnimationFrame-based processing for real-time performance
function scheduleProcessing() {
  if (detectionBuffer.length > 0 && !isProcessing) {
    // Használjuk a requestAnimationFrame-et ha elérhető, egyébként setTimeout
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(processDetectionBuffer)
    } else {
      setTimeout(processDetectionBuffer, 0)
    }
  }
}

// Optimalizált raw detekció feldolgozás
function processRawDetection(rawJsonString) {
  try {
    const parsed = JSON.parse(rawJsonString)

    // UAV ID auto-assign optimalizálva
    if (!assignedUavId && parsed.uav_id) {
      assignedUavId = parsed.uav_id
      self.postMessage({
        type: 'uavIdAssigned',
        uavId: assignedUavId
      })
    }

    // Csak saját UAV detekciók feldolgozása
    if (parsed.uav_id !== assignedUavId) return

    // Kötelező koordináták gyors ellenőrzése
    if (parsed.uav_pos_lat == null || parsed.uav_pos_lon == null) return

    // Objektum létrehozás optimalizálva - csak szükséges mezők
    const detection = {
      coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
      azimuth: parsed.lob_azim_deg || 0,
      uavId: parsed.uav_id,
      roi_id: parsed.roi_id || null,
      timestamp: Date.now(),

      // Opcionális mezők csak ha léteznek
      ...(parsed.lob_elev_deg != null && { elevation: parsed.lob_elev_deg }),
      ...(parsed.signal_strength != null && { signal_strength: parsed.signal_strength }),
      ...(parsed.frequency != null && { frequency: parsed.frequency }),
      ...(parsed.bandwidth != null && { bandwidth: parsed.bandwidth }),
      ...(parsed.snr != null && { snr: parsed.snr }),
      ...(parsed.precision != null && { precision: parsed.precision }),
      ...(parsed.uav_pos_altitude != null && { altitude: parsed.uav_pos_altitude }),

      // Quaternion csak ha van érték
      ...((parsed.uav_pos_q0 != null || parsed.uav_pos_q1 != null ||
           parsed.uav_pos_q2 != null || parsed.uav_pos_q3 != null) && {
        quaternion: {
          q0: parsed.uav_pos_q0,
          q1: parsed.uav_pos_q1,
          q2: parsed.uav_pos_q2,
          q3: parsed.uav_pos_q3
        }
      })
    }

    // Buffer-be helyezés
    detectionBuffer.push(detection)
    stats.totalReceived++

    // Azonnali feldolgozás scheduling
    const now = Date.now()
    if (now - lastProcessTime >= processThrottle) {
      processDetectionBuffer()
      lastProcessTime = now
    } else {
      // Kis késleltetéssel schedule-eljük
      scheduleProcessing()
    }

  } catch (e) {
    console.error('JSON parsing error:', e)
    self.postMessage({
      type: 'error',
      message: 'JSON parsing error: ' + e.message
    })
  }
}

// Optimalizált message handler
self.onmessage = function(e) {
  const message = e.data

  switch (message.type) {
    case 'newDetection':
      if (typeof message.value === 'string') {
        processRawDetection(message.value)
      } else {
        self.postMessage({
          type: 'error',
          message: 'Invalid data format: expected string'
        })
      }
      break

    case 'updateSettings':
      // UAV ID beállítása
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId
      }

      // Sampling rate beállítása
      if (message.samplingRate !== undefined) {
        samplingRate = Math.max(1, message.samplingRate) // Minimum 1ms
      }

      // Process throttle beállítása
      if (message.processThrottle !== undefined) {
        processThrottle = Math.max(1, message.processThrottle) // Minimum 1ms
      }

      // Visszaigazolás
      self.postMessage({
        type: 'settingsUpdated',
        settings: {
          uavId: assignedUavId,
          samplingRate,
          processThrottle
        }
      })
      break

    case 'clearDetections':
      // Gyors törlés
      detectionBuffer.length = 0
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
      // Gyors cleanup
      detectionBuffer.length = 0
      self.close()
      break
  }
}

// Worker indítás üzenet
self.postMessage({
  type: 'workerStarted',
  timestamp: Date.now()
})

console.log('Optimized detection worker initialized for real-time performance')