import cv2

def select_roi_interactive(frame_bgr, title="Select Map Box"):
    # returns [x,y,w,h] or None
    roi = cv2.selectROI(title, frame_bgr, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()
    if roi == (0,0,0,0):
        return None
    x,y,w,h = roi
    return [int(x), int(y), int(w), int(h)]
