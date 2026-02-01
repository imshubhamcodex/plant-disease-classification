<template>
  <v-card class="overflow-hidden">
    <v-sheet id="scrolling-techniques-5" class="overflow-y-auto">
      <v-container style="margin-top: 50px">
        <!-- <v-row>
          <v-col cols="auto">
            <v-data-table
              class="elevation-1"
              :headers="headers"
              :items="packets"
              dense
            />
          </v-col>
        </v-row> -->
        <v-row justify="center" style="margin-top: 20px; margin-bottom: 50px">
          <v-col cols="auto" style="position: relative">
            <canvas
              ref="gridCanvas"
              :width="h_w"
              :height="h_w"
              style="border: 1px solid #ccc"
              @click="onClickCell"
            ></canvas>
            <div
              v-if="tooltip"
              :style="{
                position: 'absolute',
                top: tooltipY + 'px',
                left: tooltipX + 'px',
                background: 'rgba(0,0,0,0.7)',
                color: 'white',
                padding: '5px',
                borderRadius: '4px',
                pointerEvents: 'none',
                whiteSpace: 'pre-line',
                zIndex: 1000,
              }"
            >
              {{ tooltip }}
            </div>
          </v-col>
        </v-row>
      </v-container>
    </v-sheet>
  </v-card>
</template>

