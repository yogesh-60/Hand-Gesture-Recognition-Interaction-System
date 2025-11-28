import cv2
import mediapipe as mp
import pyautogui
import subprocess
import os
import time
import sys
import math
from collections import deque
import numpy as np
import threading

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

last_gesture = None
gesture_cooldown = 1.0

last_action_time = {}
action_cooldown = 3

NUM_FRAMES_SMOOTH = 5
landmark_history = deque(maxlen=NUM_FRAMES_SMOOTH)

def average_landmarks(landmark_list):
    return np.mean(np.array(landmark_list), axis=0)

def count_fingers(hand_landmarks):
    fingers = []
    tip_ids = [4, 8, 12, 16, 20]

    if hand_landmarks[tip_ids[0]][0] < hand_landmarks[tip_ids[0] - 1][0]:
        fingers.append(1)
    else:
        fingers.append(0)

    for i in range(1, 5):
        if hand_landmarks[tip_ids[i]][1] < hand_landmarks[tip_ids[i] - 2][1]:
            fingers.append(1)
        else:
            fingers.append(0)
    return fingers

def can_perform_action(action_name):
    now = time.time()
    last_time = last_action_time.get(action_name, 0)
    if now - last_time > action_cooldown:
        last_action_time[action_name] = now
        return True
    return False

def perform_action(gesture):
    global cap

    if gesture == "thumbs_up":
        if can_perform_action("exit"):
            print("Ending Gesture Recognition...")
            cap.release()
            cv2.destroyAllWindows()
            sys.exit()
    elif gesture == "two_fingers":
        if can_perform_action("playpause"):
            pyautogui.press("playpause")
    elif gesture == "fist":
        if can_perform_action("close_window"):
            pyautogui.hotkey("alt", "f4")
    elif gesture == "three_fingers":
        if can_perform_action("switch_tab"):
            pyautogui.hotkey("ctrl", "tab")
    elif gesture == "four_fingers":
        if can_perform_action("minimize"):
            pyautogui.hotkey("win", "down")
    elif gesture == "five_fingers":
        if can_perform_action("maximize"):
            pyautogui.hotkey("win", "up")
    elif gesture == "rock":
        if can_perform_action("mute"):
            pyautogui.press("volumemute")
    elif gesture == "notepad":
        if can_perform_action("notepad"):
            subprocess.Popen(["notepad.exe"])
    elif gesture == "ok":
        if can_perform_action("explorer"):
            subprocess.Popen("explorer")

def detect_gesture(fingers, hand_landmarks):
    total_fingers = sum(fingers)

    wrist = hand_landmarks[0]
    tip_distances = [math.hypot(hand_landmarks[tip][0] - wrist[0], hand_landmarks[tip][1] - wrist[1]) for tip in [4,8,12,16,20]]
    max_tip_dist = max(tip_distances)

    if total_fingers == 0 and max_tip_dist < 0.1:
        return "fist"
    if fingers == [0,1,1,1,0]:
        return "three_fingers"
    if fingers == [1,0,0,0,0]:
        return "thumbs_up"
    if fingers == [0,1,1,0,0]:
        return "two_fingers"
    if fingers == [0,1,1,1,1]:
        return "four_fingers"
    if total_fingers == 5:
        return "five_fingers"
    if fingers == [0,1,0,0,1]:
        return "rock"
    if fingers == [0,1,0,0,0]:
        return "notepad"

    thumb_tip = hand_landmarks[4]
    index_tip = hand_landmarks[8]
    dist = math.hypot(index_tip[0] - thumb_tip[0], index_tip[1] - thumb_tip[1])
    if dist < 0.04:
        return "ok"

    return None

def main():
    global cap
    cap = cv2.VideoCapture(0)

    with mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5, max_num_hands=1) as hands:
        init_time = time.time()
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.resize(frame, (640, 640))
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = hands.process(rgb_frame)

            if time.time() - init_time > 5:
                hands.min_detection_confidence = 0.7
                hands.min_tracking_confidence = 0.7

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    landmark_points = [(lm.x, lm.y) for lm in hand_landmarks.landmark]
                    landmark_history.append(landmark_points)
                    if len(landmark_history) < NUM_FRAMES_SMOOTH:
                        continue

                    avg_landmarks = average_landmarks(landmark_history)
                    fingers = count_fingers(avg_landmarks)
                    gesture = detect_gesture(fingers, avg_landmarks)

                    global last_gesture, last_gesture_time
                    if gesture and (gesture != last_gesture or (time.time() - last_gesture_time) > gesture_cooldown):
                        perform_action(gesture)
                        last_gesture = gesture
                        last_gesture_time = time.time()

                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            cv2.imshow("Hand Gesture Recognition", frame)
            if cv2.waitKey(10) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
