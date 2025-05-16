// detectionWorker.js - Web Worker implementáció
// A workers mappában helyezd el

// Memória-hatékony interface a detekciókhoz
interface Comint {
  coordinate: [number, number];
  azimuth: number;
  uavId: number;
  timestamp: number;
}

// Feldolgozás változói
let detectionBuffer = []
let processThrottle = 100 // ms
let samplingRate = 20
let lastProcessTime = 0
let processingTimer = null

// Statisztikák
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0
}

// Feldolgozó függvény
function processDetectionBuffer () {
  if (detectionBuffer.length === 0) return

  const processStart = performance.now()

  try {
    // Minden samplingRatedik elemet tart csak meg
    const lastTimestampsByUav = {}

    function isSampled (detection) {
      const now = detection.timestamp
      const last = lastTimestampsByUav[detection.uavId] || 0

      if (now - last >= samplingRate) {
        lastTimestampsByUav[detection.uavId] = now
        return true
      }
      return false
    }

    const newDetections = detectionBuffer.filter(isSampled)
    stats.totalProcessed += newDetections.length

    if (newDetections.length > 0) {
      const detectionsByUavId = {}

      for (const det of newDetections) {
        if (!detectionsByUavId[det.uavId]) {
          detectionsByUavId[det.uavId] = []
        }
        detectionsByUavId[det.uavId].push(det)
      }

      // Küldjük vissza a feldolgozott adatokat a fő szálnak
      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats
      })
    }

    // Buffer ürítése
    detectionBuffer = []
  } catch (e) {
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
  // Megállítjuk a korábbi időzítőt, ha van
  if (processingTimer) {
    clearInterval(processingTimer)
  }

  // Új időzítő indítása
  processingTimer = setInterval(() => {
    if (detectionBuffer.length > 0) {
      processDetectionBuffer()
    }
  }, processThrottle * 2)
}

// Üzenetek fogadása a fő száltól
self.onmessage = function (e) {
  const message = e.data

  switch (message.type) {
    case 'newDetection':
      // Új detekció hozzáadása a bufferhez
      // detection: {
      //   coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
      //   azimuth: parsed.lob_azim_deg,
      //   uavId: parsed.uav_id,
      //   timestamp: Date.now()
      // },
      // maxSize: detectionSize.value
      const parsed = JSON.parse(message.value)
      const detection = {
        coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
        azimuth: parsed.lob_azim_deg,
        uavId: parsed.uav_id,
        timestamp: Date.now()
      }
      detectionBuffer.push(detection)
      stats.totalReceived++

      // Feldolgozás throttling-gal
      const now = Date.now()
      if (now - lastProcessTime > processThrottle) {
        processDetectionBuffer()
        lastProcessTime = now
      }
      break

    case 'updateSettings':
      // Beállítások frissítése
      if (message.samplingRate !== undefined) {
        samplingRate = message.samplingRate
      }
      if (message.processThrottle !== undefined) {
        processThrottle = message.processThrottle
        // Újraindítjuk az időzítőt az új értékkel
        startAutoProcessing()
      }
      break

    case 'clearDetections':
      // Detekciók törlése
      detectionBuffer = []
      stats = {
        totalReceived: 0,
        totalProcessed: 0,
        lastProcessingTime: 0
      }
      self.postMessage({
        type: 'statsUpdated',
        stats
      })
      break
  }
}

// Automatikus feldolgozás indítása
startAutoProcessing()

// Értesítjük a fő szálat, hogy a worker elindult
self.postMessage({
  type: 'workerStarted'
})
