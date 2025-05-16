// detectionWorker.js - UAV-specifikus Web Worker implementáció
// A workers mappában helyezd el

// Memória-hatékony interface a detekciókhoz
// interface Comint {
//   coordinate: [number, number];
//   azimuth: number;
//   uavId: number;
//   timestamp: number;
// }

// Feldolgozás változói
let detectionBuffer = [];
let processThrottle = 100; // ms
let samplingRate = 20;
let lastProcessTime = 0;
let processingTimer = null;
let assignedUavId = null; // Melyik UAV-hoz tartozik ez a worker

// Statisztikák
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  lastProcessingTime: 0
};

// Feldolgozó függvény
function processDetectionBuffer() {
  if (detectionBuffer.length === 0) return;

  const processStart = performance.now();

  try {
    // Csak a megadott mintavételezési rátának megfelelő elemeket tartja meg
    let lastTimestamp = 0;

    function isSampled(detection) {
      const now = detection.timestamp;

      if (now - lastTimestamp >= samplingRate) {
        lastTimestamp = now;
        return true;
      }
      return false;
    }

    const newDetections = detectionBuffer.filter(isSampled);
    stats.totalProcessed += newDetections.length;

    if (newDetections.length > 0) {
      // Az UAV-specifikus worker csak egy UAV-hoz tartozó detekciókkal dolgozik
      const detectionsByUavId = {};
      detectionsByUavId[assignedUavId] = newDetections;

      // Küldjük vissza a feldolgozott adatokat a fő szálnak
      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats
      });
    }

    // Buffer ürítése
    detectionBuffer = [];
  } catch (e) {
    self.postMessage({
      type: 'error',
      message: 'Hiba a detekciók feldolgozása során: ' + e.message
    });
  } finally {
    stats.lastProcessingTime = performance.now() - processStart;
  }
}

// Időzítő indítása a buffer automatikus feldolgozásához
function startAutoProcessing() {
  // Megállítjuk a korábbi időzítőt, ha van
  if (processingTimer) {
    clearInterval(processingTimer);
  }

  // Új időzítő indítása
  processingTimer = setInterval(() => {
    if (detectionBuffer.length > 0) {
      processDetectionBuffer();
    }
  }, processThrottle * 2);
}

// Üzenetek fogadása a fő száltól
self.onmessage = function(e) {
  const message = e.data;

  switch (message.type) {
    case 'newDetection':
      // Csak akkor dolgozzuk fel, ha már ismerjük az UAV ID-t
      if (!assignedUavId) {
        // Ha még nincs beállítva az UAV ID, a JSON-ból próbáljuk kiolvasni
        try {
          const parsed = JSON.parse(message.value);
          assignedUavId = parsed.uav_id;
        } catch (error) {
          console.error('Error parsing message:', error);
          return;
        }
      }

      try {
        const parsed = JSON.parse(message.value);

        // Csak akkor dolgozzuk fel, ha ennek a workernek az UAV ID-jához tartozik
        if (parsed.uav_id === assignedUavId) {
          const detection = {
            coordinate: [parsed.uav_pos_lat, parsed.uav_pos_lon],
            azimuth: parsed.lob_azim_deg,
            uavId: parsed.uav_id,
            timestamp: Date.now()
          };

          detectionBuffer.push(detection);
          stats.totalReceived++;

          // Feldolgozás throttling-gal
          const now = Date.now();
          if (now - lastProcessTime > processThrottle) {
            processDetectionBuffer();
            lastProcessTime = now;
          }
        }
      } catch (e) {
        self.postMessage({
          type: 'error',
          message: 'Hiba a detekció feldolgozása során: ' + e.message
        });
      }
      break;

    case 'updateSettings':
      // Beállítások frissítése és UAV ID megadása
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId;
      }

      if (message.samplingRate !== undefined) {
        samplingRate = message.samplingRate;
      }

      if (message.processThrottle !== undefined) {
        processThrottle = message.processThrottle;
        // Újraindítjuk az időzítőt az új értékkel
        startAutoProcessing();
      }
      break;

    case 'clearDetections':
      // Detekciók törlése
      detectionBuffer = [];
      stats = {
        totalReceived: 0,
        totalProcessed: 0,
        lastProcessingTime: 0
      };

      self.postMessage({
        type: 'statsUpdated',
        stats
      });
      break;
  }
};

// Automatikus feldolgozás indítása
startAutoProcessing();

// Értesítjük a fő szálat, hogy a worker elindult
self.postMessage({
  type: 'workerStarted'
});
