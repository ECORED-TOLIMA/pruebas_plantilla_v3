<template lang="pug">
#app.app
  Header
  .contenedor-principal
    AsideMenu
    section.seccion-principal
      router-view
  BarraAvance
  Accesibilidad
</template>

<script>
export default {
  name: 'App',
  mounted() {
    this.$aos.init({
      offset: 100,
      once: true,
    })
  },
}
</script>

<style lang="sass"></style>
