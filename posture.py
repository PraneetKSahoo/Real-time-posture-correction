import sys
import cv2
import os
import argparse
import requests
import time
import threading
import math
from concurrent.futures import ThreadPoolExecutor
import logging
import tkinter as tk
from tkinter import filedialog
import csv
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    ARDUINO_IP = "http://172.20.10.3"
    DEBOUNCE_SECONDS = 1
    WRONG_POSTURE_THRESHOLD = 2.1
    MIN_POSTURE_CHANGE_DURATION = 0.5
    SIGNAL_COOLDOWN = 5.0
    executor = ThreadPoolExecutor(max_workers=4)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    def send_led_command(command):
        current_time = time.time()
        if current_time - last_sent_time[command] < DEBOUNCE_SECONDS:
            return
        last_sent_time[command] = current_time

        def request_thread():
            url = f"{ARDUINO_IP}/LED={command}"
            for _ in range(3):
                try:
                    response = requests.get(url, timeout=1.0)
                    logging.info(f"Sent {command} to Arduino")
                    print(f"[SIGNAL SENT] Command '{command}' sent to Arduino at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    return
                except requests.exceptions.RequestException as e:
                    print(f"[SIGNAL FAILED] Attempt to send '{command}' failed: {str(e)}")
                    time.sleep(0.1)
            logging.error(f"Failed to send {command} to Arduino after retries.")
            print(f"[SIGNAL FAILED] All attempts to send '{command}' failed")
        executor.submit(request_thread)

    def check_arduino():
        try:
            requests.get(f"{ARDUINO_IP}/", timeout=1.0)
            logging.info("Arduino connected successfully.")
            print("[ARDUINO] Connection successful at startup")
        except requests.exceptions.RequestException:
            logging.warning("Could not connect to Arduino at startup.")
            print("[ARDUINO] Connection failed at startup")

    dir_path = os.path.dirname(os.path.realpath(__file__))
    try:
        sys.path.append(dir_path + '/../bin/python/openpose/Release')
        os.environ['PATH'] = os.environ['PATH'] + ';' + dir_path + '/../x64/Release;' + dir_path + '/../bin;'
        import pyopenpose as op
    except ImportError as e:
        print('Error: OpenPose library not found. Check CMake build and script location.')
        raise e

    parser = argparse.ArgumentParser()
    args = parser.parse_known_args()
    params = {"model_folder": "../models/"}
    opWrapper = op.WrapperPython(op.ThreadManagerMode.Asynchronous)
    opWrapper.configure(params)
    opWrapper.start()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Unable to access webcam.")
        sys.exit(-1)

    fps = 7.5  # Adjusted to match actual capture rate
    print(f"[DEBUG] Using FPS: {fps}")
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    root = tk.Tk()
    root.withdraw()
    video_file_path = filedialog.asksaveasfilename(
        defaultextension=".mp4",
        filetypes=[("MP4 files", "*.mp4")],
        title="Save video output"
    )
    
    video_writer = None
    if video_file_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(video_file_path, fourcc, fps, (frame_width, frame_height))
        print(f"[VIDEO] Recording to {video_file_path} at {fps} FPS")
    else:
        print("[VIDEO] Video recording cancelled.")

    def evaluate_posture(keypoints, angle_threshold=20.0):
        try:
            shoulder_left = keypoints[5]
            shoulder_right = keypoints[2]
            hip_left = keypoints[12]
            hip_right = keypoints[9]

            if -1 in [shoulder_left[0], shoulder_right[0], hip_left[0], hip_right[0]]:
                return "Unknown", None, None

            confidence = sum([shoulder_left[2], shoulder_right[2], hip_left[2], hip_right[2]]) / 4.0

            avg_shoulder = ((shoulder_left[0] + shoulder_right[0]) / 2,
                            (shoulder_left[1] + shoulder_right[1]) / 2)
            avg_hip = ((hip_left[0] + hip_right[0]) / 2,
                       (hip_left[1] + hip_right[1]) / 2)

            delta_y = avg_hip[1] - avg_shoulder[1]
            delta_x = avg_hip[0] - avg_shoulder[0]
            spine_angle = math.degrees(math.atan2(delta_x, delta_y))
            deviation = abs(spine_angle)

            if deviation <= angle_threshold:
                return "Correct", deviation, confidence
            else:
                return "Wrong", deviation, confidence
        except Exception as e:
            logging.error(f"Posture evaluation error: {e}")
            return "Unknown", None, None

    def draw_text_pil(frame, text, position, font_path, font_size, text_color):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_image)

        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"[FONT ERROR] Arial not found, falling back to DejaVuSans")
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)

        draw.text(position, text, font=font, fill=text_color)
        frame_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return frame_bgr

    check_arduino()

    last_sent_time = {"ODD": 0}
    wrong_start_time = None
    signal_sent = False
    last_signal_time = 0
    last_posture_change_time = None
    last_posture_status = None

    data = []
    start_time = time.time()  # Record start time for video timestamp
    frame_count = 0  # For FPS calculation
    last_frame_time = start_time  # For real-time FPS calculation

    def format_elapsed_time(seconds):
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        millis = int((td.total_seconds() % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

    print("[SYSTEM] Posture monitoring started")
    while True:
        ret, frame = cap.read()
        if not ret:
            logging.error("Unable to read from webcam.")
            print("[ERROR] Unable to read from webcam")
            break

        frame_count += 1
        current_time = time.time()
        # Calculate real-time FPS
        elapsed_frame = current_time - last_frame_time
        if elapsed_frame > 0:
            current_fps = 1.0 / elapsed_frame
        else:
            current_fps = 0.0
        last_frame_time = current_time

        # Calculate average FPS every 100 frames for debug
        if frame_count % 100 == 0:
            elapsed = current_time - start_time
            avg_fps = frame_count / elapsed if elapsed > 0 else fps
            print(f"[DEBUG] Average FPS: {avg_fps:.2f}")

        datum = op.Datum()
        datum.cvInputData = frame
        datum_vector = op.VectorDatum()
        datum_vector.append(datum)
        opWrapper.emplaceAndPop(datum_vector)

        keypoints = datum.poseKeypoints
        output_frame = datum.cvOutputData

        posture_status = "Unknown"
        angle_deviation = None
        confidence = None
        if keypoints is not None and len(keypoints) > 0:
            posture_status, angle_deviation, confidence = evaluate_posture(keypoints[0])

        if posture_status != last_posture_status:
            last_posture_change_time = current_time
            last_posture_status = posture_status

        if posture_status == "Wrong":
            if wrong_start_time is None:
                if last_posture_change_time is not None and (current_time - last_posture_change_time >= MIN_POSTURE_CHANGE_DURATION):
                    wrong_start_time = current_time
                    print(f"[POSTURE] Wrong posture confirmed - timing started")
            elif current_time - wrong_start_time >= WRONG_POSTURE_THRESHOLD and not signal_sent:
                if current_time - last_signal_time >= SIGNAL_COOLDOWN:
                    print(f"[POSTURE] Sending signal after {WRONG_POSTURE_THRESHOLD} seconds of wrong posture")
                    send_led_command("ODD")
                    signal_sent = True
                    last_signal_time = current_time
                    wrong_start_time = None
        else:
            if wrong_start_time is not None and (current_time - last_posture_change_time >= MIN_POSTURE_CHANGE_DURATION):
                print("[POSTURE] Posture corrected - resetting tracking")
                wrong_start_time = None
                signal_sent = False

        # Prepare text for overlay
        posture_text = f"Posture: {posture_status}"
        angle_text = f"Angle: {angle_deviation:.2f}°" if angle_deviation is not None else "Angle: N/A"
        conf_text = f"Confidence: {confidence:.2f}" if confidence is not None else "Confidence: N/A"
        fps_text = f"FPS: {current_fps:.2f}"
        time_text = f"Time: {datetime.now().strftime('%H:%M:%S')}"

        font_path = "arial.ttf"
        font_size = 30
        posture_color = (0, 255, 0) if posture_status == "Correct" else (255, 0, 0)
        text_color = (255, 255, 255)

        # Draw text on frame
        output_frame = draw_text_pil(output_frame, posture_text, (50, 50), font_path, font_size, posture_color)
        output_frame = draw_text_pil(output_frame, angle_text, (50, 100), font_path, font_size, text_color)
        output_frame = draw_text_pil(output_frame, conf_text, (50, 150), font_path, font_size, text_color)
        output_frame = draw_text_pil(output_frame, fps_text, (50, 200), font_path, font_size, text_color)
        output_frame = draw_text_pil(output_frame, time_text, (50, 250), font_path, font_size, text_color)

        logging.info(f"Posture: {posture_status}, Angle: {angle_deviation if angle_deviation is not None else 'N/A'} deg, Confidence: {confidence if confidence is not None else 'N/A'}")

        if video_writer is not None:
            video_writer.write(output_frame)

        #now = datetime.now()
        #date_str = now.strftime("%Y-%m-%d")
        #time_str = now.strftime("%H:%M:%S.%f")[:-3]
        #elapsed_time = format_elapsed_time(current_time - start_time)

        #data.append((
            #date_str,
            #time_str,
            #elapsed_time,
            #posture_status,
            #round(angle_deviation, 2) if angle_deviation else "N/A",
            #round(confidence, 2) if confidence else "N/A"
        #))
        
        unix_timestamp = time.time()  # seconds since epoch
        elapsed_time = format_elapsed_time(current_time - start_time)

        data.append((
            unix_timestamp,
            elapsed_time,
            posture_status,
            round(angle_deviation, 2) if angle_deviation else "N/A",
            round(confidence, 2) if confidence else "N/A"
        ))


        cv2.imshow('Posture Monitor', output_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[SYSTEM] Quitting posture monitoring")
            break

    cap.release()
    if video_writer is not None:
        video_writer.release()
        print(f"[VIDEO] Video saved to {video_file_path}")
    cv2.destroyAllWindows()

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        title="Save posture data"
    )

    if file_path:
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Unix Timestamp", "Video Timestamp", "Posture", "Angle", "Confidence"])
            writer.writerows(data)
        print(f"[DATA] Data saved to {file_path}")
    else:
        print("[DATA] Save cancelled.")

except Exception as e:
    logging.error(f"Program error: {e}")
    print(f"[SYSTEM ERROR] {str(e)}")
    sys.exit(-1)