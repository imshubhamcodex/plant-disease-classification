import time
from LoRaRF import SX127x
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# AES configuration
AES_KEY = bytes([
    0x2B, 0x7E, 0x15, 0x16,
    0x28, 0xAE, 0xD2, 0xA6,
    0xAB, 0xF7, 0x8C, 0x53,
    0x4A, 0xF1, 0xE1, 0x1A
])

AES_IV_MASTER = bytes([
    0x00, 0x01, 0x02, 0x03,
    0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B,
    0x0C, 0x0D, 0x0E, 0x0F
])

class LoRaComm:
    def __init__(self, bus=0, cs=0, reset=17, dio0=4, freq=433000000):
        self.lora = SX127x()

        if not self.lora.begin(bus, cs, reset, dio0):
            raise RuntimeError("LoRa initialization failed")

        self.lora.setFrequency(freq)

    def encrypt_and_send(self, msg: str):
        print("[LoRa TX]: ", msg)
        
        padded_data = pad(msg.encode(), 16)

        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV_MASTER)
        encrypted_data = cipher.encrypt(padded_data)

        blocks = [
            encrypted_data[i:i+16]
            for i in range(0, len(encrypted_data), 16)
        ]

        for i, block in enumerate(blocks):
            self.lora.beginPacket()
            self.lora.write(list(block), 16)
            self.lora.endPacket()
            self.lora.wait()
            print(
                f"[LoRa TX]: Block {i+1}/{len(blocks)}: "
                + " ".join(f"{b:02X}" for b in block)
            )
            time.sleep(0.1)
        
        
