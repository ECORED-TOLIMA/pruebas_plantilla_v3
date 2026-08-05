import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store/index.js'
import legoRedPlugin from '@ecored-sena/boulder-kit'
import config from './config/global.js'
import packageJson from '../package.json'

import './styles/_styles.sass'

const app = createApp(App)
app.use(router)
app.use(store)
app.use(legoRedPlugin, { config, packageJson })
app.mount('#app')
