# Real-Time Posture Correction System

This project uses real-time human pose estimation to monitor posture from a webcam, classify it as **Correct** or **Wrong** based on spinal angle, provide visual feedback, record video, log data to CSV, and alert via Wi-Fi to an **Arduino** board that lights up LEDs during prolonged bad posture.

https://github.com/PraneetKSahoo/Real-time-posture-correction

## Features

- Real-time pose detection using [**OpenPose**](https://github.com/CMU-Perceptual-Computing-Lab/openpose)
- Spine inclination angle calculation (shoulder-to-hip deviation)
- On-screen overlay: posture status, angle, confidence, FPS, timestamp
- Wrong posture alert after **3 seconds** persistence → HTTP request to Arduino
- Arduino activates **mini coin vibration motors** (3V, 12000 RPM) for **1.5 seconds** on alert (with debounce/cooldown)
- Video recording + CSV logging of posture data

## Hardware Required

- Computer with webcam
- [**Arduino UNO WiFi Rev2**](https://docs.arduino.cc/hardware/uno-wifi-rev2) (or compatible board using WiFiS3 library, e.g. UNO R4 WiFi)
- **4× mini coin vibration motors** (3V DC, ~12000 RPM, flat/button type — e.g. 10×3 mm models commonly sold on Amazon/AliExpress)
- Appropriate wiring/resistors if needed (most coin motors can be driven directly from Arduino pins at 3V, but check current draw)
- Same Wi-Fi network for PC and Arduino

## Setup & Run

2. **Arduino**
   - Open `fbm.ino`
   - Edit `ssid` and `password`
   - Connect vibration motors to digital pins 8–11 (positive to pin, negative to GND; most 3V coin motors draw <100 mA so direct drive is usually fine — add a small transistor/driver if using many or high-current ones)
   - Upload to your board
   - Open Serial Monitor → note the IP

## How It Works – Feedback

When bad posture is detected for ≥2.1 seconds:
- Python script sends HTTP GET to Arduino (`/LED=ODD` — endpoint name kept for simplicity)
- Arduino turns vibration motors **ON** (HIGH) for 1.5 seconds → user feels haptic buzz as alert
- Motors turn **OFF** automatically
- 5-second cooldown prevents constant buzzing
