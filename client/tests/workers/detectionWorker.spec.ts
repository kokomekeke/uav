import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const mockSelf = {
  postMessage: vi.fn(),
  close: vi.fn(),
  onmessage: null as any,
  onerror: null as any
}

global.self = mockSelf as any
global.performance = {
  now: vi.fn(() => Date.now()),
  memory: {
    usedJSHeapSize: 1000000,
    totalJSHeapSize: 5000000,
    jsHeapSizeLimit: 10000000
  }
} as any

describe('detectionWorker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSelf.postMessage.mockClear()

    vi.resetModules()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Worker Initialization', () => {
    it('should send workerStarted message on initialization', async () => {
      await import('@/workers/detectionWorker')

      expect(mockSelf.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'workerStarted',
          timestamp: expect.any(Number),
          version: expect.stringContaining('optimized')
        })
      )
    })
  })

  describe('Message Handling', () => {
    it('should update UAV IDs', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      const uavIds = [1, 2, 3]
      mockSelf.onmessage({ data: { type: 'uavIds', uavIds } })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'uavIdsUpdated',
        uavIds
      })
    })

    it('should update settings', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      mockSelf.onmessage({
        data: {
          type: 'updateSettings',
          samplingRate: 100,
          maxLatencyMs: 500
        }
      })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'settingsUpdated',
        settings: {
          samplingRate: 100,
          maxLatencyMs: 500
        }
      })
    })

    it('should clear detections and reset stats', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      mockSelf.onmessage({ data: { type: 'clearDetections' } })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'statsUpdated',
        stats: {
          totalReceived: 0,
          totalProcessed: 0,
          lastProcessingTime: 0,
          avgProcessingTime: 0
        }
      })
    })

    it('should return stats on getStats request', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      mockSelf.onmessage({ data: { type: 'getStats' } })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'statsUpdated',
        stats: expect.objectContaining({
          totalReceived: expect.any(Number),
          totalProcessed: expect.any(Number),
          lastProcessingTime: expect.any(Number),
          avgProcessingTime: expect.any(Number)
        })
      })
    })

    it('should handle terminate message', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      mockSelf.onmessage({ data: { type: 'terminate' } })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({ type: 'terminated' })
      expect(mockSelf.close).toHaveBeenCalled()
    })

    it('should handle unknown message type', async () => {
      await import('@/workers/detectionWorker')
      mockSelf.postMessage.mockClear()

      mockSelf.onmessage({ data: { type: 'unknown' } })

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'error',
        message: expect.stringContaining('Unknown message type')
      })
    })
  })

  describe('Detection Processing', () => {
    it('should process valid detection data', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            time: Date.now(),
            detection: [
              {
                frequency: 2400,
                azimuth: 45,
                elevation: 30,
                mean_azimuth: 45,
                mean_elevation: 30,
                roi_id: 1
              }
            ],
            quaternion: [1, 0, 0, 0],
            headingData: {
              gpsLat: 47.4979,
              gpsLon: 19.0402,
              altitude: 100
            }
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      expect(mockSelf.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'processedDetection',
          detection: expect.objectContaining({
            frequency: 2400,
            azimuth: 45,
            elevation: 30,
            meanAzimuth: 45,
            meanElevation: 30,
            roi_id: 1,
            gpsLat: 47.4979,
            gpsLon: 19.0402,
            altitude: 100
          }),
          uavId: 1,
          timestamp: expect.any(Number)
        })
      )
    })

    it('should ignore detections from non-selected UAVs', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 2, // UAV 2 is not selected
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402 }
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      expect(mockSelf.postMessage).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'processedDetection' })
      )
    })

    it('should skip detections without GPS coordinates', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: {} // No GPS coordinates
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      expect(mockSelf.postMessage).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'processedDetection' })
      )
    })

    it('should process spectrum measurement data', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const spectrumData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            time: Date.now(),
            data: [
              {
                dataType: 'FLOAT16',
                samples: [0.1, 0.2, 0.3]
              }
            ]
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: spectrumData }
      })

      expect(mockSelf.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'processedMeasurement',
          measurement: expect.objectContaining({
            data: expect.arrayContaining([
              expect.objectContaining({
                dataType: 'FLOAT16'
              })
            ])
          }),
          uavId: 1,
          timestamp: expect.any(Number)
        })
      )
    })

    it('should process telemetry data', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const telemetryData = JSON.stringify([
        {
          id: 1,
          Telemetry: {
            battery: 80,
            temperature: 25
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: telemetryData }
      })

      expect(mockSelf.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'processedTelemetry',
          telemetry: expect.objectContaining({
            battery: 80,
            temperature: 25
          }),
          uavId: 1,
          timestamp: expect.any(Number)
        })
      )
    })

    it('should handle multiple detections in one message', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [
              { frequency: 2400, azimuth: 45, elevation: 30 },
              { frequency: 2450, azimuth: 50, elevation: 35 }
            ],
            quaternion: [1, 0, 0, 0],
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402, altitude: 100 }
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      const detectionCalls = mockSelf.postMessage.mock.calls.filter(
        call => call[0].type === 'processedDetection'
      )

      expect(detectionCalls.length).toBe(2)
      expect(detectionCalls[0][0].detection.frequency).toBe(2400)
      expect(detectionCalls[1][0].detection.frequency).toBe(2450)
    })

    it('should handle JSON parse errors gracefully', async () => {
      await import('@/workers/detectionWorker')
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: 'invalid json' }
      })

      expect(consoleErrorSpy).toHaveBeenCalled()
      consoleErrorSpy.mockRestore()
    })

    it('should calculate heading from quaternion', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            quaternion: [0.924, 0, 0, 0.383], // ~45 degrees
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402, altitude: 100 }
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      const call = mockSelf.postMessage.mock.calls.find(
        call => call[0].type === 'processedDetection'
      )

      expect(call[0].detection.heading).toBeGreaterThan(0)
      expect(call[0].detection.heading).toBeLessThan(360)
    })
  })

  describe('Sampling Rate', () => {
    it('should respect sampling rate throttling', async () => {
      await import('@/workers/detectionWorker')

      // Set sampling rate to 1000ms
      mockSelf.onmessage({
        data: { type: 'updateSettings', samplingRate: 1000 }
      })

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402 }
          }
        }
      ])

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      const firstCallCount = mockSelf.postMessage.mock.calls.length

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: detectionData }
      })

      const secondCallCount = mockSelf.postMessage.mock.calls.length

      expect(secondCallCount).toBe(firstCallCount)
    })
  })

  describe('Object Pool', () => {
    it('should reuse detection objects from pool', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            quaternion: [1, 0, 0, 0],
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402, altitude: 100 }
          }
        }
      ])

      for (let i = 0; i < 10; i++) {
        mockSelf.onmessage({
          data: { type: 'newDetection', detection: detectionData }
        })
      }

      const detectionCalls = mockSelf.postMessage.mock.calls.filter(
        call => call[0].type === 'processedDetection'
      )

      detectionCalls.forEach(call => {
        expect(call[0].detection).toHaveProperty('frequency')
        expect(call[0].detection).toHaveProperty('coordinate')
        expect(call[0].detection).toHaveProperty('quaternion')
        expect(call[0].detection.coordinate).toHaveLength(2)
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle worker errors', async () => {
      await import('@/workers/detectionWorker')

      const error = new ErrorEvent('error', { message: 'Test error' })
      mockSelf.onerror(error)

      expect(mockSelf.postMessage).toHaveBeenCalledWith({
        type: 'error',
        message: expect.stringContaining('Test error')
      })
    })

    it('should catch and report processing errors', async () => {
      await import('@/workers/detectionWorker')

      mockSelf.onmessage({ data: { type: 'uavIds', uavIds: [1] } })
      mockSelf.postMessage.mockClear()

      const invalidData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [null],
            headingData: { gpsLat: 47.4979, gpsLon: 19.0402 }
          }
        }
      ])

      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      mockSelf.onmessage({
        data: { type: 'newDetection', detection: invalidData }
      })

      expect(consoleErrorSpy).toHaveBeenCalled()
      consoleErrorSpy.mockRestore()
    })
  })
})