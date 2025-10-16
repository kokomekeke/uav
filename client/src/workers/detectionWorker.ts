// detectionWorker.js - TELJES, JAVÍTOTT VERZIÓ
// Optimized detection worker for real-time UAV tracking

// --- CONFIGURATION ---
const BATCH_SIZE = 1;
const MAX_BUFFER_SIZE = 20;
const PROCESSING_INTERVAL = 10;
const MEMORY_CLEANUP_THRESHOLD = 100;

// --- STATE MANAGEMENT ---
const detectionBuffer = [];
let assignedUavId = null;
let isProcessing = false;
let processingTimer = null;
let samplingRate = 0;
let lastSampleTime = 0;

// --- PERFORMANCE TRACKING ---
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  totalDropped: 0,
  lastProcessingTime: 0,
  averageProcessingTime: 0,
  bufferSize: 0,
  memoryUsage: 0
};

// --- OBJECT POOLING ---
const detectionPool = [];
const POOL_SIZE = 100;

function getPooledDetection() {
  return detectionPool.pop() || {};
}

function returnToPool(detection) {
  if (detectionPool.length < POOL_SIZE) {
    for (const key in detection) {
      delete detection[key];
    }
    detectionPool.push(detection);
  }
}

// --- BATCH PROCESSING ---
function processBatch() {
  if (isProcessing || detectionBuffer.length === 0) return;

  isProcessing = true;
  const startTime = performance.now();

  try {
    const batchSize = Math.min(BATCH_SIZE, detectionBuffer.length);
    const batch = detectionBuffer.splice(0, batchSize);

    // Group by UAV ID
    const detectionsByUavId = {};
    if (assignedUavId && batch.length > 0) {
      detectionsByUavId[assignedUavId] = batch;
    }

    // Update statistics
    stats.totalProcessed += batch.length;
    stats.bufferSize = detectionBuffer.length;
    stats.memoryUsage = detectionBuffer.length + detectionPool.length;

    // Send processed batch
    if (batch.length > 0) {
      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats: { ...stats },
        timestamp: Date.now()
      });
    }

    // Performance tracking
    const processingTime = performance.now() - startTime;
    stats.lastProcessingTime = processingTime;
    stats.averageProcessingTime =
      stats.averageProcessingTime === 0
        ? processingTime
        : (stats.averageProcessingTime * 0.8) + (processingTime * 0.2);

  } catch (error) {
    console.error('Batch processing error:', error);
    self.postMessage({
      type: 'error',
      message: 'Processing error: ' + error.message,
      timestamp: Date.now()
    });
  } finally {
    isProcessing = false;
    if (detectionBuffer.length > 0) {
      scheduleNextBatch();
    }
  }
}

function scheduleNextBatch() {
  if (processingTimer) return;

  const urgentProcessing = detectionBuffer.length >= MAX_BUFFER_SIZE;
  const delay = urgentProcessing ? 0 : PROCESSING_INTERVAL;

  processingTimer = setTimeout(() => {
    processingTimer = null;
    processBatch();
  }, delay);
}

// --- OPTIMIZED DETECTION CREATION ---
function createOptimizedDetection(detectionItem, headingData, index, currentTimestamp) {
  const detection = getPooledDetection();

  // GPS coordinates
  detection.coordinate = [headingData.gpsLat, headingData.gpsLon];
  detection.azimuth = detectionItem.azimuth || 0;
  detection.elevation = detectionItem.elevation || 0;
  detection.uavId = assignedUavId;
  detection.timestamp = currentTimestamp + index;

  // Optional properties
  if (detectionItem.frequency) detection.frequency = detectionItem.frequency;
  if (headingData.altitude) detection.altitude = headingData.altitude;
  if (headingData.gpsTime) detection.gpsTime = headingData.gpsTime;

  // Quaternion data from new format
  if (headingData.quaternion && Array.isArray(headingData.quaternion)) {
    detection.quaternion = {
      q0: headingData.quaternion[0] || 0,
      q1: headingData.quaternion[1] || 0,
      q2: headingData.quaternion[2] || 0,
      q3: headingData.quaternion[3] || 0
    };
  }

  // ROI information
  if (detectionItem.roi_id !== undefined) {
    detection.roi_id = detectionItem.roi_id;
  } else {
    detection.roi_id = null;
  }

  return detection;
}

