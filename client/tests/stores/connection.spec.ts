// tests/stores/connection.spec.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '@/stores/connection'

// Mock socket.io-client
// tests/__mocks__/socket.ts (vagy inline a spec-ben)
const listeners: Record<string, Function[]> = {}

export const mockSocket = {
  connected: false,
  id: 'mock-socket-id',

  on: vi.fn((event, cb) => {
    listeners[event] ??= []
    listeners[event].push(cb)
  }),

  once: vi.fn((event, cb) => {
    const wrapper = (...args: any[]) => {
      cb(...args)
      listeners[event] = listeners[event].filter(fn => fn !== wrapper)
    }
    listeners[event] ??= []
    listeners[event].push(wrapper)
  }),

  off: vi.fn((event, cb) => {
    if (!listeners[event]) return
    listeners[event] = listeners[event].filter(fn => fn !== cb)
  }),

  emit: vi.fn(),

  connect: vi.fn(() => {
    // SEMMIT nem csinál automatikusan
  }),

  disconnect: vi.fn(() => {
    mockSocket.connected = false
  }),

  removeAllListeners: vi.fn()
}

export const trigger = (event: string, payload?: any) => {
  listeners[event]?.forEach(fn => fn(payload))
}

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket)
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
      const connectPromise = store.connectToServer()

      expect(store.connectionState).toBe('connecting')

      // szimuláljuk a szerver connect-et
      trigger('connect')

      await connectPromise

      expect(store.connectionState).toBe('connected')
    })


    it('should handle connection timeout', async () => {
      const promise = store.connectToServer()

      // CONNECT_TIMEOUT = 15000
      vi.advanceTimersByTime(15000)

      await promise

      // 🔑 a store logikája szerint itt reconnectel
      expect(['failed', 'reconnecting']).toContain(store.connectionState)
      expect(store.isReconnecting).toBe(true)
    })



    it('should track reconnection attempts', async () => {
      store.connectToServer()

      // szimulálunk egy connection hibát
      trigger('connect_error', new Error('fail'))

      // reconnect delay
      vi.advanceTimersByTime(3000)

      expect(store.reconnectAttempts).toBeGreaterThan(0)
      expect(store.isReconnecting).toBe(true)
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
      store.connectToServer()
      store.connectToServer()

      // nem triggerelünk connect-et
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
