<script setup>
defineProps({
  show: Boolean
})

defineEmits(['close'])
</script>

<template>
  <Transition name="modal">
    <div v-if="show" class="modal-mask">
      <div class="modal-container">
        <div class="modal-header">
          <slot name="header">Default Header</slot>
        </div>

        <div class="modal-body">
          <slot name="body">Default Body</slot>
        </div>

        <div class="modal-footer">
          <slot name="close">
            <button class="modal-close-button" @click="close">Close</button>
          </slot>
          <slot name="submit">
            <button class="modal-submit-button" @click="submit">Submit</button>
          </slot>
        </div>
        <div class="modal-alerts">
          <slot name="alert">
          </slot>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-mask {
  position: fixed;
  z-index: 9998;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  transition: opacity 0.3s ease;
}

.modal-container {
  width: 400px;
  margin: auto;
  padding: 20px 30px;
  background-color: #dbd9d9;
  border-style: solid;
  border-radius: 8px;
  border-color: #263024;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.33);
  transition: all 0.3s ease;
  font-family: 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Bitstream Vera Sans Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.modal-header h3 {
  margin-top: 0;
  color: #42b983;
}

.modal-body {
  margin: 20px 0;
}

.modal-submit-button {
  float: right;
  font-family: 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Bitstream Vera Sans Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 1px;
  border-style: solid;
  border-radius: 8px;
  border-width: medium;
  border-color: #263024;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.modal-enter-from {
  opacity: 0;
}

.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  -webkit-transform: scale(1.1);
  transform: scale(1.1);
}

</style>
