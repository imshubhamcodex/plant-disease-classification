# Raspberry Pi YOLO + LoRa Setup Guide

This document provides **step-by-step instructions** to set up a Raspberry Pi for running a **YOLO (Ultralytics) NCNN-based inference pipeline** with **LoRa (SX127x)** support, optional **camera preview over VNC**, and **Python 3.11 via pyenv**.

---

## 1. Network & VNC Setup

### Step 1: Get Raspberry Pi IP Address

```bash
ifconfig
```

Copy the `inet` address under `wlan0`.

### Step 2: Enable VNC

```bash
raspi-config
```

Navigate to:

- **Interface Options** → **VNC** → **Enable**

### Step 3: Connect via RealVNC

Use the copied `inet` IP address to log in using **RealVNC Viewer**.

---

## 2. Keyboard, Localization & SPI Configuration

From the Raspberry Pi desktop:

### Step 4.1: Keyboard Layout

- **Pi Logo** → **Preferences** → **Control Center** → **Keyboard** → **English (US)**

### Step 4.2: Localization

- **Pi Logo** → **Preferences** → **Control Center** → **Localization** → **English (US)**

### Step 4.3: Enable SPI (Required for LoRa)

- **Pi Logo** → **Preferences** → **Control Center** → **Interfaces** → **Enable SPI**

### Step 5: Reboot

```bash
sudo reboot
```

---

## 3. System Update

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 4. Install pyenv & Python 3.11

### Step 7: Install pyenv

```bash
curl https://pyenv.run | bash
```

### Step 8: Configure pyenv

Add the following to `~/.bashrc`:

```bash
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
source ~/.bashrc
```

### Step 8.6: Install Python Build Dependencies

```bash
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev tk-dev libffi-dev liblzma-dev
```

### Step 8.7: GPIO & LoRa Dependencies

```bash
sudo apt install -y swig python3-dev liblgpio-dev
```

### Step 8.8: Install Python 3.11.8

```bash
pyenv install 3.11.8
```

---

## 5. Project Directory & Python Environment

### Step 9: Create Workspace

```bash
mkdir YOLO
cd YOLO
```

### Step 10: Set Local Python Version

```bash
pyenv local 3.11.8
```

### Step 11: Create Virtual Environment

```bash
cd YOLO
python --version   # Should show Python 3.11.8
python -m venv --system-site-packages venv
source venv/bin/activate
```

---

## 6. Install Python Dependencies

### Step 12.1: YOLO & Torch

```bash
pip install ultralytics==8.3.70 torch==2.5.0 torchvision==0.20.0 --no-cache-dir
```

### Step 12.2: NCNN, LoRa & Crypto

```bash
pip install ncnn spidev==3.8 rpi-lgpio==0.6 lgpio==0.2.2.0 \
LoRaRF==1.4.0 pycryptodome openpyxl
```

---

## 7. Clone Project & Model Export

### Step 13.1: Clone Repository

```bash
git clone https://github.com/imshubhamcodex/plant-disease-classification.git
cd plant-disease-classification/rpi4
```

### Step 13.3: Disable LoRa Interrupt (Critical Fix)

```bash
scp SX127x.py /home/rpi4/YOLO/venv/lib/python3.11/site-packages/LoRaRF/SX127x.py
```

### Step 13.4: Export YOLO Model to NCNN

```bash
yolo export model=best.pt format=ncnn imgsz=128
```

> **Note:** `imgsz=128` must match `INFERENCE_SIZE` in the code.

---

## 8. Running the Application

### Step 14.1: Terminal-Only Mode (No Camera Preview)

Comment out the following line in `main.py`:

```python
cv2.imshow("Drone Live Feed", frame)
```

### Step 14.2: Camera Preview Mode

- Connect via **RealVNC**
- Activate the virtual environment

### Step 15.1: Run the Program

```bash
python main.py
```

---

## Notes

- SPI **must** be enabled for SX127x LoRa communication.
- VNC is required for OpenCV GUI preview.
- NCNN export significantly improves inference speed on Raspberry Pi.

---

## Author

**Shubham Kumar**
