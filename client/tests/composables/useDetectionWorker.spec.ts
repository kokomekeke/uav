import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useDetectionWorker } from '@/composables/useDetectionWorker'

describe('useDetectionWorker', () => {
  let mockWorker: any
  let postMessageSpy: any
  let terminateSpy: any
  let workerInstance: any
  let workerConstructorSpy: any

  beforeEach(() => {
    vi.clearAllMocks()

    postMessageSpy = vi.fn()
    terminateSpy = vi.fn()
    workerConstructorSpy = vi.fn()

    global.Worker = class MockWorker {
      postMessage = postMessageSpy
      terminate = terminateSpy
      onmessage: any = null
      onerror: any = null

      constructor(url: any, options?: any) {
        workerConstructorSpy(url, options)
        workerInstance = this
        mockWorker = this
      }
    } as any
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()

    const { terminateWorker } = useDetectionWorker()
    terminateWorker()
  })

  describe('initWorker', () => {
    it('should initialize worker instance', () => {
      const { initWorker, isWorkerReady } = useDetectionWorker()

      const worker = initWorker()

      expect(worker).toBeDefined()
      expect(isWorkerReady()).toBe(true)
      expect(workerConstructorSpy).toHaveBeenCalledTimes(1)
    })

    it('should return same instance on multiple calls (singleton)', () => {
      const { initWorker } = useDetectionWorker()

      const worker1 = initWorker()
      const worker2 = initWorker()

      expect(worker1).toBe(worker2)
      expect(workerConstructorSpy).toHaveBeenCalledTimes(1)
    })

    it('should set up message handler', () => {
      const { initWorker } = useDetectionWorker()

      initWorker()

      expect(mockWorker.onmessage).toBeDefined()
      expect(typeof mockWorker.onmessage).toBe('function')
    })

    it('should set up error handler', () => {
      const { initWorker } = useDetectionWorker()

      initWorker()

      expect(mockWorker.onerror).toBeDefined()
      expect(typeof mockWorker.onerror).toBe('function')
    })
  })

  describe('onWorkerMessage', () => {
    it('should register message handler', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const handler = vi.fn()
      const cleanup = onWorkerMessage('processedDetection', handler)

      // Simulate worker message
      const testData = { detection: { frequency: 100 }, uavId: 1, timestamp: Date.now() }
      mockWorker.onmessage({ data: { type: 'processedDetection', ...testData } })

      expect(handler).toHaveBeenCalledWith(testData)
      expect(typeof cleanup).toBe('function')
    })

    it('should handle multiple handlers for same type', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const handler1 = vi.fn()
      const handler2 = vi.fn()

      onWorkerMessage('processedDetection', handler1)
      onWorkerMessage('processedDetection', handler2)

      const testData = { detection: { frequency: 100 }, uavId: 1, timestamp: Date.now() }
      mockWorker.onmessage({ data: { type: 'processedDetection', ...testData } })

      expect(handler1).toHaveBeenCalledWith(testData)
      expect(handler2).toHaveBeenCalledWith(testData)
    })

    it('should cleanup handler when cleanup function is called', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const handler = vi.fn()
      const cleanup = onWorkerMessage('processedDetection', handler)

      cleanup()

      const testData = { detection: { frequency: 100 }, uavId: 1, timestamp: Date.now() }
      mockWorker.onmessage({ data: { type: 'processedDetection', ...testData } })

      expect(handler).not.toHaveBeenCalled()
    })

    it('should handle errors in message handlers gracefully', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const errorHandler = vi.fn(() => {
        throw new Error('Handler error')
      })
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      onWorkerMessage('processedDetection', errorHandler)

      const testData = { detection: { frequency: 100 }, uavId: 1, timestamp: Date.now() }
      mockWorker.onmessage({ data: { type: 'processedDetection', ...testData } })

      expect(consoleErrorSpy).toHaveBeenCalled()
      consoleErrorSpy.mockRestore()
    })
  })

  describe('postToWorker', () => {
    it('should post message to worker', () => {
      const { initWorker, postToWorker } = useDetectionWorker()
      initWorker()

      const message = { type: 'getStats' as const }
      postToWorker(message)

      expect(postMessageSpy).toHaveBeenCalledWith(message)
    })

    it('should not post if worker not initialized', () => {
      const { postToWorker } = useDetectionWorker()
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      postToWorker({ type: 'getStats' })

      expect(postMessageSpy).not.toHaveBeenCalled()
      expect(consoleErrorSpy).toHaveBeenCalled()
      consoleErrorSpy.mockRestore()
    })
  })

  describe('updateSelectedUavIds', () => {
    it('should send uavIds update message', () => {
      const { initWorker, updateSelectedUavIds } = useDetectionWorker()
      initWorker()

      const uavIds = [1, 2, 3]
      updateSelectedUavIds(uavIds)

      expect(postMessageSpy).toHaveBeenCalledWith({
        type: 'uavIds',
        uavIds
      })
    })
  })

  describe('sendDetection', () => {
    it('should send detection data to worker', () => {
      const { initWorker, sendDetection } = useDetectionWorker()
      initWorker()

      const detectionData = JSON.stringify([{ id: 1, Measurement: {} }])
      sendDetection(detectionData)

      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'newDetection',
          detection: detectionData,
          timestamp: expect.any(Number)
        })
      )
    })
  })

  describe('updateSamplingRate', () => {
    it('should send sampling rate update', () => {
      const { initWorker, updateSamplingRate } = useDetectionWorker()
      initWorker()

      updateSamplingRate(100)

      expect(postMessageSpy).toHaveBeenCalledWith({
        type: 'updateSettings',
        samplingRate: 100
      })
    })
  })

  describe('requestStats', () => {
    it('should request worker stats', () => {
      const { initWorker, requestStats } = useDetectionWorker()
      initWorker()

      requestStats()

      expect(postMessageSpy).toHaveBeenCalledWith({ type: 'getStats' })
    })
  })

  describe('clearDetections', () => {
    it('should send clear detections message', () => {
      const { initWorker, clearDetections } = useDetectionWorker()
      initWorker()

      clearDetections()

      expect(postMessageSpy).toHaveBeenCalledWith({ type: 'clearDetections' })
    })
  })

  describe('terminateWorker', () => {
    it('should terminate worker and cleanup', () => {
      const { initWorker, terminateWorker, isWorkerReady } = useDetectionWorker()
      initWorker()

      expect(isWorkerReady()).toBe(true)

      terminateWorker()

      expect(postMessageSpy).toHaveBeenCalledWith({ type: 'terminate' })
      expect(terminateSpy).toHaveBeenCalled()
      expect(isWorkerReady()).toBe(false)
    })

    it('should handle termination when worker not initialized', () => {
      const { terminateWorker, isWorkerReady } = useDetectionWorker()

      terminateWorker() // Should not throw

      expect(isWorkerReady()).toBe(false)
    })
  })

  describe('isWorkerReady', () => {
    it('should return false before initialization', () => {
      const { isWorkerReady } = useDetectionWorker()

      expect(isWorkerReady()).toBe(false)
    })

    it('should return true after initialization', () => {
      const { initWorker, isWorkerReady } = useDetectionWorker()

      initWorker()

      expect(isWorkerReady()).toBe(true)
    })

    it('should return false after termination', () => {
      const { initWorker, terminateWorker, isWorkerReady } = useDetectionWorker()

      initWorker()
      expect(isWorkerReady()).toBe(true)

      terminateWorker()
      expect(isWorkerReady()).toBe(false)
    })
  })

  describe('worker error handling', () => {
    it('should handle worker errors', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const errorHandler = vi.fn()
      onWorkerMessage('error', errorHandler)

      const error = new ErrorEvent('error', { message: 'Worker error' })
      mockWorker.onerror(error)

      expect(errorHandler).toHaveBeenCalledWith({ message: 'Worker error' })
    })
  })

  describe('message routing', () => {
    it('should route different message types to correct handlers', () => {
      const { initWorker, onWorkerMessage } = useDetectionWorker()
      initWorker()

      const detectionHandler = vi.fn()
      const statsHandler = vi.fn()

      onWorkerMessage('processedDetection', detectionHandler)
      onWorkerMessage('statsUpdated', statsHandler)

      mockWorker.onmessage({ data: { type: 'processedDetection', detection: {}, uavId: 1, timestamp: Date.now() } })
      mockWorker.onmessage({ data: { type: 'statsUpdated', stats: {} } })

      expect(detectionHandler).toHaveBeenCalledTimes(1)
      expect(statsHandler).toHaveBeenCalledTimes(1)
    })

    it('should not log warnings for expected init messages', () => {
      const { initWorker } = useDetectionWorker()
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      initWorker()

      mockWorker.onmessage({ data: { type: 'workerStarted', timestamp: Date.now(), version: '1.0' } })
      mockWorker.onmessage({ data: { type: 'uavIdsUpdated', uavIds: [1, 2] } })

      expect(consoleWarnSpy).not.toHaveBeenCalled()
      consoleWarnSpy.mockRestore()
    })
  })
})