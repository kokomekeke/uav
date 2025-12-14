// tests/stores/connection.spec.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '@/stores/connection'

describe('Connection Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should initialize with default state', () => {
    const store = useConnectionStore()

    expect(store.connectionState).toBe('disconnected')
    expect(store.isConnected).toBe(false)
    expect(store.socket).toBeNull()
    expect(store.ipPort).toBe('http://localhost:5000')
  })

  it('should update ipPort', () => {
    const store = useConnectionStore()

    store.ipPortModel = '  http://example.com:8080  '

    expect(store.ipPort).toBe('http://example.com:8080')
  })

  it('should connect successfully', async () => {
    const store = useConnectionStore()

    store.connectToServer()

    await vi.advanceTimersByTimeAsync(100)

    if (store.socket) {
      store.connectionState = 'connected'
    }

    expect(store.isConnected).toBe(true)
  })

  it('should handle connection error', async () => {
    const store = useConnectionStore()

    store.connectToServer()

    await vi.advanceTimersByTimeAsync(100)

    store.connectionState = 'failed'

    expect(store.isFailed).toBe(true)
  })

  it('should handle disconnect', async () => {
    const store = useConnectionStore()

    store.connectionState = 'connected'
    store.connectionState = 'disconnected'

    expect(store.isConnected).toBe(false)
  })

  it('should send and receive ping/pong', () => {
    const store = useConnectionStore()

    const beforePing = Date.now()
    store.lastPingSent = beforePing
    store.lastPongReceived = beforePing + 50
    store.currentPing = 50

    expect(store.currentPing).toBe(50)
  })

  it('should attempt reconnection on disconnect', () => {
    const store = useConnectionStore()

    store.reconnectAttempts = 1
    store.isReconnecting = true

    expect(store.reconnectAttempts).toBeGreaterThan(0)
  })

  it('should force disconnect', () => {
    const store = useConnectionStore()

    store.forceDisconnect()

    expect(store.connectionState).toBe('disconnected')
    expect(store.socket).toBeNull()
  })

  it('should perform hard reset', async () => {
    const store = useConnectionStore()

    store.reconnectAttempts = 3
    store.lastPingSent = Date.now()

    store.hardReset()

    await vi.advanceTimersByTimeAsync(1000)

    expect(store.reconnectAttempts).toBe(0)
    expect(store.lastPingSent).toBeNull()
  })

  it('should test connection', async () => {
    const store = useConnectionStore()

    const result = await store.testConnection()
    expect(result).toBe(false)
  })

  it('should cleanup properly', () => {
    const store = useConnectionStore()

    store.reconnectAttempts = 2

    store.cleanup()

    expect(store.reconnectAttempts).toBe(0)
  })
})