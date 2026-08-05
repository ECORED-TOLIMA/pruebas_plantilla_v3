import { createStore } from 'vuex'

export default createStore({
  state: {
    loading: 0,
    menuOpen: false,
  },
  getters: {
    isLoading: (state) => !!state.loading,
    isMenuOpen: (state) => state.menuOpen,
  },
  mutations: {
    toggleMenu(state, newVal) {
      state.menuOpen = newVal
    },
    increment(state) {
      state.loading++
    },
    decrease(state) {
      state.loading--
    },
  },
  actions: {
    toggleMenu({ commit }, newVal) {
      commit('toggleMenu', newVal)
    },
    increment({ commit }) {
      commit('increment')
    },
    decrease({ commit }) {
      commit('decrease')
    },
  },
})