<script>
export default {
  data() {
    return {
      /* ================= TABLE ================= */
      headers: [
        { text: "Timestamp", value: "ts_date_time" },
        { text: "Payload", value: "payload" },
      ],

      /* ================= CANVAS / GRID ================= */
      h_w: 800,
      gridRows: 20,
      gridCols: 20,
      cellW: 0,
      cellH: 0,
      ctx: null,

      /* ================= GRID DATA ================= */
      gridData: {},
      lastProcessedIndex: 0,
      /* ================= DRONE ANIMATION ================= */
      visitQueue: [],
      visitHistory: [],
      currentVisit: null,
      animationPhase: "scan", // scan | transition

      spiralTrail: [],
      spiralDir: 0,
      spiralStep: 1,

      transitionStart: null,
      transitionFrom: null,
      transitionTo: null,

      SPIRAL_DURATION: 2500,
      TRANSITION_DURATION: 800,
      DRONE_SIZE_FACTOR: 0.3,

      /* ================= TOOLTIP ================= */
      tooltip: "",
      tooltipX: 0,
      tooltipY: 0,
    };
  },

  computed: {
    packets() {
      return this.$store.getters.allPackets;
    },
  },

  watch: {
    packets: {
      handler(newPackets) {
        this.updateGrid(newPackets);
      },
      deep: true,
    },
  },

  mounted() {
    this.h_w = Math.min(window.innerWidth * 0.9, 800);
    this.cellW = this.h_w / this.gridCols;
    this.cellH = this.h_w / this.gridRows;
    this.ctx = this.$refs.gridCanvas.getContext("2d");
    this.drawGrid();
    this.drawCellCoordinates();
  },

  methods: {
    /* ================= DRAW GRID ================= */
    drawGrid() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.h_w, this.h_w);
      ctx.strokeStyle = "#eee";

      for (let c = 0; c <= this.gridCols; c++) {
        const x = c * this.cellW;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, this.h_w);
        ctx.stroke();
      }

      for (let r = 0; r <= this.gridRows; r++) {
        const y = r * this.cellH;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(this.h_w, y);
        ctx.stroke();
      }
      this.drawCellCoordinates();
    },
    drawCellCoordinates() {
      const ctx = this.ctx;
      ctx.fillStyle = "#555";
      ctx.font = "12px Arial";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      for (let x = 0; x < this.gridCols; x++) {
        for (let y = 0; y < this.gridRows; y++) {
          const cx = x * this.cellW + this.cellW / 2;
          const cy = this.h_w - (y * this.cellH + this.cellH / 2);

          ctx.fillText(`${x},${y}`, cx, cy);
        }
      }
    },

    /* ================= PARSE PAYLOAD ================= */
    parsePacket(payload) {
      const cells = [];
      const parts = payload.split(/\[ID\]:\d+/).filter(Boolean);

      parts.forEach((part) => {
        const cellMatch = part.match(/CELL \((\d+),\s*(\d+)\)/);
        if (!cellMatch) return;

        const x = parseInt(cellMatch[1]);
        const y = parseInt(cellMatch[2]);

        const diseaseMatches = [
          ...part.matchAll(/(\w+)\s*:\s*(\d+)\s*:\s*(\d+)/g),
        ];

        const diseases = diseaseMatches.map((m) => ({
          name: m[1],
          infected: parseInt(m[2]),
          healthy: parseInt(m[3]),
        }));

        cells.push({ x, y, diseases });
      });

      return cells;
    },

    /* ================= UPDATE GRID ================= */
    updateGrid(packets) {
      // process ONLY packets that arrived after last run
      const newPackets = packets.slice(this.lastProcessedIndex);

      if (!newPackets.length) return;

      newPackets.forEach((packet) => {
        const cells = this.parsePacket(packet.payload);
        cells.forEach((cell) => {
          const key = `${cell.x},${cell.y}`;
          if (!this.gridData[key]) {
            this.gridData[key] = cell;
            this.visitQueue.push(cell);
          }
        });
      });

      // update pointer
      this.lastProcessedIndex = packets.length;

      // start animation ONLY if idle
      if (!this.currentVisit && this.visitQueue.length) {
        this.startNextCell();
      }
    },

    /* ================= START CELL ================= */
    startNextCell() {
      if (!this.visitQueue.length) return;

      const cell = this.visitQueue.shift();

      const infected = cell.diseases.reduce((a, d) => a + d.infected, 0);
      const healthy = cell.diseases.reduce((a, d) => a + d.healthy, 0);

      cell.trailColor =
        infected > 0
          ? "red"
          : healthy > 0 || cell.diseases.length == 0
          ? "lime"
          : "#aaa";

      const cx = cell.x * this.cellW + this.cellW / 2;
      const cy = this.h_w - (cell.y * this.cellH + this.cellH / 2);

      this.currentVisit = {
        ...cell,
        cx,
        cy,
        startTime: performance.now(),
      };

      this.spiralTrail = [{ x: cx, y: cy }];
      this.spiralDir = 0;
      this.spiralStep = 1;
      this.animationPhase = "scan";

      requestAnimationFrame(this.animateDrone);
    },

    /* ================= MAIN LOOP ================= */
    animateDrone(time) {
      if (!this.currentVisit) return;

      // clear only dynamic layer
      this.clearDynamicLayer();

      if (this.animationPhase === "scan") {
        this.drawRectSpiral(time);
      } else {
        this.drawTransition(time);
      }
    },

    clearDynamicLayer() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.h_w, this.h_w);

      // redraw static grid + visited cells ONLY ONCE
      this.drawGrid();
      this.visitHistory.forEach((cell) => this.paintVisitedCell(cell));
    },

    /* ================= RECTANGULAR SPIRAL ================= */
    drawRectSpiral(time) {
      const elapsed = time - this.currentVisit.startTime;

      if (elapsed >= this.SPIRAL_DURATION) {
        this.startTransition();
        return;
      }

      const ctx = this.ctx;
      const step = Math.min(this.cellW, this.cellH) * 0.012;
      let last = this.spiralTrail[this.spiralTrail.length - 1];
      let nx = last.x;
      let ny = last.y;

      if (this.spiralDir === 0) nx += step;
      else if (this.spiralDir === 1) ny += step;
      else if (this.spiralDir === 2) nx -= step;
      else ny -= step;

      this.spiralTrail.push({ x: nx, y: ny });

      if (this.spiralTrail.length % (this.spiralStep * 10) === 0) {
        this.spiralDir = (this.spiralDir + 1) % 4;
        if (this.spiralDir === 0 || this.spiralDir === 2) {
          this.spiralStep++;
        }
      }

      const trailColor =
        elapsed < 500 ? "#00ff00" : this.currentVisit.trailColor;

      ctx.strokeStyle = trailColor;
      ctx.lineWidth = 2;

      ctx.beginPath();
      this.spiralTrail.forEach((p, i) =>
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y),
      );
      ctx.stroke();

      this.drawDrone(nx, ny);
      requestAnimationFrame(this.animateDrone);
    },

    /* ================= TRANSITION ================= */
    startTransition() {
      this.visitHistory.push(this.currentVisit);

      if (!this.visitQueue.length) {
        this.currentVisit = null;
        return;
      }

      const last = this.spiralTrail[this.spiralTrail.length - 1];
      const next = this.visitQueue[0];

      this.transitionFrom = last;
      this.transitionTo = {
        x: next.x * this.cellW + this.cellW / 2,
        y: this.h_w - (next.y * this.cellH + this.cellH / 2),
      };

      this.transitionStart = performance.now();
      this.animationPhase = "transition";
      requestAnimationFrame(this.animateDrone);
    },

    drawTransition(time) {
      const t = Math.min(
        (time - this.transitionStart) / this.TRANSITION_DURATION,
        1,
      );

      const x =
        this.transitionFrom.x +
        (this.transitionTo.x - this.transitionFrom.x) * t;
      const y =
        this.transitionFrom.y +
        (this.transitionTo.y - this.transitionFrom.y) * t;

      this.drawDrone(x, y);

      if (t < 1) {
        requestAnimationFrame(this.animateDrone);
      } else {
        this.startNextCell();
      }
    },

    /* ================= DRONE ================= */
    drawDrone(x, y) {
      const ctx = this.ctx;
      const size = Math.min(this.cellW, this.cellH) * this.DRONE_SIZE_FACTOR;

      ctx.fillStyle = "black";
      ctx.beginPath();
      ctx.arc(x, y, size / 2.5, 0, Math.PI * 2);
      ctx.closePath();
      ctx.fill();
    },

    /* ================= TOOLTIP ================= */
    onClickCell(e) {
      const rect = this.$refs.gridCanvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const col = Math.floor(mx / this.cellW);
      const row = Math.floor((this.h_w - my) / this.cellH);

      const data = this.gridData[`${col},${row}`];
      if (!data) return (this.tooltip = "");

      this.tooltipX = mx + 6;
      this.tooltipY = my + 6;

      this.tooltip =
        `CELL: (${col}, ${row})\n` +
        data.diseases
          .map(
            (d) =>
              `DISEASE: ${d.name} | Infected ${d.infected} | Healthy ${d.healthy}`,
          )
          .join("\n");
    },
    paintVisitedCell(cell) {
      const ctx = this.ctx;

      const totalInfected = cell.diseases.reduce((s, d) => s + d.infected, 0);
      const totalHealthy = cell.diseases.reduce((s, d) => s + d.healthy, 0);

      let fillColor;
      if (totalInfected > 0) fillColor = "#ff9d9d";
      else if (totalHealthy > 0 || cell.diseases.length === 0)
        fillColor = "#9dff9d";
      else fillColor = "#f0f0f0";

      const x = cell.x * this.cellW;
      const y = this.h_w - (cell.y + 1) * this.cellH;

      ctx.fillStyle = fillColor;
      ctx.fillRect(x, y, this.cellW, this.cellH);

      ctx.strokeStyle = "#ddd";
      ctx.strokeRect(x, y, this.cellW, this.cellH);
      // this.drawCellCoordinates();
    },
  },
};
</script>
