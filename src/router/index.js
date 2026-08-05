import { createRouter, createWebHashHistory } from 'vue-router'
import Inicio from '@ecored-sena/boulder-kit/plugin/components/Inicio.vue'
import Curso from '@ecored-sena/boulder-kit/plugin/components/plantilla/Curso.vue'
import Glosario from '@ecored-sena/boulder-kit/plugin/components/Glosario.vue'
import Referencias from '@ecored-sena/boulder-kit/plugin/components/Referencias.vue'
import Creditos from '@ecored-sena/boulder-kit/plugin/components/Creditos.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'inicio',
      component: Inicio,
    },
    {
      path: '/introduccion',
      name: 'introduccion',
      component: () =>
        import(/* webpackChunkName: "intro" */ '../views/Introduccion.vue'),
    },
    {
      path: '/curso',
      name: 'curso',
      component: Curso,
      redirect: {
        name: 'tema1',
      },
      children: [
        {
          path: 'tema1',
          name: 'tema1',
          component: () =>
            import(/* webpackChunkName: "tema1" */ '../views/Tema1.vue'),
        },
        {
          path: 'tema2',
          name: 'tema2',
          component: () =>
            import(/* webpackChunkName: "tema2" */ '../views/Tema2.vue'),
        },
        {
          path: 'tema3',
          name: 'tema3',
          component: () =>
            import(/* webpackChunkName: "tema3" */ '../views/Tema3.vue'),
        },
      ],
    },
    {
      path: '/actividad',
      name: 'actividad',
      component: () =>
        import(/* webpackChunkName: "actividad" */ '../views/Actividad.vue'),
    },
    {
      path: '/glosario',
      name: 'glosario',
      component: Glosario,
    },
    {
      path: '/referencias',
      name: 'referencias',
      component: Referencias,
    },
    {
      path: '/sintesis',
      name: 'sintesis',
      component: () =>
        import(/* webpackChunkName: "sintesis" */ '../views/Sintesis.vue'),
    },
    {
      path: '/creditos',
      name: 'creditos',
      component: Creditos,
    },
  ],
  scrollBehavior(to, from) {
    if (to.hash) {
      const newRoute = {
        el: to.hash,
        top: 100,
        behavior: 'smooth',
      }
      if (to.name === from.name) {
        return newRoute
      } else {
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve(newRoute)
          }, 500)
        })
      }
    } else {
      setTimeout(() => {
        window.scrollTo({
          left: 0,
          top: 0,
          behavior: 'auto',
        })
      }, 100)
    }
  },
})

export default router
