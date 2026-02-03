import time
import random
import math
import cv2
from config import *
from ultralytics import YOLO
from comm import LoRaComm
import subprocess
import threading
from threading import Lock
import queue
import numpy as np
import os
import RPi.GPIO as GPIO
from openpyxl import Workbook, load_workbook


os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMBA_NUM_THREADS"] = "2"



LED_PIN = 24  # GPIO pin your LED is connected to
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# =========================================================
# INIT
# =========================================================
# yolo export model=best.pt format=ncnn imgsz=128
model = YOLO("best_ncnn_model", task="classify")

# Lora Comm Init
comm = LoRaComm()
lora_tx_lock = Lock()

# TX Buffer
tx_buffer = []
last_tx_time = 0

# FPS Calculation
prev_time = time.time()
fps = 0.0


# =========================================================
# DATA LOG INIT
# =========================================================
# Excel file path
EXCEL_PATH = "plant_data.xlsx"
# Initialize Excel
if os.path.exists(EXCEL_PATH):
    wb = load_workbook(EXCEL_PATH)
    ws = wb.active
else:
    wb = Workbook()
    ws = wb.active
    ws.append(["Timestamp", "Latitude", "Longitude", "Cell", "Disease", "Infected Area", "Healthy Area", "Leaves"])

def log_cell_to_excel(cell, data):
    lat, lon = data["gps"]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    if not data["diseases"]:
        ws.append([
            ts, lat, lon,
            f"{cell}",
            "NO DATA",
            0, 0, 0
        ])
    else:
        for disease, s in data["diseases"].items():
            ws.append([
                ts,
                lat,
                lon,
                f"{cell}",
                disease,
                int(s["infected_area"] / px_to_area_scale),
                int(s["healthy_area"] / px_to_area_scale),
                s["leaves"]
            ])

    wb.save(EXCEL_PATH)



# =========================================================
# CAMERA INIT
# =========================================================
frame_q = queue.Queue(maxsize=1)
stop_event = threading.Event()

