#include <WiFiS3.h>
#include <WiFiServer.h>

const char* ssid = "iPhone v";         // Replace with your Wi-Fi network
const char* password = "valbashir";    // Replace with your Wi-Fi password

WiFiServer server(80); // Web server on port 80

const int greenLED[] = {8, 9, 10, 11}; // Green LEDs for ODD (Wrong posture)
const int numLEDs = 4;
const unsigned long ledDuration = 1500; // LED ON time in milliseconds

unsigned long ledOffTime = 0;
unsigned long curTime;
bool ledOn = false;

void setup() {
    Serial.begin(9600);
    delay(1000);

    // Initialize LED pins
    for (int i = 0; i < numLEDs; i++) {
        pinMode(greenLED[i], OUTPUT);
        digitalWrite(greenLED[i], LOW);
    }

    connectToWiFi();
    server.begin();
    Serial.println("Web server started");
}

void connectToWiFi() {
    Serial.print("Connecting to WiFi...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nConnected to WiFi!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
}

void loop() {
    // Reconnect if WiFi is lost
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected. Reconnecting...");
        WiFi.disconnect();
        connectToWiFi();
        server.begin();
    }

    WiFiClient client = server.available();
    if (client) {
        String request = "";
        while (client.connected()) {
            if (client.available()) {
                char c = client.read();
                request += c;
                if (request.endsWith("\r\n\r\n")) break;
            }
        }

        Serial.println("Request received: " + request);

        if (request.indexOf("GET /LED=ODD") != -1) {
            ledOffTime = millis() + ledDuration;
        }

        client.println("HTTP/1.1 200 OK");
        client.println("Content-Type: text/html");
        client.println();
        client.println("<h1>LED Control Successful</h1>");
        client.stop();
        Serial.println("Client disconnected");
    }

    curTime = millis();
    if (ledOn && curTime >= ledOffTime){
        for (int i = 0; i < numLEDs; i++) digitalWrite(greenLED[i], LOW);
        Serial.println("Green LEDs OFF");
        ledOn = false;
    }
    if ((!ledOn) && curTime < ledOffTime){
        for (int i = 0; i < numLEDs; i++) digitalWrite(greenLED[i], HIGH);
        Serial.println("Green LEDs ON (Wrong posture)");
        ledOn = true;
    }
}
