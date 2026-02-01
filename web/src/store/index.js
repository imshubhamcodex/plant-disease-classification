import Vue from 'vue'
import Vuex from 'vuex'
import { ref, onValue } from "firebase/database"
import { rtdb } from "../plugins/firebase"

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    rxPackets: [],     // parsed & sorted packets
    rxRaw: {}          // raw firebase data
  },

  getters: {
    allPackets: state => state.rxPackets,
    latestPacket: state =>
      state.rxPackets.length
        ? state.rxPackets[state.rxPackets.length - 1]
        : null
  },

  mutations: {
    SET_RX_RAW(state, payload) {
      state.rxRaw = payload
    },
    SET_RX_PACKETS(state, packets) {
      state.rxPackets = packets
    }
  },

  actions: {
    listenRx({ commit }) {
      const rxRef = ref(rtdb, "rx")

      onValue(rxRef, snapshot => {
        const data = snapshot.val() || {}

        commit("SET_RX_RAW", data)

        const packets = Object.keys(data)
          .map(key => ({
            id: key,
            ts: data[key].gw_ts,
            ts_date_time: new Date(data[key].gw_ts).toISOString().replace("T", " ").slice(0, 19),
            payload: data[key].payload
          }))
          .sort((a, b) => a.ts - b.ts)

        commit("SET_RX_PACKETS", packets)
      })
    }
  }
})