if LIVE_STREAM:
    print("[CAM]: Using Pi Camera (rpicam-vid)")

    cam_proc = subprocess.Popen(
        [
            "rpicam-vid",
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--framerate", "10",
            "--codec", "yuv420",
            "--nopreview",
            "-t", "0",
            "-o", "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    def cam_reader():
        while not stop_event.is_set():
            raw = cam_proc.stdout.read(FRAME_SIZE)
            if len(raw) != FRAME_SIZE:
                continue
            try:
                yuv = np.frombuffer(raw, np.uint8).reshape((int(HEIGHT * 1.5), WIDTH))
                frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            except:
                time.sleep(0.5)
                continue

            if frame_q.full():
                frame_q.get_nowait()
            frame_q.put(frame)

    threading.Thread(target=cam_reader, daemon=True).start()

else:
    print("[CAM]: Using video file")
    cap = cv2.VideoCapture("./apple.mp4")


# =========================================================
# GPS SIMULATION
# =========================================================
# GRID SCAN STATE (S-PATTERN)
last_gps_update_time = 0
scan_gx = 0
scan_gy = 0
scan_dir = 1   # +1 = left→right, -1 = right→left
scan_done = False

def fake_gps():
    global scan_gx, scan_gy, scan_dir, scan_done
    global drone_lat, drone_lon, last_gps_update_time

    if scan_done:
        return drone_lat, drone_lon

    now = time.time()
    # ONLY advance the grid if the interval has passed
    if now - last_gps_update_time >= GPS_UPDATE_INTERVAL:
        
        # Convert current grid cell to GPS
        drone_lat, drone_lon = grid_to_gps(scan_gx, scan_gy)

        # -------- ADVANCE TO NEXT CELL --------
        scan_gx += scan_dir

        # End of row reached
        if scan_gx >= GRID_COLS or scan_gx < 0:
            scan_dir *= -1
            scan_gx += scan_dir
            scan_gy += 1

            if scan_gy >= GRID_ROWS:
                scan_done = True
                scan_gx += 1
                print("[SCAN]: Grid coverage complete")
        
        last_gps_update_time = now # Reset the timer

    return drone_lat, drone_lon


# =========================================================
# YOLO CLS
# =========================================================
def yolo_cls_infer(frame, prob_thresh=0.9, max_classes=5):
    results = model.predict(frame, imgsz=INFERENCE_SIZE, verbose=False)
    
    detections = []
    r = results[0]
    
    if r.probs is None:
        return detections

    probs = r.probs.data.cpu().numpy()
    class_ids = probs.argsort()[::-1]

    h, w = frame.shape[:2]
    count = 0

    for cls_id in class_ids:
        conf = probs[cls_id]
        if conf < prob_thresh or count >= max_classes:
            break

        disease = r.names[int(cls_id)]

        x_offset = int((count % 3) * w * 0.15)
        y_offset = int((count // 3) * h * 0.15)

        x1 = int(w * 0.2 + x_offset)
        y1 = int(h * 0.2 + y_offset)
        x2 = int(w * 0.5 + x_offset)
        y2 = int(h * 0.5 + y_offset)

        area = (x2 - x1) * (y2 - y1)
        infected_px = area * conf
        healthy_px = area * (1 - conf)

        detections.append((disease, infected_px, healthy_px, conf, (x1, y1, x2, y2)))
        print(f"[YOLO-CLS]: Classify {disease} ({conf:.2f})")
        count += 1

    return detections

def yolo_infer(frame):
    return yolo_cls_infer(frame) if YOLO_CLS else []

# =========================================================
# GRID / GPS
# =========================================================
def gps_to_xy(lat, lon):
    dlat = math.radians(lat - LAT0)
    dlon = math.radians(lon - LON0)
    x = EARTH_RADIUS * dlon * math.cos(math.radians(LAT0))
    y = EARTH_RADIUS * dlat
    return x, y

def gps_to_grid(lat, lon):
    x, y = gps_to_xy(lat, lon)
    if x < 0 or y < 0 or x > FIELD_WIDTH_M or y > FIELD_HEIGHT_M:
        return (-1, -1)
    return int(x // CELL_W), int(y // CELL_H)

def grid_to_gps(gx, gy):
    x = (gx + 0.5) * CELL_W
    y = (gy + 0.5) * CELL_H
    lat = LAT0 + math.degrees(y / EARTH_RADIUS)
    lon = LON0 + math.degrees(x / (EARTH_RADIUS * math.cos(math.radians(LAT0))))
    return lat, lon

# =========================================================
# TRACKING
# =========================================================
def iou(a, b):
    xA, yA = max(a[0], b[0]), max(a[1], b[1])
    xB, yB = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0.0
    areaA = (a[2]-a[0]) * (a[3]-a[1])
    areaB = (b[2]-b[0]) * (b[3]-b[1])
    return inter / (areaA + areaB - inter)

def center_dist(a, b):
    ax, ay = (a[0]+a[2])/2, (a[1]+a[3])/2
    bx, by = (b[0]+b[2])/2, (b[1]+b[3])/2
    return math.hypot(ax - bx, ay - by)

def match_or_create_leaf(cell, bbox):
    global leaf_id_counter
    now = time.time()
    tracks = leaf_tracks.setdefault(cell, {})

    for lid, t in tracks.items():
        if iou(t["bbox"], bbox) > IOU_THRESH or center_dist(t["bbox"], bbox) < MAX_CENTER_DIST:
            t["bbox"] = bbox
            t["last_seen"] = now
            return lid, False

    leaf_id_counter += 1
    tracks[leaf_id_counter] = {
        "bbox": bbox,
        "last_seen": now,
        "diseases": {}   # track per-leaf disease
    }
    return leaf_id_counter, True


def cleanup_tracks():
    now = time.time()
    for cell in list(leaf_tracks.keys()):
        for lid in list(leaf_tracks[cell].keys()):
            if now - leaf_tracks[cell][lid]["last_seen"] > LEAF_TIMEOUT:
                del leaf_tracks[cell][lid]
        if not leaf_tracks[cell]:
            del leaf_tracks[cell]

# =========================================================
# GRID AGGREGATION
# =========================================================
def update_grid(cell, leaf_id, disease, infected_px, healthy_px):
    grid = grid_data.setdefault(cell, {
        "gps": grid_to_gps(*cell),
        "diseases": {}
    })

    d = grid["diseases"].setdefault(disease, {
        "infected_area": 0,
        "healthy_area": 0,
        "leaves": 0
    })

    leaf = leaf_tracks[cell][leaf_id]
    prev = leaf["diseases"].get(disease)

    if prev is None:
        # first time this leaf-disease pair
        leaf["diseases"][disease] = (infected_px, healthy_px)
        d["infected_area"] += infected_px
        d["healthy_area"] += healthy_px
        d["leaves"] += 1
    else:
        # update instead of add
        old_inf, old_hea = prev
        d["infected_area"] += infected_px - old_inf
        d["healthy_area"] += healthy_px - old_hea
        leaf["diseases"][disease] = (infected_px, healthy_px)

# =========================================================
# TRANSMISSION
# =========================================================
def try_transmit():
    global last_tx_time, tx_buffer

    if not tx_buffer:
        return

    now = time.time()
    if now - last_tx_time > TX_INTERVAL:   # Send every TX_INTERVAL seconds
        final_payload = "".join(tx_buffer)
        
        with lora_tx_lock:
            comm.encrypt_and_send(final_payload)
            tx_buffer.clear()
            last_tx_time = now
            print("[TX]: SENT TO BASE\n")

def save_grid(cell, data):
    global MSG_ID
    lat, lon = data["gps"]
    gx, gy = cell
    payload = f"[ID]:{MSG_ID} | CELL {gx, gy} | GPS {int(lat*gps_scale)},{int(lon*gps_scale)}"

    if data["diseases"]:
        for disease, s in data["diseases"].items():
            payload += f" | {disease} : {int(s['infected_area']/px_to_area_scale)} : {int(s['healthy_area']/px_to_area_scale)} : {s['leaves']}"
    else:
        payload += " | NO DATA"
        
    payload += "\n"
    tx_buffer.append(payload)
    MSG_ID += 1
    print("[TX-BUFFER]: QUEUED")
    
    
def blink_led(times=1, duration=0.2):
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(duration)


# =========================================================
# MAIN LOOP
# =========================================================
print("\n================= Drone Grid-Level Plant Disease Classification Started =================\n")
try:
    while True:

        # ================= FRAME SOURCE =================
        if LIVE_STREAM:
            if frame_q.empty():
                continue
            frame = frame_q.get()
        else:
            ret, frame = cap.read()
            if not ret:
                break
        # ================================================
        
        
        # ================= GPS & GRID =================
        lat, lon = fake_gps()
        cell = gps_to_grid(lat, lon)
        if cell == (-1, -1):
            continue
        
        # if scan finished, flush last cell exactly once
        if scan_done and current_cell is not None:
            data = grid_data.pop(
                current_cell,
                {"gps": grid_to_gps(*current_cell), "diseases": {}}
            )
            print(f"[SCAN]: Final cell {current_cell} : SEND DATA")
            
            log_cell_to_excel(current_cell, data)   # Sent to Log
            save_grid(current_cell, data)           # Sent to Base
            try_transmit()                          # Sent to Base
            break
        # ==============================================
        
        detections = yolo_infer(frame)  # Detection

        for disease, infected, healthy, conf, bbox in detections: # Create Dataset of current cell
            
            # Draw on cam feed
            x1, y1, x2, y2 = bbox
            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            # Label text
            label = f"{disease} ({conf*100:.1f}%)"
            # Background for text
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), (0, 0, 255), -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Noramal flow matching & updating leaf
            leaf_id, is_new_leaf = match_or_create_leaf(cell, bbox)
            update_grid(cell, leaf_id, disease, infected, healthy)

        cleanup_tracks()                # Stale Leaf Cleanup


        # ================= CELL TRANSITION =================
        if current_cell is None:
            current_cell = cell

        elif cell != current_cell:
            data = grid_data.pop(
                current_cell,
                {"gps": grid_to_gps(*current_cell), "diseases": {}}
            )
            print(f"[CELL]: Leaving cell {current_cell} : SEND DATA")
            save_grid(current_cell, data)
            
            # ---------- EXCEL LOG ----------
            log_cell_to_excel(current_cell, data)
            # -----------------------------
            
            # Blink LED parallel
            threading.Thread(target=blink_led, args=(1, 0.2), daemon=True).start()
        
            current_cell = cell
        # ==================================================
        
        
        # ================= FPS ==============================
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1 / (now - prev_time))
        prev_time = now

        cv2.putText(frame, f"FPS: {fps:.2f}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        
        cell_text = f"Cell: ({cell[0]}, {cell[1]})"
        cv2.putText(frame, cell_text, (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
        cv2.putText(frame, f"Number of Detections: {len(detections)}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        cv2.imshow("Drone Live Feed", frame)
        # ==================================================
        
        
        # ================= Data Transmission =================
        try_transmit()
        # =================================================== 
        
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
finally:
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    cv2.destroyAllWindows()
