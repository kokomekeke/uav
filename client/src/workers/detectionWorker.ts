// detectionWorker.js - Optimalizált verzió memory leak és teljesítmény javításokkal
// detectionWorker.js - Frissített verzió JSON parsing-gal
let detectionBuffer = []
let processThrottle = 100 // ms
let samplingRate = 20
let lastProcessTime = 0
let processingTimer = null
let assignedUavId = null // Melyik UAV-hoz tartozik ez a worker

// Statisztikák
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0
}

// Feldolgozó függvény
function processDetectionBuffer () {
  console.log('Processing buffer, length:', detectionBuffer.length)

  if (detectionBuffer.length === 0) return

  const processStart = performance.now()

  try {
    // Csak a megadott mintavételezési rátának megfelelő elemeket tartja meg
    let lastTimestamp = 0

    function isSampled (detection) {
      const now = detection.timestamp

      if (now - lastTimestamp >= samplingRate) {
        lastTimestamp = now
        return true
      }
      return false
    }

    const newDetections = detectionBuffer.filter(isSampled)
    console.log('Sampled detections:', newDetections.length)

    stats.totalProcessed += newDetections.length

    if (newDetections.length > 0) {
      const detectionsByUavId = {}
      detectionsByUavId[assignedUavId] = newDetections

      console.log('Sending processed detections for UAV:', assignedUavId)

      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats: { ...stats }
      })
    }

    // Buffer ürítése
    detectionBuffer = []
  } catch (e) {
    console.error('Processing error:', e)
    self.postMessage({
      type: 'error',
      message: 'Hiba a detekciók feldolgozása során: ' + e.message
    })
  } finally {
    stats.lastProcessingTime = performance.now() - processStart
  }
}

// Időzítő indítása a buffer automatikus feldolgozásához
function startAutoProcessing () {
  console.log('Starting auto processing for UAV:', assignedUavId)

  // Megállítjuk a korábbi időzítőt, ha van
  if (processingTimer !== null) {
    clearInterval(processingTimer)
    processingTimer = null
    console.log('Previous processing timer cleared')
  }

  // Új időzítő indítása
  processingTimer = setInterval(() => {
    if (detectionBuffer.length > 0) {
      console.log('Timer triggered, processing buffer')
      processDetectionBuffer()
    }
  }, processThrottle * 2)

  console.log('New processing timer started with throttle:', processThrottle * 2)
}

// Raw detekció feldolgozása JSON string-ből
function processRawDetection (rawJsonString) {
  try {
    const parsed = JSON.parse(rawJsonString)
    console.log('Parsed raw detection:', parsed)

    if (!assignedUavId && parsed.uav_id) {
      assignedUavId = parsed.uav_id
      console.log('Auto-assigned UAV ID:', assignedUavId)
      self.postMessage({
        type: 'uavIdAssigned',
        uavId: assignedUavId
      })
    }

    if (parsed.uav_id === assignedUavId) {
      if (parsed.uav_pos_lat == null || parsed.uav_pos_lon == null) {
        console.warn('Missing coordinates in detection:', parsed)
        return
      }

      const detection = {
        coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
        azimuth: parsed.lob_azim_deg || 0,
        uavId: parsed.uav_id,
        roi_id: parsed.roi_id || null,
        timestamp: Date.now(),

        // További mezők
        elevation: parsed.lob_elev_deg || null,
        signal_strength: parsed.signal_strength || null,
        frequency: parsed.frequency || null,
        bandwidth: parsed.bandwidth || null,
        snr: parsed.snr || null,
        precision: parsed.precision || null,

        // Quaternion komponensek
        quaternion: {
          q0: parsed.uav_pos_q0 || null,
          q1: parsed.uav_pos_q1 || null,
          q2: parsed.uav_pos_q2 || null,
          q3: parsed.uav_pos_q3 || null
        },

        // UAV pozíció magasság
        altitude: parsed.uav_pos_altitude || null
      }

      detectionBuffer.push(detection)
      stats.totalReceived++

      console.log('Added detection to buffer:', detection)

      // Feldolgozás throttling-gal
      const now = Date.now()
      if (now - lastProcessTime > processThrottle) {
        processDetectionBuffer()
        lastProcessTime = now
      }
    } else {
      console.log(`Skipping detection for UAV ${parsed.uav_id}, worker assigned to UAV ${assignedUavId}`)
    }
  } catch (e) {
    console.error('JSON parsing error:', e)
    self.postMessage({
      type: 'error',
      message: 'Hiba a JSON feldolgozása során: ' + e.message + ' - Raw data: ' + rawJsonString.substring(0, 100)
    })
  }
}

// Üzenetek fogadása a fő száltól
self.onmessage = function (e) {
  const message = e.data
  console.log('Worker received message:', message.type)

  switch (message.type) {
    case 'newDetection':
      // Most már raw JSON string-et várunk
      if (typeof message.value === 'string') {
        processRawDetection(message.value)
      } else {
        console.error('Expected string, got:', typeof message.value)
        self.postMessage({
          type: 'error',
          message: 'Hibás adatformátum: string helyett ' + typeof message.value + ' érkezett'
        })
      }
      break

    case 'updateSettings':
      console.log('Updating settings:', message)

      // Beállítások frissítése és UAV ID megadása
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId
        console.log('UAV ID set to:', assignedUavId)
      }

      if (message.samplingRate !== undefined) {
        samplingRate = message.samplingRate
        console.log('Sampling rate set to:', samplingRate)
      }

      if (message.processThrottle !== undefined) {
        processThrottle = message.processThrottle
        console.log('Process throttle set to:', processThrottle)
        // Újraindítjuk az időzítőt az új értékkel
        startAutoProcessing()
      }

      // Beállítások visszaigazolása
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
      console.log('Clearing detections')

      // Detekciók törlése
      detectionBuffer = []
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
      // Statisztikák lekérése
      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      })
      break

    case 'terminate':
      console.log('Terminating worker and clearing timer...')
      if (processingTimer !== null) {
        clearInterval(processingTimer)
        processingTimer = null
      }
      self.close()
      break
  }
}

// Automatikus feldolgozás indítása
startAutoProcessing()

// Értesítjük a fő szálat, hogy a worker elindult
self.postMessage({
  type: 'workerStarted',
  timestamp: Date.now()
})

console.log('Detection worker initialized')
