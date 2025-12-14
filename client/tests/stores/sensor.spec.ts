// tests/stores/sensor.spec.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSensorStore } from '@/stores/sensor'
import { useConnectionStore } from '@/stores/connection'
import { mockFetch } from '../setup'

describe('Sensor Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with default state', () => {
    const store = useSensorStore()

    expect(store.sensors).toEqual({})
    expect(store.selectedSensor).toBeNull()
    expect(store.isLoading).toBe(false)
  })

  it('should compute correct stream URL', () => {
    const connectionStore = useConnectionStore()
    connectionStore.ipPort = 'http://localhost:5000'

    const store = useSensorStore()

    expect(store.streamUrl).toContain('stream/comint_detection')
  })

  it('should fetch sensors successfully', async () => {
    const mockSensors = [
      {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true
      }
    ]

    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    mockFetch(mockSensors)

    const store = useSensorStore()
    await store.fetchSensors()

    expect(Object.keys(store.sensors).length).toBeGreaterThan(0)
  })

  it('should not fetch when disconnected', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'disconnected'

    const store = useSensorStore()
    await store.fetchSensors()

    expect(store.errorMessage).toBe('Not connected to server')
  })

  it('should handle fetch error', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    mockFetch({ error: 'Failed' }, false)

    const store = useSensorStore()
    await store.fetchSensors()

    expect(store.errorMessage).toBe('Failed to load sensors')
  })

  it('should select sensor', () => {
    const store = useSensorStore()

    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    store.selectSensor(1)

    expect(store.sensors[1].is_selected).toBe(true)
  })

  it('should set current sensor', () => {
    const store = useSensorStore()
    const sensor = {
      uav_id: 1,
      uav_label: 'UAV-1',
      uav_address: '192.168.1.100',
      active: true,
      is_selected: false,
      detections: []
    } as any

    store.setCurrentSensor(sensor)

    expect(store.selectedSensor).toEqual(sensor)
  })

  it('should initialize stream when connected', () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'

    const store = useSensorStore()
    store.initializeStream()

    expect(store.isStreamConnected).toBeDefined()
  })

  it('should not initialize stream when disconnected', () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'disconnected'

    const store = useSensorStore()
    store.initializeStream()

    expect(store.isStreamConnected).toBe(false)
  })

  it('should disconnect stream', () => {
    const store = useSensorStore()
    store.disconnectStream()

    expect(store.isStreamConnected).toBe(false)
  })

  it('should add detection to sensor', () => {
    const store = useSensorStore()

    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    const detection = {
      timestamp: Date.now(),
      frequency: 2400
    }

    store.addDetectionToSensor(1, detection)

    expect(store.sensors[1].detections.length).toBe(1)
  })

  it('should limit detections by buffer size', () => {
    const store = useSensorStore()
    store.realtimeConfig.circularBufferSize = 3

    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    for (let i = 0; i < 5; i++) {
      store.addDetectionToSensor(1, {
        timestamp: Date.now() + i,
        frequency: 2400 + i
      })
    }

    expect(store.sensors[1].detections.length).toBeLessThanOrEqual(3)
  })

  it('should clear all detections', () => {
    const store = useSensorStore()

    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        detections: [{ timestamp: Date.now() }]
      } as any
    }

    store.clearDetections()

    expect(store.sensors[1].detections.length).toBe(0)
  })

  it('should remove sensor successfully', async () => {
    const connectionStore = useConnectionStore()
    connectionStore.connectionState = 'connected'
    connectionStore.ipPort = 'http://localhost:5000'

    mockFetch({ success: true })

    const store = useSensorStore()
    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        uav_address: '192.168.1.100',
        active: true,
        is_selected: false,
        detections: []
      } as any
    }

    await store.removeSensor(1)

    expect(store.sensors[1]).toBeUndefined()
  })

  it('should update realtime config', () => {
    const store = useSensorStore()

    store.updateRealtimeConfig({
      maxLatencyMs: 500
    })

    expect(store.realtimeConfig.maxLatencyMs).toBe(500)
  })

  it('should compute selected sensors correctly', () => {
    const store = useSensorStore()

    store.sensors = {
      1: {
        uav_id: 1,
        uav_label: 'UAV-1',
        is_selected: true,
        detections: []
      } as any,
      2: {
        uav_id: 2,
        uav_label: 'UAV-2',
        is_selected: false,
        detections: []
      } as any
    }

    expect(store.selectedSensors.length).toBe(1)
    expect(store.hasSelectedSensors).toBe(true)
  })
})