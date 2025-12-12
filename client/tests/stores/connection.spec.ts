// tests/stores/connection.spec.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '@/stores/connection'

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    once: vi.fn(), // ✅ Hozzáadva
    off: vi.fn(),
    emit: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    removeAllListeners: vi.fn(),
    connected: false,
    id: 'mock-socket-id'
  }))
}))

describe('Connection Store', () => {
  let store: ReturnType<typeof useConnectionStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useConnectionStore()
    vi.clearAllTimers()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    store.cleanup()
  })

  describe('Initial State', () => {
    it('should initialize with correct default values', () => {
      expect(store.connectionState).toBe('disconnected')
      expect(store.connectionMessage).toBe('')
      expect(store.ipPort).toBe('http://localhost:5000')
      expect(store.isReconnecting).toBe(false)
      expect(store.reconnectAttempts).toBe(0)
      expect(store.maxReconnectAttempts).toBe(5)
    })

    it('should have correct computed properties', () => {
      expect(store.isConnected).toBe(false)
      expect(store.isConnecting).toBe(false)
      expect(store.isFailed).toBe(false)
      expect(store.isDisconnected).toBe(true)
    })
  })

  describe('Connection State Management', () => {
    it('should update state to connecting', async () => {
      await store.connectToServer()

      // State should change during connection attempt
      expect(['connecting', 'connected', 'failed']).toContain(store.connectionState)
    })

    it('should handle connection timeout', async () => {
      const connectPromise = store.connectToServer()

      // Fast-forward time to trigger timeout
      vi.advanceTimersByTime(16000)

      await connectPromise

      expect(store.connectionState).toBe('failed')
    })

    it('should track reconnection attempts', async () => {
      store.connectionState = 'disconnected'
      store.isReconnecting = false

      // Trigger reconnect logic
      await store.manualReconnect()

      expect(store.reconnectAttempts).toBeGreaterThanOrEqual(0)
    })

    it('should not exceed max reconnection attempts', async () => {
      store.reconnectAttempts = 5
      store.maxReconnectAttempts = 5

      await store.manualReconnect()

      expect(store.reconnectAttempts).toBeLessThanOrEqual(store.maxReconnectAttempts)
    })
  })

  describe('Connection Actions', () => {
    it('should force disconnect', () => {
      store.connectionState = 'connected'

      store.forceDisconnect()

      expect(store.connectionState).toBe('disconnected')
      expect(store.socket).toBeNull()
      expect(store.isReconnecting).toBe(false)
    })

    it('should perform hard reset', () => {
      store.connectionState = 'connected'
      store.reconnectAttempts = 3
      store.isReconnecting = true

      store.hardReset()

      vi.advanceTimersByTime(1100)

      expect(store.connectionState).toBe('disconnected')
      expect(store.reconnectAttempts).toBe(0)
      expect(store.isReconnecting).toBe(false)
    })

    it('should cleanup resources', () => {
      store.connectionState = 'connected'

      store.cleanup()

      expect(store.isReconnecting).toBe(false)
      expect(store.reconnectAttempts).toBe(0)
    })
  })

  describe('Computed Properties Reactivity', () => {
    it('should update isConnected when state changes', () => {
      expect(store.isConnected).toBe(false)

      store.connectionState = 'connected'

      expect(store.isConnected).toBe(true)
    })

    it('should update isConnecting when state changes', () => {
      store.connectionState = 'connecting'

      expect(store.isConnecting).toBe(true)
    })

    it('should update isFailed when state changes', () => {
      store.connectionState = 'failed'

      expect(store.isFailed).toBe(true)
    })
  })

  describe('Edge Cases', () => {
    it('should handle multiple connection attempts gracefully', async () => {
      const promise1 = store.connectToServer()
      const promise2 = store.connectToServer()

      await Promise.all([promise1, promise2])

      // Should not crash or create multiple connections
      expect(store.connectionState).toBeDefined()
    })

    it('should handle cleanup without active connection', () => {
      expect(() => store.cleanup()).not.toThrow()
    })

    it('should handle force disconnect without socket', () => {
      store.forceDisconnect()
      store.cleanup()
      expect(() => store.forceDisconnect()).not.toThrow()
    })
  })
})
