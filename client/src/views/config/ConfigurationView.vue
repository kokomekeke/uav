<script setup lang="ts">
import { ref } from 'vue'
import ConfigComponent from '@/components/configuration/ConfigComponent.vue'
import axios from 'axios'

const config = ref({
  // Source configuration
  center_freq: '446M',
  bandwidth: '1M',
  gain: '50',
  bin_count: '1024',
  burst_stride: '65536',
  antenna_id: '',

  // Stream configuration
  stream_id: '1',
  stream_level: 'SPECTRUM', // OPTIONS: SPECTRUM, DETECTION, TELEMETRY
  stream_address: '',
  stream_port: '4242',
  heartbeat_timeout: '1',
  telemetry_timeout: '1',

  // Post-processing configuration
  pp_config: {
    enabled: true,
    // ROI settings
    roi_settings: []
  },

  // Recording settings
  recording_path: '',

  // Connection settings
  host_address: '',
  host_cmd_port: '5556',
  client_stream_port: '4242',

  // Map server settings
  map_server_host: '0.0.0.0',
  map_server_port: '20000',
  map_server_lat: '',
  map_server_lon: ''
})

const streamLevels = ['SPECTRUM', 'DETECTION', 'TELEMETRY']

const updateConfig = async () => {
  try {
    const payload = buildProtoConfig(config.value)

    const uavId = 1 // vagy store-ból
    const res = await axios.post(
      'http://localhost:5000/v1/uav/1/command/CONFIG/',
      payload
    )

    console.log('CONFIG response:', res.data)
  } catch (err) {
    console.error('Failed to send CONFIG', err)
  }
}

const addRoiSetting = () => {
  config.value.pp_config.roi_settings.push({
    center_frequency: '',
    threshold: ''
  })
}

function parseFreq (str: string): number {
  if (!str) return 0
  if (str.endsWith('M')) return parseFloat(str) * 1e6
  if (str.endsWith('k')) return parseFloat(str) * 1e3
  return Number(str)
}

function buildProtoConfig (cfg: any) {
  return {
    config_id: Date.now(),

    cs: {
      center_frequency: parseFreq(cfg.center_freq),
      iq_rate: parseFreq(cfg.bandwidth),

      bin_count: Number(cfg.bin_count),
      burst_stride: Number(cfg.burst_stride),

      channel_gain:
        cfg.gain && Number(cfg.gain) > 0
          ? [Number(cfg.gain)]
          : [],

      type: 0 // LIVE
    },

    pp: {
      roi: cfg.pp_config.enabled
        ? cfg.pp_config.roi_settings.map((roi, idx) => ({
          roi_id: idx + 1,
          center_frequency: parseFreq(roi.center_frequency),
          span: 10_000, // 🔥 KÖTELEZŐ
          threshold: Number(roi.threshold)
        }))
        : []
    }
  }
}

const removeRoiSetting = (index) => {
  config.value.pp_config.roi_settings.splice(index, 1)
}
</script>

