export interface RealtimeConfig {
  maxLatencyMs: number        // Max elfogadható késleltetés (pl. 500ms)
  detectionTTL: number        // Detekció élettartama (pl. 5000ms)
  enableStrictRealtime: boolean  // Ha true, eldobja a régi adatokat
  circularBufferSize: number  // Fix méretű buffer (pl. 50)
  interval: number
}
