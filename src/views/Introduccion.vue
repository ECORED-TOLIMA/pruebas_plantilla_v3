<template lang="pug">
.curso-main-container.introduccion
  BannerInterno
  .container.tarjeta.tarjeta--blanca.p-4.p-md-5.mb-5

    .titulo-principal.color-acento-contenido
      .titulo-principal__numero
        span
          i.fas.fa-info
      h1 Introducción

    //- Fila 1: párrafo de entrada (col-lg-9, texto de 910 pt) + foto lateral de 292x389 r=10
    //- (col-lg-3). La foto abarca en el XD desde el primer párrafo hasta el pie de la caja rosa.
    .row
      .col-lg-9
        p La cartera de créditos es el principal activo generador de ingresos de las entidades del sector financiero colombiano y, al mismo tiempo, su mayor fuente de riesgo operativo y crediticio. Para bancos, compañías de financiamiento, cooperativas financieras y demás establecimientos de crédito vigilados por la Superintendencia Financiera de Colombia, la calidad de la cartera determina la solidez patrimonial de la institución y su capacidad para continuar prestando servicios financieros a la comunidad. Comprender la gestión integral de este activo no es una competencia técnica secundaria, sino una habilidad central para cualquier profesional del sector financiero colombiano.
        .bg-1.r-10.p-32
          p.mb-0 El presente componente formativo tiene como propósito desarrollar en el aprendiz las competencias conceptuales, procedimentales y actitudinales necesarias para identificar los elementos de la administración y recuperación de la cartera y reconocer los procesos de cobranza y manejo del cliente. Para ello, integra el estudio de los fundamentos de la administración aplicados al contexto financiero, el marco normativo y ético que rige la gestión de cartera, los procesos de elaboración y ejecución de planes de recuperación, las competencias de servicio al cliente y negociación, y las técnicas diferenciadas de cobranza según la etapa de mora de cada obligación. Este recorrido formativo cierra con el análisis de casos prácticos que trasladan los conceptos al entorno productivo real.
      .col-lg-3
        figure
          img.r-10.m-auto(
            src="@/assets/curso/introduccion/foto-gestores.png"
            style="width: 292px"
            alt="Dos gestores de cartera revisan información financiera en una tableta"
          )

    //- Fila 2: ilustración de 292x212 sin radio (col-lg-3) + círculo de puntos de 84x84 y los dos
    //- párrafos de cierre (col-lg-9). El párrafo largo arranca a la derecha de los puntos.
    .row.mt-4
      .col-lg-3
        figure
          img(
            src="@/assets/curso/introduccion/ilustracion-cartera.svg"
            style="width: 292px"
            alt="Ilustración de personas que entregan y reciben billetes y monedas"
          )
      .col-lg-9
        .row
          .col-auto
            figure
              img(
                src="@/assets/curso/introduccion/puntos-naranja.svg"
                style="width: 84px"
                alt=""
              )
          .col
            p Cabe destacar que la gestión de cartera exige una actuación ética, clara y responsable, debido a que el gestor maneja información financiera sensible y se comunica con personas que pueden enfrentar dificultades de pago. Por esta razón, la recuperación de las obligaciones debe realizarse con respeto, transparencia y cumplimiento de la normativa vigente. Asimismo, este equilibrio entre la efectividad del recaudo y la protección del consumidor financiero fortalece el desempeño profesional y promueve una gestión coherente con las políticas institucionales y las buenas prácticas del sector financiero.
        p.mb-0 Para ampliar la comprensión de los conceptos abordados y contextualizar su aplicación en la gestión de cartera, se recomienda acceder al recurso audiovisual que acompaña esta sección.

    //- Bloque de video de 1228x580 r=10 (col-12). El diseño lo dibuja como ESPACIO PARA VIDEO: el
    //- video de la introducción todavía no existe (fuentes sólo trae el guion, CF1_13340008_GUION
    //- .docx), así que va el marcador del propio diseño. Ver fuentes/REVISION-PENDIENTES.md.
    figure.mt-4.mb-0
      img.r-10(
        src="@/assets/curso/introduccion/video-placeholder.png"
        alt="Espacio reservado para el video de la introducción"
      )
</template>

<script>
export default {
  name: 'Introduccion',
  data: () => ({
    // variables de vue
  }),
  mounted() {
    this.$nextTick(() => {
      this.$aosRefresh()
    })
  },
  updated() {
    this.$aosRefresh()
  },
}
</script>

<style lang="sass"></style>
