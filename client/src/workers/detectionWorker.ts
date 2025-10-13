// Optimized detection worker for real-time UAV tracking
// Works with the hybrid Vue component approach

// --- CONFIGURATION ---
const BATCH_SIZE = 5 // Smaller batches for smoother real-time updates
const MAX_BUFFER_SIZE = 50 // Prevent memory buildup
const PROCESSING_INTERVAL = 100 // ms - fast processing for real-time feel
const MEMORY_CLEANUP_THRESHOLD = 1000

// --- STATE MANAGEMENT ---
const detectionBuffer = []
const processedCount = 0
let assignedUavId = null
let isProcessing = false
let processingTimer = null
let samplingRate = 50 // ms between samples
let lastSampleTime = 0

// --- PERFORMANCE TRACKING ---
let stats = {
  totalReceived: 0,
  totalProcessed: 0,
  totalDropped: 0,
  lastProcessingTime: 0,
  averageProcessingTime: 0,
  bufferSize: 0,
  memoryUsage: 0
}

// --- OBJECT POOLING FOR MEMORY EFFICIENCY ---
const detectionPool = []
const POOL_SIZE = 100

function getPooledDetection () {
  return detectionPool.pop() || {}
}

function returnToPool (detection) {
  if (detectionPool.length < POOL_SIZE) {
    // Clear all properties efficiently
    for (const key in detection) {
      delete detection[key]
    }
    detectionPool.push(detection)
  }
}

// --- OPTIMIZED BATCH PROCESSING ---
function processBatch () {
  if (isProcessing || detectionBuffer.length === 0) return

  isProcessing = true
  const startTime = performance.now()

  try {
    // Process smaller batches for smoother performance
    const batchSize = Math.min(BATCH_SIZE, detectionBuffer.length)
    const batch = detectionBuffer.splice(0, batchSize)

    // Group by UAV ID for efficient processing
    const detectionsByUavId = {}

    if (assignedUavId && batch.length > 0) {
      detectionsByUavId[assignedUavId] = batch
    }

    // Update statistics
    stats.totalProcessed += batch.length
    stats.bufferSize = detectionBuffer.length
    stats.memoryUsage = detectionBuffer.length + detectionPool.length

    // Send processed batch immediately for real-time updates
    if (batch.length > 0) {
      self.postMessage({
        type: 'processedDetections',
        detectionsByUavId,
        stats: { ...stats },
        timestamp: Date.now()
      })
    }

    // Performance tracking
    const processingTime = performance.now() - startTime
    stats.lastProcessingTime = processingTime

    // Exponential moving average for smoother performance metrics
    stats.averageProcessingTime = stats.averageProcessingTime === 0
      ? processingTime
      : (stats.averageProcessingTime * 0.8) + (processingTime * 0.2)
  } catch (error) {
    console.error('Batch processing error:', error)
    self.postMessage({
      type: 'error',
      message: 'Processing error: ' + error.message,
      timestamp: Date.now()
    })
  } finally {
    isProcessing = false

    // Schedule next batch if buffer has data
    if (detectionBuffer.length > 0) {
      scheduleNextBatch()
    }
  }
}

// --- INTELLIGENT SCHEDULING ---
function scheduleNextBatch () {
  if (processingTimer) return

  // Immediate processing for critical buffer size
  const urgentProcessing = detectionBuffer.length >= MAX_BUFFER_SIZE
  const delay = urgentProcessing ? 0 : PROCESSING_INTERVAL

  processingTimer = setTimeout(() => {
    processingTimer = null
    processBatch()
  }, delay)
}

// --- OPTIMIZED DETECTION CREATION ---
function createOptimizedDetection (detectionItem, headingData, index, currentTimestamp) {
  const detection = getPooledDetection()

  // Only essential properties for performance
  detection.coordinate = [headingData.gpsLat, headingData.gpsLon]
  detection.azimuth = detectionItem.azimuth || 0
  detection.elevation = detectionItem.elevation || 0
  detection.uavId = assignedUavId
  detection.timestamp = currentTimestamp + index

  // Optional properties (only if available)
  if (detectionItem.frequency) detection.frequency = detectionItem.frequency
  if (headingData.altitude) detection.altitude = headingData.altitude
  if (headingData.gpsTime) detection.gpsTime = headingData.gpsTime

  // Quaternion data for heading calculation
  if (headingData.quaternion && Array.isArray(headingData.quaternion)) {
    detection.quaternion = {
      q0: headingData.quaternion[0] || 0,
      q1: headingData.quaternion[1] || 0,
      q2: headingData.quaternion[2] || 0,
      q3: headingData.quaternion[3] || 0
    }
  }

  // ROI information for color coding
  if (detectionItem.roi_id !== undefined) {
    detection.roi_id = detectionItem.roi_id
  }

  return detection
}

