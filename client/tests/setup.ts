import { afterEach, beforeEach, vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
  fillStyle: '',
  fillRect: vi.fn(),
  clearRect: vi.fn(),
  getImageData: vi.fn(() => ({
    data: new Uint8ClampedArray(4)
  })),
  putImageData: vi.fn(),
  createImageData: vi.fn(() => []),
  setTransform: vi.fn(),
  drawImage: vi.fn(),
  save: vi.fn(),
  restore: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  closePath: vi.fn(),
  stroke: vi.fn(),
  translate: vi.fn(),
  scale: vi.fn(),
  rotate: vi.fn(),
  arc: vi.fn(),
  fill: vi.fn(),
  measureText: vi.fn(() => ({ width: 0 })),
  transform: vi.fn(),
  rect: vi.fn(),
  clip: vi.fn()
})) as any

global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}))

global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  root: null,
  rootMargin: '',
  thresholds: []
}))


export class MockSocket {
  connected = false
  id = 'mock-socket-id'
  private listeners = new Map<string, Function[]>()

  connect() {
    this.connected = true
    this.emit('connect')
    return this
  }

  disconnect() {
    this.connected = false
    this.emit('disconnect', 'io client disconnect')
    return this
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event)!.push(callback)
    return this
  }

  once(event: string, callback: Function) {
    const wrappedCallback = (...args: any[]) => {
      callback(...args)
      this.off(event, wrappedCallback)
    }
    return this.on(event, wrappedCallback)
  }

  off(event: string, callback?: Function) {
    if (!callback) {
      this.listeners.delete(event)
    } else {
      const callbacks = this.listeners.get(event) || []
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    }
    return this
  }

  emit(event: string, ...args: any[]) {
    const callbacks = this.listeners.get(event) || []
    callbacks.forEach(callback => callback(...args))
    return this
  }

  removeAllListeners() {
    this.listeners.clear()
    return this
  }
}

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => new MockSocket())
}))


export class MockEventSource {
  url: string
  readyState = 0
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2

  constructor(url: string) {
    this.url = url
    this.readyState = MockEventSource.CONNECTING
  }

  close() {
    this.readyState = MockEventSource.CLOSED
  }

  simulateOpen() {
    this.readyState = MockEventSource.OPEN
    if (this.onopen) {
      this.onopen(new Event('open'))
    }
  }

  simulateMessage(data: string) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }))
    }
  }

  simulateError() {
    this.readyState = MockEventSource.CLOSED
    if (this.onerror) {
      this.onerror(new Event('error'))
    }
  }
}

global.EventSource = MockEventSource as any


export class MockWorker {
  url: string
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: ErrorEvent) => void) | null = null
  private listeners = new Map<string, Function[]>()

  constructor(url: string | URL) {
    this.url = url.toString()
  }

  postMessage(message: any) {
    setTimeout(() => {
      if (message.type === 'uavIds') {
        this.simulateMessage({ type: 'uavIdsUpdated', uavIds: message.uavIds })
      }
    }, 0)
  }

  addEventListener(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event)!.push(callback)
  }

  removeEventListener(event: string, callback: Function) {
    const callbacks = this.listeners.get(event) || []
    const index = callbacks.indexOf(callback)
    if (index > -1) {
      callbacks.splice(index, 1)
    }
  }

  terminate() {
    this.listeners.clear()
  }

  simulateMessage(data: any) {
    const event = new MessageEvent('message', { data })
    if (this.onmessage) {
      this.onmessage(event)
    }
    const callbacks = this.listeners.get('message') || []
    callbacks.forEach(callback => callback(event))
  }

  simulateError(error: Error) {
    const event = new ErrorEvent('error', { error, message: error.message })
    if (this.onerror) {
      this.onerror(event)
    }
  }
}

global.Worker = MockWorker as any


global.fetch = vi.fn()

export const mockFetch = (response: any, ok = true) => {
  (global.fetch as any).mockResolvedValueOnce({
    ok,
    status: ok ? 200 : 400,
    json: async () => response,
    text: async () => JSON.stringify(response)
  })
}

vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => ({
      setView: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      remove: vi.fn(),
      getBounds: vi.fn(() => ({
        contains: vi.fn(() => true)
      }))
    })),
    tileLayer: vi.fn(() => ({
      addTo: vi.fn()
    })),
    marker: vi.fn(() => ({
      addTo: vi.fn(),
      bindPopup: vi.fn()
    })),
    polyline: vi.fn(() => ({
      addTo: vi.fn()
    })),
    circleMarker: vi.fn(() => ({
      addTo: vi.fn(),
      bindPopup: vi.fn()
    })),
    divIcon: vi.fn(() => ({})),
    latLng: vi.fn((lat, lon) => ({ lat, lon }))
  }
}))


vi.mock('leaflet.heat', () => ({
  default: {
    heatLayer: vi.fn(() => ({
      addTo: vi.fn(),
      setLatLngs: vi.fn(),
      redraw: vi.fn(),
      remove: vi.fn()
    }))
  }
}))


vi.mock('@vue-leaflet/vue-leaflet', () => ({
  LMap: { name: 'LMap', template: '<div class="l-map-stub"></div>' },
  LTileLayer: { name: 'LTileLayer', template: '<div></div>' },
  LMarker: { name: 'LMarker', template: '<div></div>' },
  LPolyline: { name: 'LPolyline', template: '<div></div>' },
  LCircleMarker: { name: 'LCircleMarker', template: '<div></div>' },
  LPopup: { name: 'LPopup', template: '<div></div>' }
}))


vi.mock('@vueuse/core', () => ({
  useIntervalFn: vi.fn((callback, interval) => ({
    pause: vi.fn(),
    resume: vi.fn()
  })),
  useThrottleFn: vi.fn((fn) => fn)
}))


beforeEach(() => {
  const pinia = createPinia()
  setActivePinia(pinia)

  vi.clearAllMocks()

  if (global.fetch) {
    (global.fetch as any).mockReset()
  }
})

afterEach(() => {
  vi.clearAllTimers()
})


config.global.stubs = {
  teleport: true,
  'router-link': true
}