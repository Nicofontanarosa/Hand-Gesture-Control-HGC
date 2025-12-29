
import cv2
import mediapipe as mp
import time
import win32gui
import win32con
import win32api
import math
import pyautogui

# --- Window state ---
active_hwnd = None
current_mode = "idle"  # idle | alt_tab | drag | mouse | scroll

# --- Webcam setup ---
cap = cv2.VideoCapture(0)

# --- MediaPipe Hands setup ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
draw = mp.solutions.drawing_utils

# --- Landmark IDs ---
tip_ids = [4, 8, 12, 16, 20]

# --- Gesture thresholds ---
tab_delay = 0.8
scroll_delay = 0.3
click_threshold = 15
alt_tab_threshold = 10
scroll_down_threshold = 10
scroll_up_threshold = 150

last_scroll_time = 0
last_tab_time = 0
last_fingers = [0, 0, 0, 0, 0]

# --- FPS timing ---
ctime, ptime = 0, 0

# --- Multi-monitor info ---
VIRTUAL_X = win32api.GetSystemMetrics(76)
VIRTUAL_Y = win32api.GetSystemMetrics(77)
SCREEN_W = win32api.GetSystemMetrics(78)
SCREEN_H = win32api.GetSystemMetrics(79)


def fingers_up(hand_landmarks):
    
    tips = [4, 8, 12, 16, 20]
    fingers = []

    # Thumb (x axis)
    fingers.append(1 if hand_landmarks.landmark[tips[0]].x < hand_landmarks.landmark[tips[0] - 1].x else 0)

    # Other fingers (y axis)
    for id in range(1, 5):
        fingers.append(1 if hand_landmarks.landmark[tips[id]].y < hand_landmarks.landmark[tips[id] - 2].y else 0)

    return fingers


