// composables/useDetectionWorker.ts
import type {
  WorkerStats,
  WorkerOutgoingMessage,
  WorkerIncomingMessage
} from '@/types/worker'

// Worker singleton instance
let workerInstance: Worker | null = null
let messageHandlers = new Map<string, Set<(data: any) => void>>()
let isInitialized = false

export function useDetectionWorker () {
  /**
   * Inicializálja a Worker instance-t (singleton pattern)
   */
  const initWorker = (): Worker => {
    console.log('initialize worker')
    if (workerInstance && isInitialized) {
      console.log('[WorkerManager] Worker already initialized')
      return workerInstance
    }

    try {
      // TypeScript worker import Vite-tal
      workerInstance = new Worker(
        new URL('@/workers/detectionWorker.ts', import.meta.url),
        { type: 'module' }
      )

      // Központi message handler
      workerInstance.onmessage = (e: MessageEvent<WorkerOutgoingMessage>) => {
        const { type, ...data } = e.data

        const handlers = messageHandlers.get(type)

        if (handlers && handlers.size > 0) {
          handlers.forEach(handler => {
            try {
              handler(data)
            } catch (error) {
              console.error(`[WorkerManager] Handler error for type "${type}":`, error)
            }
          })
        } else if (type !== 'workerStarted' && type !== 'uavIdsUpdated') {
          // Ne logoljuk az init üzeneteket
          console.warn(`[WorkerManager] No handlers registered for message type: ${type}`)
        }
      }

      workerInstance.onerror = (error: ErrorEvent) => {
        console.error('[WorkerManager] Worker error:', error)
        const errorHandlers = messageHandlers.get('error')
        if (errorHandlers) {
          errorHandlers.forEach(handler => {
            handler({ message: error.message })
          })
        }
      }

      isInitialized = true
      console.log('✅ Detection Worker Manager initialized')

      return workerInstance
    } catch (error) {
      console.error('[WorkerManager] Failed to initialize worker:', error)
      throw error
    }
  }

  /**
   * Feliratkozás worker üzenetekre
   */
  const onWorkerMessage = <T = any>(
    type: string,
    handler: (data: T) => void
  ): (() => void) => {
    if (!messageHandlers.has(type)) {
      messageHandlers.set(type, new Set())
    }
    messageHandlers.get(type)!.add(handler)

    // Cleanup function
    return () => {
      const handlers = messageHandlers.get(type)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          messageHandlers.delete(type)
        }
      }
    }
  }

  /**
   * Üzenet küldése a workernek
   */
  const postToWorker = (message: WorkerIncomingMessage): void => {
    if (!workerInstance || !isInitialized) {
      console.error('[WorkerManager] Worker not initialized. Call initWorker() first.')
      return
    }

    try {
      workerInstance.postMessage(message)
    } catch (error) {
      console.error('[WorkerManager] Failed to post message:', error)
    }
  }

  /**
   * Kiválasztott UAV ID-k frissítése
   */
  const updateSelectedUavIds = (uavIds: number[]): void => {
    console.log('[WorkerManager] 📤 Updating selected UAV IDs:', uavIds)
    postToWorker({
      type: 'uavIds',
      uavIds
    })
  }

  /**
   * Detekciós adat küldése a workernek
   */
  const sendDetection = (detectionData: string): void => {
    postToWorker({
      type: 'newDetection',
      detection: detectionData,
      timestamp: performance.now()
    })
  }

  /**
   * Sampling rate frissítése
   */
  const updateSamplingRate = (samplingRate: number): void => {
    postToWorker({
      type: 'updateSettings',
      samplingRate
    })
  }

  /**
   * Worker statisztikák lekérése
   */
  const requestStats = (): void => {
    postToWorker({ type: 'getStats' })
  }

  /**
   * Detekciók törlése
   */
  const clearDetections = (): void => {
    postToWorker({ type: 'clearDetections' })
  }

  /**
   * Worker leállítása
   */
  const terminateWorker = (): void => {
    if (workerInstance) {
      postToWorker({ type: 'terminate' })
      workerInstance.terminate()
      workerInstance = null
      isInitialized = false
      messageHandlers.clear()
      console.log('[WorkerManager] Worker terminated')
    }
  }

  /**
   * Worker állapot ellenőrzése
   */
  const isWorkerReady = (): boolean => {
    return isInitialized && workerInstance !== null
  }

  return {
    initWorker,
    onWorkerMessage,
    postToWorker,
    updateSelectedUavIds,
    sendDetection,
    updateSamplingRate,
    requestStats,
    clearDetections,
    terminateWorker,
    isWorkerReady
  }
}