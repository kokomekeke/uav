import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '@/stores/connection'

/* ============================================================================
 * 🔌 socket.io-client MOCK (deterministic)
 * ============================================================================
 */
const socketEventMap: Record<string, Function> = {}

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    id: 'mock-socket-id',
    connected: false,

    on: vi.fn((event: string, cb: Function) => {
      socketEventMap[event] = cb
    }),

    off: vi.fn(),

    emit: vi.fn(),

    connect: vi.fn(() => {
      if (socketEventMap.connect) {
        socketEventMap.connect()
      }
    }),

    disconnect: vi.fn(() => {
      if (socketEventMap.disconnect) {
        socketEventMap.disconnect('io client disconnect')
      }
    })
  }))
}))

/* ============================================================================
 * 🧪 TEST SUITE
 * ============================================================================
 */
describe('ConnectionStore', () => {
  let store: ReturnType<typeof useConnectionStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useConnectionStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    store.cleanup()
    vi.clearAllMocks()
  })

  /* ------------------------------------------------------------------------
   * INITIAL STATE
   * ------------------------------------------------------------------------
   */
  it('should have correct initial state', () => {
    expect(store.connectionState).toBe('disconnected')
    expect(store.isConnected).toBe(false)
    expect(store.reconnectAttempts).toBe(0)
  })

  /* ------------------------------------------------------------------------
   * connectToServer
   * ------------------------------------------------------------------------
   */
  describe('connectToServer()', () => {
    it('should successfully connect to server', async () => {
      const result = await store.connectToServer()

      expect(result).toBe(true)
      expect(store.connectionState).toBe('connected')
      expect(store.socket?.id).toBe('mock-socket-id')
    })

    it('should handle connection timeout', async () => {
      vi.useFakeTimers()

      const promise = store.connectToServer()
      vi.advanceTimersByTime(16000)

      await promise

      expect(store.connectionState).toBe('failed')
      vi.useRealTimers()
    })

    it('should not connect if already connecting', async () => {
      store.connectionState = 'connecting'
      const spy = vi.spyOn(store, 'connectToServer')

      await store.connectToServer()

      expect(spy).toHaveBeenCalledTimes(1)
    })
  })

  /* ------------------------------------------------------------------------
   * manualReconnect
   * ------------------------------------------------------------------------
   */
  describe('manualReconnect()', () => {
    it('should reset reconnect attempts and reconnect', async () => {
      store.reconnectAttempts = 3
      store.connectionState = 'failed'

      const spy = vi.spyOn(store, 'connectToServer')

      await store.manualReconnect()

      expect(store.reconnectAttempts).toBe(0)
      expect(spy).toHaveBeenCalled()
    })
  })

  /* ------------------------------------------------------------------------
   * disconnect
   * ------------------------------------------------------------------------
   */
  it('should force disconnect and cleanup socket', () => {
    store.connectionState = 'connected'
    store.forceDisconnect()

    expect(store.connectionState).toBe('disconnected')
    expect(store.socket).toBeNull()
  })

  /* ------------------------------------------------------------------------
   * cleanup
   * ------------------------------------------------------------------------
   */
  it('should cleanup all resources', () => {
    store.reconnectAttempts = 5
    store.cleanup()

    expect(store.reconnectAttempts).toBe(0)
    expect(store.socket).toBeNull()
  })
})
