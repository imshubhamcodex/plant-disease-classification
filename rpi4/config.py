# =========================================================
# CONFIGURATION
# =========================================================
# Grid definition (100m x 100m field, 1m x 1m cells)
GRID_ROWS = 20
GRID_COLS = 20
FIELD_WIDTH_M = 100.0
FIELD_HEIGHT_M = 100.0

CELL_W = FIELD_WIDTH_M / GRID_COLS
CELL_H = FIELD_HEIGHT_M / GRID_ROWS

# Earth model for GPS <-> meter conversion
EARTH_RADIUS = 6378137

# Bottom-left GPS reference of the field
LAT0 = 22.572300
LON0 = 88.431200

# Transmission control
# SEND_INTERVAL = 1.0        # flush data after seconds
DELTA_THRESH = 3.0           # % change threshold
FRAME_DELAY = 0.2            # seconds per frame

# Leaf deduplication thresholds
IOU_THRESH = 0.5
MAX_CENTER_DIST = 40         # pixels from two bounding boxes
LEAF_TIMEOUT = 3.0           # for tracks clean up after seconds
TX_INTERVAL = 7.0           # seconds (slightly > RX listen window)

# =========================================================
# GLOBAL STATE
# =========================================================
grid_data = {}               # Aggregated disease data per grid cell
leaf_tracks = {}             # Active leaf tracks per cell
current_cell = None          # Cell where drone currently resides
leaf_id_counter = 0
px_to_area_scale = 1000    # scale factor to convert pixel area to actual area
gps_scale = 100000           # scale factor to convert GPS coordinates
MSG_ID = 1
# =========================================================
# GPS SIMULATION
# =========================================================
drone_lat = LAT0
drone_lon = LON0
GPS_UPDATE_INTERVAL = 3.0   # Spent 3 seconds in each grid cell
# =========================================================
# CAMERA CONFIG
# =========================================================
WIDTH, HEIGHT = 640, 480
FRAME_SIZE = int(WIDTH * HEIGHT * 1.5)
INFERENCE_SIZE = 128  # imgsz=128 matches to this ->  # yolo export model=best.pt format=ncnn imgsz=128

# =========================================================
# YOLO Classifier Model
# =========================================================
YOLO_CLS = True
LIVE_STREAM = True   # True = Pi camera (rpicam-vid), False = video file