// --- MAIN DETECTION PROCESSING ---
function processRawDetection (rawJsonString) {
  const currentTime = Date.now()

  // Sampling rate control - drop samples if too frequent
  if (currentTime - lastSampleTime < samplingRate) {
    stats.totalDropped++
    return
  }
  lastSampleTime = currentTime

  let parsedData
  try {
    // Handle different input formats
    parsedData = typeof rawJsonString === 'string' ? JSON.parse(rawJsonString) : rawJsonString

    // Handle double-encoded JSON
    if (typeof parsedData === 'string') {
      parsedData = JSON.parse(parsedData)
    }
  } catch (e) {
    console.error('JSON parsing error:', e)
    self.postMessage({
      type: 'error',
      message: 'JSON parsing error: ' + e.message
    })
    return
  }

  // Validate parsed data structure
  if (!parsedData || typeof parsedData !== 'object') {
    console.warn('Invalid detection format: not an object')
    return
  }

  if (!parsedData.headingData) {
    console.warn('Invalid detection format: missing headingData')
    return
  }

  if (!parsedData.detection || !Array.isArray(parsedData.detection)) {
    console.warn('Invalid detection format: missing or invalid detection array')
    return
  }

  const headingData = parsedData.headingData

  // Validate GPS coordinates
  if (headingData.gpsLat == null || headingData.gpsLon == null) {
    console.warn('Missing GPS coordinates')
    return
  }

  // Auto-assign UAV ID if not set
  if (!assignedUavId) {
    assignedUavId = 1 // Default UAV ID
    self.postMessage({
      type: 'uavIdAssigned',
      uavId: assignedUavId
    })
  }

  // Process all detections in the batch
  const currentTimestamp = currentTime

  parsedData.detection.forEach((detectionItem, index) => {
    const detection = createOptimizedDetection(
      detectionItem,
      headingData,
      index,
      currentTimestamp
    )

    detectionBuffer.push(detection)
    stats.totalReceived++
  })

  // Memory management - prevent buffer overflow
  if (detectionBuffer.length > MEMORY_CLEANUP_THRESHOLD) {
    const excessCount = detectionBuffer.length - MAX_BUFFER_SIZE
    const removed = detectionBuffer.splice(0, excessCount)

    // Return removed detections to pool
    removed.forEach(returnToPool)
    stats.totalDropped += excessCount
  }

  // Schedule processing
  if (!isProcessing) {
    scheduleNextBatch()
  }
}

// --- MESSAGE HANDLER ---
self.onmessage = function (e) {
  const message = e.data

  switch (message.type) {
    case 'newDetection':
      if (typeof message.value === 'string') {
        processRawDetection(JSON.parse(message.value))
      } else if (typeof message.value === 'object') {
        processRawDetection(message.value)
      } else {
        self.postMessage({
          type: 'error',
          message: 'Invalid data format: expected object or string'
        })
      }
      break

    case 'updateSettings':
      // Update UAV ID
      if (message.uavId !== undefined) {
        assignedUavId = message.uavId
      }

      // Update sampling rate
      if (message.samplingRate !== undefined) {
        samplingRate = Math.max(10, message.samplingRate) // Minimum 10ms
      }

      // Confirm settings update
      self.postMessage({
        type: 'settingsUpdated',
        settings: {
          uavId: assignedUavId,
          samplingRate,
          bufferSize: detectionBuffer.length
        }
      })
      break

    case 'clearDetections':
      // Return all detections to pool
      detectionBuffer.forEach(returnToPool)
      detectionBuffer.length = 0

      // Reset statistics
      stats = {
        totalReceived: 0,
        totalProcessed: 0,
        totalDropped: 0,
        lastProcessingTime: 0,
        averageProcessingTime: 0,
        bufferSize: 0,
        memoryUsage: 0
      }

      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      })
      break

    case 'getStats':
      stats.bufferSize = detectionBuffer.length
      stats.memoryUsage = detectionBuffer.length + detectionPool.length

      self.postMessage({
        type: 'statsUpdated',
        stats: { ...stats }
      })
      break

    case 'pause':
      // Stop processing without clearing data
      if (processingTimer) {
        clearTimeout(processingTimer)
        processingTimer = null
      }
      isProcessing = false
      break

    case 'resume':
      // Resume processing
      if (detectionBuffer.length > 0 && !isProcessing) {
        scheduleNextBatch()
      }
      break

    case 'terminate':
      // Clean shutdown
      if (processingTimer) {
        clearTimeout(processingTimer)
      }

      detectionBuffer.forEach(returnToPool)
      detectionBuffer.length = 0
      detectionPool.length = 0

      self.close()
      break

    default:
      console.warn('Unknown message type:', message.type)
  }
}

// --- INITIALIZATION ---
self.postMessage({
  type: 'workerStarted',
  timestamp: Date.now(),
  version: '2.0-optimized'
})

console.log('Optimized detection worker v2.0 initialized for real-time UAV tracking')