<template>
  <div class="p-6 bg-slate-900 rounded-xl shadow-lg w-full h-full overflow-y-auto border border-slate-700">
    <h1 class="text-lg font-semibold text-cyan-400 mb-6">Configuration Settings</h1>

    <!-- Source Configuration Section -->
    <section class="mb-6">
      <h2 class="text-md font-semibold text-cyan-300 mb-3 border-b border-slate-700 pb-2">
        Source Configuration
      </h2>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="center_freq" class="block text-sm font-medium text-gray-300 mb-1">
            Center Frequency
          </label>
          <input
            id="center_freq"
            v-model="config.center_freq"
            type="text"
            placeholder="e.g., 446M"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="bandwidth" class="block text-sm font-medium text-gray-300 mb-1">
            Bandwidth
          </label>
          <input
            id="bandwidth"
            v-model="config.bandwidth"
            type="text"
            placeholder="e.g., 1M"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="gain" class="block text-sm font-medium text-gray-300 mb-1">
            Gain
          </label>
          <input
            id="gain"
            v-model="config.gain"
            type="text"
            placeholder="e.g., 50"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="bin_count" class="block text-sm font-medium text-gray-300 mb-1">
            Bin Count
          </label>
          <input
            id="bin_count"
            v-model="config.bin_count"
            type="text"
            placeholder="e.g., 1024"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="burst_stride" class="block text-sm font-medium text-gray-300 mb-1">
            Burst Stride
          </label>
          <input
            id="burst_stride"
            v-model="config.burst_stride"
            type="text"
            placeholder="e.g., 65536"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="antenna_id" class="block text-sm font-medium text-gray-300 mb-1">
            Antenna ID (Optional)
          </label>
          <input
            id="antenna_id"
            v-model="config.antenna_id"
            type="text"
            placeholder="Optional"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>
      </div>
    </section>

    <!-- Stream Configuration Section -->
    <section class="mb-6">
      <h2 class="text-md font-semibold text-cyan-300 mb-3 border-b border-slate-700 pb-2">
        Stream Configuration
      </h2>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="stream_id" class="block text-sm font-medium text-gray-300 mb-1">
            Stream ID
          </label>
          <input
            id="stream_id"
            v-model="config.stream_id"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="stream_level" class="block text-sm font-medium text-gray-300 mb-1">
            Stream Level
          </label>
          <select
            id="stream_level"
            v-model="config.stream_level"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          >
            <option v-for="level in streamLevels" :key="level" :value="level">
              {{ level }}
            </option>
          </select>
        </div>

        <div>
          <label for="stream_address" class="block text-sm font-medium text-gray-300 mb-1">
            Stream Address
          </label>
          <input
            id="stream_address"
            v-model="config.stream_address"
            type="text"
            placeholder="IP address"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="stream_port" class="block text-sm font-medium text-gray-300 mb-1">
            Stream Port
          </label>
          <input
            id="stream_port"
            v-model="config.stream_port"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="heartbeat_timeout" class="block text-sm font-medium text-gray-300 mb-1">
            Heartbeat Timeout (s)
          </label>
          <input
            id="heartbeat_timeout"
            v-model="config.heartbeat_timeout"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="telemetry_timeout" class="block text-sm font-medium text-gray-300 mb-1">
            Telemetry Timeout (s)
          </label>
          <input
            id="telemetry_timeout"
            v-model="config.telemetry_timeout"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>
      </div>
    </section>

    <!-- Connection Settings Section -->
    <section class="mb-6">
      <h2 class="text-md font-semibold text-cyan-300 mb-3 border-b border-slate-700 pb-2">
        Connection Settings
      </h2>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="host_address" class="block text-sm font-medium text-gray-300 mb-1">
            Host Address
          </label>
          <input
            id="host_address"
            v-model="config.host_address"
            type="text"
            placeholder="Server IP"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="host_cmd_port" class="block text-sm font-medium text-gray-300 mb-1">
            Command Port
          </label>
          <input
            id="host_cmd_port"
            v-model="config.host_cmd_port"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="client_stream_port" class="block text-sm font-medium text-gray-300 mb-1">
            Client Stream Port
          </label>
          <input
            id="client_stream_port"
            v-model="config.client_stream_port"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>
      </div>
    </section>

    <!-- Map Server Settings Section -->
    <section class="mb-6">
      <h2 class="text-md font-semibold text-cyan-300 mb-3 border-b border-slate-700 pb-2">
        Map Server Settings
      </h2>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="map_server_host" class="block text-sm font-medium text-gray-300 mb-1">
            Map Server Host
          </label>
          <input
            id="map_server_host"
            v-model="config.map_server_host"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="map_server_port" class="block text-sm font-medium text-gray-300 mb-1">
            Map Server Port
          </label>
          <input
            id="map_server_port"
            v-model="config.map_server_port"
            type="text"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="map_server_lat" class="block text-sm font-medium text-gray-300 mb-1">
            Latitude (Optional)
          </label>
          <input
            id="map_server_lat"
            v-model="config.map_server_lat"
            type="text"
            placeholder="Latitude"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>

        <div>
          <label for="map_server_lon" class="block text-sm font-medium text-gray-300 mb-1">
            Longitude (Optional)
          </label>
          <input
            id="map_server_lon"
            v-model="config.map_server_lon"
            type="text"
            placeholder="Longitude"
            class="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>
      </div>
    </section>

    <!-- Post-Processing Configuration Section -->
    <section class="mb-6">
      <h2 class="text-md font-semibold text-cyan-300 mb-3 border-b border-slate-700 pb-2">
        Post-Processing Configuration
      </h2>

      <div class="mb-4">
        <label class="flex items-center text-sm font-medium text-gray-300">
          <input
            v-model="config.pp_config.enabled"
            type="checkbox"
            class="mr-2 rounded bg-slate-800 border-slate-600 text-cyan-600 focus:ring-2 focus:ring-cyan-500"
          />
          Enable Post-Processing
        </label>
      </div>

      <div v-if="config.pp_config.enabled">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-sm font-medium text-gray-300">ROI Settings</h3>
          <button
            @click="addRoiSetting"
            class="px-3 py-1 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg transition"
          >
            Add ROI
          </button>
        </div>

        <div
          v-for="(roi, index) in config.pp_config.roi_settings"
          :key="index"
          class="mb-3 p-3 bg-slate-800 rounded-lg border border-slate-700"
        >
          <div class="flex justify-between items-start mb-2">
            <span class="text-sm font-medium text-cyan-400">ROI {{ index + 1 }}</span>
            <button
              @click="removeRoiSetting(index)"
              class="text-red-400 hover:text-red-300 text-sm"
            >
              Remove
            </button>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1">Center Frequency</label>
              <input
                v-model="roi.center_frequency"
                type="text"
                class="w-full px-2 py-1 text-sm rounded bg-slate-700 border border-slate-600 text-gray-100 focus:ring-1 focus:ring-cyan-500"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1">Threshold</label>
              <input
                v-model="roi.threshold"
                type="text"
                class="w-full px-2 py-1 text-sm rounded bg-slate-700 border border-slate-600 text-gray-100 focus:ring-1 focus:ring-cyan-500"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <config-component class="mb-4"></config-component>

    <button
      @click="updateConfig"
      class="w-full bg-cyan-600 hover:bg-cyan-500 text-white py-2 rounded-xl font-medium shadow transition"
    >
      Save Configuration
    </button>
  </div>
</template>
