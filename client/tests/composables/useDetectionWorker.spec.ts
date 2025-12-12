// tests/composables/useDetectionWorker.spec.ts
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useDetectionWorker } from '@/composables/useDetectionWorker'

// ✅ Mock Web Worker
class MockWorker {
  onmessage: ((event: MessageEvent) => void) | null = null
  postMessage = vi.fn()
  terminate = vi.fn()

  // Simulate worker response
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }))
    }
  }
}

vi.stubGlobal('Worker', MockWorker)

describe('useDetectionWorker', () => {
  let worker: any

  beforeEach(() => {
    worker = new MockWorker()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('initializes worker', () => {
    const { initWorker, isWorkerReady } = useDetectionWorker()

    initWorker()

    expect(isWorkerReady()).toBe(true)
  })

  it('sends detection data to worker', () => {
    const { initWorker, sendDetection } = useDetectionWorker()
    initWorker()

    const testData = JSON.stringify([{ id: 17, Measurement: {} }])
    sendDetection(testData)

    expect(worker.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'processDetection',
        data: testData
      })
    )
  })

  it('receives processed detection from worker', () => {
    const { initWorker, onWorkerMessage } = useDetectionWorker()
    initWorker()

    const mockCallback = vi.fn()
    onWorkerMessage('processedDetection', mockCallback)

    // Simulate worker response
    worker.simulateMessage({
      type: 'processedDetection',
      detection: { id: 1 },
      uavId: 17
    })

    expect(mockCallback).toHaveBeenCalledWith(
      expect.objectContaining({
        detection: { id: 1 },
        uavId: 17
      })
    )
  })

  it('terminates worker on cleanup', () => {
    const { initWorker, terminateWorker } = useDetectionWorker()
    initWorker()

    terminateWorker()

    expect(worker.terminate).toHaveBeenCalled()
  })
})