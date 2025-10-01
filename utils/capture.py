import mss
import numpy as np
import cv2

def capture_screen():
    with mss.mss() as sct:
        mon = sct.monitors[1]
        img = np.array(sct.grab(mon))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def screen_resolution_key():
    with mss.mss() as sct:
        mon = sct.monitors[1]
        w, h = mon["width"], mon["height"]
        return f"{w}x{h}", (w, h)
