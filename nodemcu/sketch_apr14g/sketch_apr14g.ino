// ================= LoRa + AES RX =================

// LoRa (SX1278)
// RST  -> D0
// DIO0 -> D1
// SCK  -> D5
// MISO -> D6
// MOSI -> D7
// NSS  -> D8

#include <SPI.h>
#include <LoRa.h>
#include <AESLib.h>

// Add Cloud
#include <ESP8266WiFi.h>
#include <Firebase_ESP_Client.h>

// ================= WiFi =================
#define WIFI_SSID "TECNO POP 8"
#define WIFI_PASSWORD "donotask"

// ================= Firebase =================
#define API_KEY "AIzaSyAeyN_7vFm6wJaP7mDW8SDBoYnp4Qsr5Is"
#define DATABASE_URL "https://lora-rx-default-rtdb.asia-southeast1.firebasedatabase.app"

// Firebase objects
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;
FirebaseJson json;

// ================= LoRa Pins =================
#define LORA_SS    15   // D8
#define LORA_RST   16   // D0
#define LORA_DIO0  2    // D1

// ================= AES =================
AESLib aesLib;
const int BLOCK_SIZE = 16;

byte aes_key[] = {
  0x2B, 0x7E, 0x15, 0x16,
  0x28, 0xAE, 0xD2, 0xA6,
  0xAB, 0xF7, 0x8C, 0x53,
  0x4A, 0xF1, 0xE1, 0x1A
};

byte aes_iv[BLOCK_SIZE];

byte aes_iv_master[BLOCK_SIZE] = {
  0x00, 0x01, 0x02, 0x03,
  0x04, 0x05, 0x06, 0x07,
  0x08, 0x09, 0x0A, 0x0B,
  0x0C, 0x0D, 0x0E, 0x0F
};

int pkt_count = 0;
// ================= Message Buffer =================
#define MAX_BLOCKS 50

byte decryptedBlocks[MAX_BLOCKS][BLOCK_SIZE];
int blockIndex = 0;
unsigned long lastPacketTime = 0;
const unsigned long TIMEOUT_MS = 3000;

// ================= Setup =================
void setup() {
  Serial.begin(115200);
  delay(500);

  // ---- WiFi ----
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print(F("Connecting to WiFi"));
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(F("."));
  }
  Serial.println(F("\nWiFi Connected"));

  // ---- Firebase ----
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  auth.user.email = "hello@gmail.com";
  auth.user.password = "123456";
  
  // config.signer.test_mode = true;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // ---- LoRa ----
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println(F("LoRa init failed"));
    while (true);
  }

  Serial.println(F("LoRa AES RX Ready"));
}

// ================= Loop =================
void loop() {

  int packetSize = LoRa.parsePacket();
  if (packetSize == BLOCK_SIZE) {

    if (blockIndex == 0) {
      memcpy(aes_iv, aes_iv_master, BLOCK_SIZE);
    }

    byte encrypted[BLOCK_SIZE];
    for (int i = 0; i < BLOCK_SIZE; i++) {
      encrypted[i] = LoRa.read();
    }
    pkt_count += 1;
    Serial.print("Received HEX " + String(pkt_count) + " : ");
    printHex(encrypted, BLOCK_SIZE);

    byte decrypted[BLOCK_SIZE];
    aesLib.decrypt(encrypted, BLOCK_SIZE, decrypted, aes_key, 128, aes_iv);

    if (blockIndex < MAX_BLOCKS) {
      memcpy(decryptedBlocks[blockIndex], decrypted, BLOCK_SIZE);
      blockIndex++;
      lastPacketTime = millis();
    }
  }

  // Timeout → process message
  if (blockIndex > 0 && millis() - lastPacketTime > TIMEOUT_MS) {
    processMessage();
    blockIndex = 0;
    pkt_count = 0;
  }
}

// ================= Message Processing =================
void processMessage() {
  byte* lastBlock = decryptedBlocks[blockIndex - 1];
  int padLen = lastBlock[BLOCK_SIZE - 1];

  if (!validatePadding(lastBlock, padLen)) {
    Serial.println(F("Invalid padding"));
    return;
  }

  int totalLength = blockIndex * BLOCK_SIZE - padLen;
  String msg = "";

  int count = 0;
  for (int b = 0; b < blockIndex; b++) {
    for (int i = 0; i < BLOCK_SIZE && count < totalLength; i++) {
      msg += (char)decryptedBlocks[b][i];
      count++;
    }
  }

  Serial.println(F("Decrypted Message: "));
  Serial.println(msg);

  // Send to cloud
  sendToFirebase(msg);
}

// ================= Helpers =================
bool validatePadding(byte* data, int padLen) {
  if (padLen < 1 || padLen > BLOCK_SIZE) return false;
  for (int i = 1; i <= padLen; i++) {
    if (data[BLOCK_SIZE - i] != padLen) return false;
  }
  return true;
}

void printHex(byte* data, int length) {
  for (int i = 0; i < length; i++) {
    if (data[i] < 0x10) Serial.print("0");
    Serial.print(data[i], HEX);
    Serial.print(" ");
  }
  Serial.println("");
}

void sendToFirebase(String msg) {
  String clean_msg = "";
  for (int i = 0; i < msg.length(); i++) {
    char c = msg[i];
    if (c >= 32 && c <= 126) {
      clean_msg += c;
    }
  }
  json.set("payload", clean_msg);
  json.set("gw_ts/.sv", "timestamp");

  if (Firebase.RTDB.pushJSON(&fbdo, "/rx", &json)) {
    Serial.print(F("Firebase PUSH OK\n"));
  } else {
    Serial.println(F("Firebase ERROR: "));
    Serial.println(fbdo.errorReason());
  }
}