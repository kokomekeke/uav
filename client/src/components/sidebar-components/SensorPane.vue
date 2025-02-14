<script setup>

</script>

<template>
  <div>
    <div class="sidebar">
      <div class="sidebar-content">
        <div class="sidebar-header">
          <p>Components menu</p>
          <button class="btn btn-sm btn-link">
            X
          </button>
        </div>
        <div class="sidebar-body">
          <ul>
            <li class="sidebar-item">
              <router-link to="/">
                <i class="material-icons-outlined">code</i>
                Sidebar
              </router-link>
            </li>
          </ul>
        </div>
        <div class="sidebar-footer">
          <a href="https://blog.colorffy.com" target="_blank" rel="noopener">
            By: blog.colorffy.com
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  background: #42b983;
  grid-area: main;
  margin-top: 10px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
