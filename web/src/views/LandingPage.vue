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

      initialLoadDone: false,
      isIdle: false,
      lastKnownCell: null,
      idleAngle: 0,

      /* ================= TOOLTIP ================= */
      tooltip: "",
      tooltipX: 0,
      tooltipY: 0,

      /* ================= DISEASE COLORS ================= */
      diseaseColors: {},
      colorPalette: [
        "#ff4d4d",
        "#ffa500",
        "#8a2be2",
        "#00bfff",
        "#2ecc71",
        "#f1c40f",
        "#e67e22",
        "#3498db",
        "#e84393",
        "#FF007F",
        "#3498db",
        "#2c3e50",
        "#2980b9",
      ],
      nextColorIndex: 0,
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
    this.sendTelegramMessage("Drone is ready to scan");
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
      const newPackets = packets.slice(this.lastProcessedIndex);
      if (!newPackets.length) return;

      newPackets.forEach((packet) => {
        const cells = this.parsePacket(packet.payload);

        cells.forEach((cell) => {
          const key = `${cell.x},${cell.y}`;

          /* Skip if already painted OR already queued */
          if (
            this.gridData[key] ||
            this.visitQueue.some((c) => c.x === cell.x && c.y === cell.y)
          ) {
            return;
          }

          this.gridData[key] = cell;
          this.visitQueue.push(cell);
        });
      });

      this.lastProcessedIndex = packets.length;

      /* ===== FIRST LOAD ===== */
      if (!this.initialLoadDone) {
        while (this.visitQueue.length) {
          const cell = this.visitQueue.shift();
          this.visitHistory.push(cell);
          this.paintVisitedCell(cell);
          this.lastKnownCell = cell;
        }

        this.initialLoadDone = true;
        this.startIdleDrone();
        return;
      }

      /* ===== NORMAL FLOW ===== */
      if (!this.currentVisit && this.visitQueue.length) {
        this.isIdle = false;
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

      this.lastKnownCell = cell;
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

      // 🔔 SEND MESSAGE AFTER EVERY 10 CELLS
      if (this.visitHistory.length % 10 === 0) {
        const last10 = this.visitHistory.slice(-10);

        const report = last10
          .map((c) => {
            const inf = c.diseases.reduce((s, d) => s + d.infected, 0);
            const heal = c.diseases.reduce((s, d) => s + d.healthy, 0);
            return `(${c.x},${c.y}) → Infected:${inf} Healthy:${heal}`;
          })
          .join("\n");

        this.sendTelegramMessage(
          `*Drone Scan Update*\nScanned ${this.visitHistory.length} cells\n\n${report}`,
        );
      }

      if (!this.visitQueue.length) {
        this.sendFinalReport();
        this.currentVisit = null;
        this.startIdleDrone();
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
      const x = cell.x * this.cellW;
      const y = this.h_w - (cell.y + 1) * this.cellH;

      const diseaseName = cell.diseases?.length ? cell.diseases[0].name : null;

      const color = diseaseName ? this.getDiseaseColor(diseaseName) : "green";

      ctx.fillStyle = color;
      ctx.fillRect(x, y, this.cellW, this.cellH);

      ctx.strokeStyle = "#ddd";
      ctx.strokeRect(x, y, this.cellW, this.cellH);
      // this.drawCellCoordinates();
    },
    sendFinalReport() {
      let totalInfected = 0;
      let totalHealthy = 0;

      this.visitHistory.forEach((c) => {
        c.diseases.forEach((d) => {
          totalInfected += d.infected;
          totalHealthy += d.healthy;
        });
      });

      this.sendTelegramMessage(
        `✅ *Scan Completed*\n\n` +
          `Cells scanned: ${this.visitHistory.length}\n` +
          `Total Infected: ${totalInfected}\n` +
          `Total Healthy: ${totalHealthy}`,
      );
    },
    startIdleDrone() {
      if (!this.lastKnownCell) return;

      this.isIdle = true;

      const cx = this.lastKnownCell.x * this.cellW + this.cellW / 2;
      const cy =
        this.h_w - (this.lastKnownCell.y * this.cellH + this.cellH / 2);

      const animateIdle = () => {
        if (!this.isIdle) return;

        this.clearDynamicLayer();

        const r = Math.min(this.cellW, this.cellH) * 0.3;
        this.idleAngle += 0.04;

        const x = cx + r * Math.cos(this.idleAngle);
        const y = cy + r * Math.sin(this.idleAngle);

        this.drawDrone(x, y);
        requestAnimationFrame(animateIdle);
      };

      requestAnimationFrame(animateIdle);
    },

    getDiseaseColor(diseaseName) {
      if (!this.diseaseColors[diseaseName]) {
        // assign next palette color
        const color =
          this.colorPalette[this.nextColorIndex % this.colorPalette.length];

        this.diseaseColors[diseaseName] = color;
        this.nextColorIndex++;
      }

      return this.diseaseColors[diseaseName];
    },

    sendTelegramMessage(text) {
      const BOT_TOKEN = process.env.VUE_APP_BOT_TOKEN;
      // For getting chat id https://api.telegram.org/bot<NEW_BOT_TOKEN>/getUpdates
      const CHAT_ID = process.env.VUE_APP_CHAT_ID;

      fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: CHAT_ID,
          text,
          parse_mode: "Markdown",
        }),
      }).catch((err) => console.error("Telegram error", err));
    },
  },
};
</script>
