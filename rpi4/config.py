# =========================================================
# CONFIGURATION
# =========================================================
# Grid definition (100m x 100m field, 1m x 1m cells)
GRID_ROWS = 10
GRID_COLS = 10
FIELD_WIDTH_M = 100.0
FIELD_HEIGHT_M = 100.0

CELL_W = FIELD_WIDTH_M / GRID_COLS
CELL_H = FIELD_HEIGHT_M / GRID_ROWS

# Earth model for GPS <-> meter conversion
EARTH_RADIUS = 6378137

# Bottom-left GPS reference of the field
LAT0 = 22.572300
LON0 = 88.431200
# =========================================================
# GLOBAL STATE
# =========================================================
grid_data = {}               # Aggregated disease data per grid cell
current_cell = None          # Cell where drone currently resides
px_to_area_scale = 1000    # scale factor to convert pixel area to actual area
gps_scale = 100000           # scale factor to convert GPS coordinates
MSG_ID = 1

# =========================================================
# GPS SIMULATION
# =========================================================
drone_lat = LAT0
drone_lon = LON0
GPS_UPDATE_INTERVAL = 5.0   # Spent 2 seconds in each grid cell

# =========================================================
# CAMERA CONFIG
# =========================================================
WIDTH, HEIGHT = 640, 480
FRAME_SIZE = int(WIDTH * HEIGHT * 1.5)
INFERENCE_SIZE = 320  # imgsz=128 matches to this ->  # yolo export model=best.pt format=ncnn imgsz=128

# =========================================================
# YOLO Classifier Model
# =========================================================
YOLO_CLS = True
LIVE_STREAM = True   # True = Pi camera (rpicam-vid), False = video file