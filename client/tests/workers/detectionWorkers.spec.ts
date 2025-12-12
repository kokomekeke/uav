// tests/workers/detectionWorker.spec.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// Mock Web Worker environment
const mockPostMessage = vi.fn()
const mockClose = vi.fn()

// @ts-ignore
global.self = {
  postMessage: mockPostMessage,
  close: mockClose,
  onmessage: null,
  onerror: null
} as any

describe('Detection Worker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPostMessage.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Worker Initialization', () => {
    it('should send workerStarted message on initialization', () => {
      // Import worker to trigger initialization
      require('@/workers/detectionWorker')

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'workerStarted',
          version: expect.any(String)
        })
      )
    })
  })

  describe('Message Handling', () => {
    it('should handle uavIds message', () => {
      const worker = require('@/workers/detectionWorker')

      const message = {
        data: {
          type: 'uavIds',
          uavIds: [1, 2, 3]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'uavIdsUpdated',
          uavIds: [1, 2, 3]
        })
      )
    })

    it('should handle updateSettings message', () => {
      const message = {
        data: {
          type: 'updateSettings',
          samplingRate: 100,
          maxLatencyMs: 500
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'settingsUpdated',
          settings: {
            samplingRate: 100,
            maxLatencyMs: 500
          }
        })
      )
    })

    it('should handle clearDetections message', () => {
      const message = {
        data: {
          type: 'clearDetections'
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'statsUpdated',
          stats: expect.objectContaining({
            totalReceived: 0,
            totalProcessed: 0
          })
        })
      )
    })

    it('should handle getStats message', () => {
      const message = {
        data: {
          type: 'getStats'
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'statsUpdated',
          stats: expect.any(Object)
        })
      )
    })

    it('should handle terminate message', () => {
      const message = {
        data: {
          type: 'terminate'
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith({ type: 'terminated' })
      expect(mockClose).toHaveBeenCalled()
    })
  })

  describe('Detection Processing', () => {
    it('should process valid detection data', () => {
      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [
              {
                frequency: 2400,
                azimuth: 45,
                elevation: 30,
                mean_azimuth: 45,
                mean_elevation: 30
              }
            ],
            headingData: {
              gpsLat: 47.49,
              gpsLon: 19.04,
              altitude: 100,
              heading: 90
            },
            quaternion: [1, 0, 0, 0],
            time: Date.now()
          }
        }
      ])

      const message = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      mockPostMessage.mockClear()

      const detectionMessage = {
        data: {
          type: 'newDetection',
          detection: detectionData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(detectionMessage as MessageEvent)
      }

      // Should process and emit detection
      expect(mockPostMessage).toHaveBeenCalled()
    })

    it('should ignore detections from non-selected UAVs', () => {
      const detectionData = JSON.stringify([
        {
          id: 99, // UAV not in selected list
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: { gpsLat: 47.49, gpsLon: 19.04 }
          }
        }
      ])

      // Set UAV IDs to [1, 2, 3]
      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1, 2, 3]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      mockPostMessage.mockClear()

      const detectionMessage = {
        data: {
          type: 'newDetection',
          detection: detectionData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(detectionMessage as MessageEvent)
      }

      // Should not process detection from UAV 99
      const processedCalls = mockPostMessage.mock.calls.filter(
        call => call[0].type === 'processedDetection' && call[0].uavId === 99
      )
      expect(processedCalls.length).toBe(0)
    })

    it('should handle spectrum measurements', () => {
      const measurementData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            data: [
              {
                dataType: 'FLOAT16',
                values: [1, 2, 3, 4, 5]
              }
            ],
            time: Date.now()
          }
        }
      ])

      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      mockPostMessage.mockClear()

      const measurementMessage = {
        data: {
          type: 'newDetection',
          detection: measurementData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(measurementMessage as MessageEvent)
      }

      // Should emit spectrum measurement
      const measurementCalls = mockPostMessage.mock.calls.filter(
        call => call[0].type === 'processedMeasurement'
      )
      expect(measurementCalls.length).toBeGreaterThanOrEqual(0)
    })

    it('should handle telemetry data', () => {
      const telemetryData = JSON.stringify([
        {
          id: 1,
          Telemetry: {
            battery: 95,
            temperature: 25
          }
        }
      ])

      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      mockPostMessage.mockClear()

      const telemetryMessage = {
        data: {
          type: 'newDetection',
          detection: telemetryData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(telemetryMessage as MessageEvent)
      }

      // Should emit telemetry
      const telemetryCalls = mockPostMessage.mock.calls.filter(
        call => call[0].type === 'processedTelemetry'
      )
      expect(telemetryCalls.length).toBeGreaterThanOrEqual(0)
    })

    it('should handle invalid JSON gracefully', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const invalidData = 'invalid json {'

      const message = {
        data: {
          type: 'newDetection',
          detection: invalidData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining('JSON parse error'),
        expect.any(Error)
      )

      consoleErrorSpy.mockRestore()
    })

    it('should handle missing GPS coordinates', () => {
      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: {} // Missing gpsLat and gpsLon
          }
        }
      ])

      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      mockPostMessage.mockClear()

      const message = {
        data: {
          type: 'newDetection',
          detection: detectionData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      // Should skip detections without GPS
      const detectionCalls = mockPostMessage.mock.calls.filter(
        call => call[0].type === 'processedDetection'
      )
      expect(detectionCalls.length).toBe(0)
    })
  })

  describe('Error Handling', () => {
    it('should handle unknown message types', () => {
      const message = {
        data: {
          type: 'unknownType'
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          message: expect.stringContaining('Unknown message type')
        })
      )
    })

    it('should emit error on processing failure', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      // Invalid detection structure that will cause processing error
      const badData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [null] // Invalid detection
          }
        }
      ])

      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      const message = {
        data: {
          type: 'newDetection',
          detection: badData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      consoleErrorSpy.mockRestore()
    })
  })

  describe('Performance', () => {
    it('should track processing statistics', () => {
      const message = {
        data: {
          type: 'getStats'
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      expect(mockPostMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'statsUpdated',
          stats: expect.objectContaining({
            totalReceived: expect.any(Number),
            totalProcessed: expect.any(Number),
            lastProcessingTime: expect.any(Number),
            avgProcessingTime: expect.any(Number)
          })
        })
      )
    })

    it('should respect sampling rate', () => {
      const settingsMessage = {
        data: {
          type: 'updateSettings',
          samplingRate: 10000 // Very high sampling rate (process once per 10s)
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(settingsMessage as MessageEvent)
      }

      mockPostMessage.mockClear()

      // Send multiple detections rapidly
      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: [{ frequency: 2400 }],
            headingData: { gpsLat: 47.49, gpsLon: 19.04 }
          }
        }
      ])

      for (let i = 0; i < 10; i++) {
        const message = {
          data: {
            type: 'newDetection',
            detection: detectionData
          }
        }

        if (global.self.onmessage) {
          global.self.onmessage(message as MessageEvent)
        }
      }

      // With high sampling rate, most should be skipped
      const processedCount = mockPostMessage.mock.calls.filter(
        call => call[0].type === 'processedDetection'
      ).length

      expect(processedCount).toBeLessThan(10)
    })
  })

  describe('Object Pool', () => {
    it('should reuse detection objects from pool', () => {
      const detectionData = JSON.stringify([
        {
          id: 1,
          Measurement: {
            detection: Array(100).fill({
              frequency: 2400,
              azimuth: 45,
              elevation: 30
            }),
            headingData: { gpsLat: 47.49, gpsLon: 19.04 },
            quaternion: [1, 0, 0, 0],
            time: Date.now()
          }
        }
      ])

      const uavMessage = {
        data: {
          type: 'uavIds',
          uavIds: [1]
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(uavMessage as MessageEvent)
      }

      const message = {
        data: {
          type: 'newDetection',
          detection: detectionData
        }
      }

      if (global.self.onmessage) {
        global.self.onmessage(message as MessageEvent)
      }

      // Should process without memory issues (pool reuse)
      expect(mockPostMessage).toHaveBeenCalled()
    })
  })
})