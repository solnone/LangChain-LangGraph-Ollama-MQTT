/**
   ESP32 Servo Example for Wokwi
   
   https://wokwi.com/arduino/projects/365724802866330625
*/
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// WiFi
const char* ssid ="Wokwi-GUEST";
const char* password = "";

// MQTT
const char* mqtt_server = "test.mosquitto.org";

const char* SUBTOPIC_LED_CTL = "esp32-solomon/LED_CTL";
const char* SUBTOPIC_DOOR_CTL = "esp32-solomon/DOOR_CTL";

const char* SUBTOPIC_LED = "esp32-solomon/LED";
const char* SUBTOPIC_DOOR = "esp32-solomon/DOOR";


WiFiClient espClient;
PubSubClient client(espClient);

// LED
const int LED_PIN = 13;

// Servo
Servo servo;  // create servo object to control a servo

int SERVO_PIN = 2;  // analog pin used to connect the potentiometer

int old_led = -1;
int old_door = -1;

void setup_wifi() {
  delay(10);
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password, 6);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Attempting MQTT connection...");
    String clientId = "esp32-sol-clientId-";
    clientId += String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      Serial.println("Connected");
      client.subscribe(SUBTOPIC_LED_CTL);
      client.subscribe(SUBTOPIC_DOOR_CTL);
    } else {
      delay(5000);
    }
  }
}

void callback(char *topic, byte *payload, unsigned int length) {
  Serial.print("Receive Topic: ");
  Serial.println(topic);

  payload[length] = '\0';
  char *str = (char *) payload;
  Serial.print("Payload: ");
  Serial.println(str);
  if (!strcmp(topic, SUBTOPIC_LED_CTL)) {
    int value = atoi(str);
    if (value != -1) {
      digitalWrite(LED_PIN, value);
      delay(250);
      ledState(-1);
    }
  } else if (!strcmp(topic, SUBTOPIC_DOOR_CTL)) {
    int value = atoi(str);
    if (value != -1) {
      servo.write(value);
      delay(250);
      doorState(-1);
    }
  }
}

void setup() {
  Serial.begin(115200);
  randomSeed(micros());

  pinMode(LED_PIN, OUTPUT);

  servo.attach(SERVO_PIN, 500, 2400);  // attaches the servo on pin 13 to the servo object
  
  servo.write(2);

  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void ledState(int old) {
  int led = digitalRead(LED_PIN);
  if (old != led) {
    client.publish(SUBTOPIC_LED, String(led).c_str(), 2);
    delay(250);
  }
  old_led = led;

}

void doorState(int old) {
  int door = servo.read();
  if (old != door) {
    client.publish(SUBTOPIC_DOOR, String(door).c_str(), 2);
    delay(250);
  }
  old_door = door;
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  ledState(old_led);
  doorState(old_door);
  client.loop();
  delay(500);
}