while True:
    success, img = cap.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    h, w, _ = img.shape

    imgrgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    res = hands.process(imgrgb)

    lmlist = []

    if res.multi_hand_landmarks:
        for i, handlms in enumerate(res.multi_hand_landmarks):
            # Process only right hand
            handedness = res.multi_handedness[i].classification[0].label
            if handedness != "Right":
                continue

            for id, lm in enumerate(handlms.landmark):
                cx, cy = int(lm.x * w), int(lm.y * h)
                lmlist.append([id, cx, cy])

            if len(lmlist) == 21:

                fingers = fingers_up(handlms)
                fingercount = fingers.count(1)
                thumb, index, middle, ring, pinky = fingers

                # Key landmark coordinates
                x_thumb, y_thumb = lmlist[4][1], lmlist[4][2]
                x_index, y_index = lmlist[8][1], lmlist[8][2]
                x_middle, y_middle = lmlist[12][1], lmlist[12][2]
                x_ring, y_ring = lmlist[16][1], lmlist[16][2]
                x_pinky, y_pinky = lmlist[20][1], lmlist[20][2]

                # Distances between fingers
                distances = {
                    "thumb_index": math.hypot(x_index - x_thumb, y_index - y_thumb),
                    "thumb_middle": math.hypot(x_middle - x_thumb, y_middle - y_thumb),
                    "thumb_pinky": math.hypot(x_pinky - x_thumb, y_pinky - y_thumb)
                }

                now = time.time()

                # === STATE MACHINE ===
                if current_mode == "idle":
                    # ALT + TAB gesture
                    if distances["thumb_index"] < alt_tab_threshold and middle == 1 and ring == 1 and pinky == 1:
                        current_mode = "alt_tab"
                        pyautogui.keyDown('alt')
                        pyautogui.press('tab')
                        last_tab_time = now
                        cv2.putText(img, "ALT+TAB MODE ACTIVE", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                    # Drag window gesture
                    elif index == 1 and thumb == 0 and middle == 0 and ring == 0 and pinky == 0:
                        current_mode = "drag"
                        active_hwnd = win32gui.GetForegroundWindow()
                        style = win32gui.GetWindowLong(active_hwnd, win32con.GWL_STYLE)
                        if style & win32con.WS_MAXIMIZE:
                            win32gui.ShowWindow(active_hwnd, win32con.SW_RESTORE)
                        cv2.putText(img, "WINDOW SELECTED", (100, 100), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 255), 2)

                    # Mouse control gesture
                    elif distances["thumb_middle"] < click_threshold and index == 1:
                        current_mode = "mouse"
                        cv2.putText(img, "MOUSE MODE", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                    # Scroll gesture
                    elif distances["thumb_pinky"] < scroll_down_threshold or distances["thumb_pinky"] > scroll_up_threshold:
                        current_mode = "scroll"

                elif current_mode == "alt_tab":
                    if now - last_tab_time > tab_delay and distances["thumb_index"] < alt_tab_threshold:
                        pyautogui.press('tab')
                        last_tab_time = now
                    elif distances["thumb_index"] > alt_tab_threshold * 2:
                        pyautogui.keyUp('alt')
                        current_mode = "idle"

                elif current_mode == "drag":
                    if active_hwnd:
                        px, py = lmlist[9][1], lmlist[9][2]
                        screen_x = int(VIRTUAL_X + (px / w) * SCREEN_W)
                        screen_y = int(VIRTUAL_Y + (py / h) * SCREEN_H)
                        rect = win32gui.GetWindowRect(active_hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        win32gui.MoveWindow(active_hwnd, screen_x - width // 2, screen_y - height // 2, width, height, True)
                    
                    # Fullscreen
                    if index == 1 and middle == 1 and thumb == 0 and pinky == 0 and ring == 0 and active_hwnd:
                        win32gui.ShowWindow(active_hwnd, win32con.SW_MAXIMIZE)
                        current_mode = "idle"

                    if fingercount == 0:
                        current_mode = "idle"

                elif current_mode == "mouse":
                    screen_x = int((x_index / w) * SCREEN_W)
                    screen_y = int((y_index / h) * SCREEN_H)
                    pyautogui.moveTo(screen_x, screen_y)
                    if distances["thumb_middle"] > click_threshold:
                        pyautogui.click()
                        current_mode = "idle"

                elif current_mode == "scroll":
                    if now - last_scroll_time > scroll_delay:
                        if distances["thumb_pinky"] < scroll_down_threshold:
                            pyautogui.scroll(-300)
                            cv2.putText(img, "Scrolling Down", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                            last_scroll_time = now
                        elif distances["thumb_pinky"] > scroll_up_threshold:
                            pyautogui.scroll(300)
                            cv2.putText(img, "Scrolling Up", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                            last_scroll_time = now
                    if scroll_down_threshold < distances["thumb_pinky"] < scroll_up_threshold:
                        current_mode = "idle"

                # Display finger vector
                cv2.putText(img, str(fingers), (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                # Finger count box
                cv2.rectangle(img, (20, 350), (90, 440), (0, 255, 255), cv2.FILLED)
                cv2.rectangle(img, (20, 350), (90, 440), (0, 0, 0), 4)

                # Display finger count
                cv2.putText(img, str(fingercount), (25, 430), cv2.FONT_HERSHEY_PLAIN, 6, (0, 0, 0), 3)

                # Display distances on screen
                cv2.putText(img, f"T-I: {int(distances['thumb_index'])}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(img, f"T-P: {int(distances['thumb_pinky'])}", (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                cv2.putText(img, f"T-M: {int(distances['thumb_middle'])}", (10, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 68, 255), 2)

                # Draw hand landmarks
                draw.draw_landmarks(
                    img, handlms, mp_hands.HAND_CONNECTIONS,
                    draw.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2),
                    draw.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1)
                )

                # Draw key points and lines between fingers
                cv2.circle(img, (x_thumb, y_thumb), 7, (0, 255, 0), -1)
                cv2.circle(img, (x_index, y_index), 7, (255, 255, 0), -1)
                cv2.circle(img, (x_pinky, y_pinky), 7, (255, 0, 255), -1)
                cv2.circle(img, (x_middle, y_middle), 7, (255, 255, 255), -1)

                cv2.line(img, (x_thumb, y_thumb), (x_index, y_index), (0, 255, 255), 2)
                cv2.line(img, (x_thumb, y_thumb), (x_pinky, y_pinky), (255, 0, 255), 2)
                cv2.line(img, (x_thumb, y_thumb), (x_middle, y_middle), (255, 68, 255), 2)

                # Show active mode
                cv2.putText(img, f"Mode: {current_mode.upper()}", (400, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

    # FPS counter
    ctime = time.time()
    fps = 1 / (ctime - ptime) if ctime != ptime else 0
    ptime = ctime
    cv2.putText(img, f'FPS: {int(fps)}', (550, 30), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 2)

    cv2.imshow("Hand Gesture Window Control", img)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