// --- MAIN DETECTION PROCESSING ---
function processRawDetection(measurementData) {
  const currentTime = Date.now();

  // Sampling rate control
  if (currentTime - lastSampleTime < samplingRate) {
    stats.totalDropped++;
    return;
  }
  lastSampleTime = currentTime;

  // Validation
  if (!measurementData || typeof measurementData !== 'object') {
    console.warn('Invalid detection format: not an object');
    return;
  }

  // NEW FORMAT: Measurement object
  if (!measurementData.headingData) {
    console.warn('Invalid detection format: missing headingData', measurementData);
    return;
  }

  if (!measurementData.detection || !Array.isArray(measurementData.detection)) {
    console.warn('Invalid detection format: missing or invalid detection array');
    return;
  }

  const headingData = measurementData.headingData;

  // GPS validation
  if (headingData.gpsLat == null || headingData.gpsLon == null) {
    console.warn('Missing GPS coordinates');
    return;
  }

  // Auto-assign UAV ID if not set
  if (!assignedUavId) {
    assignedUavId = 1; // Default
    self.postMessage({
      type: 'uavIdAssigned',
      uavId: assignedUavId
    });
  }

  // Process all detections in the batch
  const currentTimestamp = currentTime;
  measurementData.detection.forEach((detectionItem, index) => {
    const detection = createOptimizedDetection(
      detectionItem,
      headingData,
      index,
      currentTimestamp
    );

    detectionBuffer.push(detection);
    stats.totalReceived++;
  });

  // Memory management
  if (detectionBuffer.length > MEMORY_CLEANUP_THRESHOLD) {
    const excessCount = detectionBuffer.length - MAX_BUFFER_SIZE;
    const removed = detectionBuffer.splice(0, excessCount);
    removed.forEach(returnToPool);
    stats.totalDropped += excessCount;
  }

  // Schedule processing
  if (!isProcessing) {
    scheduleNextBatch();
  }
}

// --- MESSAGE HANDLER ---
self.onmessage = function(e) {
  const message = e.data;

  switch (message.type) {
    case 'newDetection':
      // JAVÍTÁS: Ha explicit UAV ID van, használd azt
      if (message.uavId !== undefined && !assignedUavId) {
        assignedUavId = message.uavId;
        console.log(`Worker auto-assigned to UAV ${assignedUavId}`);
      }
      // A value már Measurement object, nem kell parse-olni
      processRawDetection(message.value);
      break;

    case 'updateSettings':
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId;
      }
      if (message.samplingRate !== undefined) {
        samplingRate = Math.max(10, message.samplingRate);
      }
      self.postMessage({
        type: 'settingsUpdated',
        settings: {
          uavId: assignedUavId,
          samplingRate,
          bufferSize: detectionBuffer.length
        }
      });
      break;

    case 'clearDetections':
      detectionBuffer.forEach(returnToPool);
      detectionBuffer.length = 0;
      stats = {
        totalReceived: 0,
        totalProcessed: 0,
        totalDropped: 0,
        lastProcessingTime: 0,
        averageProcessingTime: 0,
        bufferSize: 0,
        memoryUsage: 0
      };
      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      });
      break;

    case 'getStats':
      stats.bufferSize = detectionBuffer.length;
      stats.memoryUsage = detectionBuffer.length + detectionPool.length;
      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      });
      break;

    case 'pause':
      if (processingTimer) {
        clearTimeout(processingTimer);
        processingTimer = null;
      }
      isProcessing = false;
      break;

    case 'resume':
      if (detectionBuffer.length > 0 && !isProcessing) {
        scheduleNextBatch();
      }
      break;

    case 'terminate':
      if (processingTimer) {
        clearTimeout(processingTimer);
      }
      detectionBuffer.forEach(returnToPool);
      detectionBuffer.length = 0;
      detectionPool.length = 0;
      self.close();
      break;

    default:
      console.warn('Unknown message type:', message.type);
  }
};

// --- INITIALIZATION ---
self.postMessage({
  type: 'workerStarted',
  timestamp: Date.now(),
  version: '2.1-measurement-complete'
});

console.log('Detection worker v2.1 initialized - TELJES VERZIÓ');
