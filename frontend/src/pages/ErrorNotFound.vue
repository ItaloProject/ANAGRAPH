<template>
  <q-page class="flex flex-center column" style="background:var(--bg-deep);min-height:100vh;">
    <div class="text-center">
      <div class="text-neon-cyan" style="font-size:80px;font-weight:700;letter-spacing:-4px;">404</div>
      <div class="text-h6 text-muted q-mb-lg">Página não encontrada</div>
      <q-btn unelevated color="cyan" label="Voltar ao Dashboard" to="/" />
    </div>
  </q-page>
</template>
<script setup lang="ts" />
<style scoped>
.text-muted { color: var(--text-muted); }
</style>
