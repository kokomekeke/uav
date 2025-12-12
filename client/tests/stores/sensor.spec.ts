    // tests/stores/sensor.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSensorStore } from '@/stores/sensor'

// ✅ Mock fetch
global.fetch = vi.fn()

describe('useSensorStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initializes with empty sensors', () => {
    const store = useSensorStore()
    expect(store.sensors).toEqual({})
  })

  it('fetches sensors from API', async () => {
    const mockSensors = [
      { uav_id: 17, uav_label: 'UAV 17', active: true },
      { uav_id: 18, uav_label: 'UAV 18', active: false }
    ]

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSensors
    })

    const store = useSensorStore()
    await store.fetchSensors()

    expect(store.sensors[17]).toBeDefined()
    expect(store.sensors[17].uav_label).toBe('UAV 17')
    expect(store.sensors[18]).toBeDefined()
  })

  it('handles fetch error', async () => {
    ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

    const store = useSensorStore()
    await store.fetchSensors()

    expect(store.errorMessage).toBe('Failed to load sensors')
  })

  it('selects sensor', () => {
    const store = useSensorStore()
    store.sensors = {
      17: { uav_id: 17, uav_label: 'Test', active: true, is_selected: false, detections: [] }
    }

    store.selectSensor(17)

    expect(store.sensors[17].is_selected).toBe(true)
  })

  it('adds detection to sensor', () => {
    const store = useSensorStore()
    store.sensors = {
      17: { uav_id: 17, active: true, detections: [] }
    }

    const detection = { timestamp: Date.now(), data: {} }
    store.addDetectionToSensor(17, detection)

    expect(store.sensors[17].detections).toHaveLength(1)
    expect(store.sensors[17].detections[0]).toBe(detection)
  })

  it('respects circular buffer size', () => {
    const store = useSensorStore()
    store.realtimeConfig.circularBufferSize = 3
    store.sensors = {
      17: { uav_id: 17, active: true, detections: [] }
    }

    // Add 5 detections
    for (let i = 0; i < 5; i++) {
      store.addDetectionToSensor(17, { timestamp: Date.now(), id: i })
    }

    // Should only keep last 3
    expect(store.sensors[17].detections).toHaveLength(3)
    expect(store.sensors[17].detections[0].id).toBe(2) // Oldest kept
    expect(store.sensors[17].detections[2].id).toBe(4) // Newest
  })
})