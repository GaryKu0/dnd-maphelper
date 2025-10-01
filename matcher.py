import os, glob, json
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Cache for loaded templates and identified cells
_template_cache = {}
_identified_map = None
_identified_cells = {}  # {cell_idx: (location_name, rotation, confidence)}
_cache_timestamp = None  # When the map was first identified
_cache_duration = 15 * 60  # 15 minutes in seconds

# Confidence logging
_confidence_log_file = "confidence_log.txt"


def log_confidence(map_name, cell_idx, location, rotation, confidence, score_type):
    """Log confidence scores for analysis and threshold tuning.

    Args:
        map_name: Name of the map
        cell_idx: Cell index
        location: Matched location name
        rotation: Rotation angle
        confidence: Normalized confidence (0-100)
        score_type: 'orb' or 'color'
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_confidence_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} | {map_name} | cell_{cell_idx} | {location} | {rotation}° | {confidence}% | {score_type}\n")
    except:
        pass  # Don't crash if logging fails


def _normalize_confidence(score, score_type='orb'):
    """
    Normalize different score types to a unified 0-100 confidence scale.

    Args:
        score: Raw score value
        score_type: 'orb' for inlier counts, 'color' for histogram correlation

    Returns:
        Normalized confidence (0-100)
    """
    if score_type == 'orb':
        # ORB inliers: typically 5-50 for good matches
        # Map 5->50, 30->85, 50+->95
        if score < 5:
            return 0
        elif score >= 50:
            return 95
        else:
            # Linear mapping: 5 inliers = 50%, 30 inliers = 85%
            return 50 + int((score - 5) * 35 / 25)
    elif score_type == 'color':
        # Color histogram: already 0-100
        # But scale it down slightly since it's less reliable
        return int(score * 0.8)  # Max 80% confidence for color-only matches
    else:
        return int(score)


def reset_session():
    """Reset session cache (call when starting new game/map)."""
    global _identified_map, _identified_cells, _cache_timestamp
    _identified_map = None
    _identified_cells = {}
    _cache_timestamp = None


def is_cache_expired():
    """Check if cache has expired (15 minutes)."""
    global _cache_timestamp
    if _cache_timestamp is None:
        return False

    import time
    elapsed = time.time() - _cache_timestamp
    return elapsed > _cache_duration


def load_templates(map_folder):
    """Load and cache templates for a map folder."""
    if map_folder in _template_cache:
        return _template_cache[map_folder]

    tile_paths = glob.glob(os.path.join(map_folder, "*.png")) + \
                 glob.glob(os.path.join(map_folder, "*.jpg"))

    templates = []
    for tp in tile_paths:
        tpl = cv2.imread(tp)
        if tpl is not None:
            location_name = os.path.splitext(os.path.basename(tp))[0]
            templates.append((location_name, tpl))

    _template_cache[map_folder] = templates
    return templates

def load_grid_config(map_folder):
    """Load grid.json from map folder. Returns (rows, cols) or None."""
    grid_path = os.path.join(map_folder, "grid.json")
    if os.path.exists(grid_path):
        try:
            with open(grid_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return (data.get("rows", 5), data.get("cols", 5))
        except:
            pass
    return None


def load_location_names(map_folder, language='en'):
    """Load location display names from names.json.
    Returns dict mapping filename (without extension) to display name.
    If names.json doesn't exist, returns empty dict (use original filenames)."""
    names_path = os.path.join(map_folder, "names.json")
    if os.path.exists(names_path):
        try:
            with open(names_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Support both simple dict and multi-language dict
                if language in data:
                    return data[language]
                elif 'en' in data:
                    return data['en']
                else:
                    # Assume it's a simple dict without language keys
                    return data
        except:
            pass
    return {}


def rotate_image(img, angle):
    """Rotate image by angle (0, 90, 180, 270 degrees)."""
    if angle == 0:
        return img
    elif angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def split_into_grid(img, rows, cols):
    """Split image into rows x cols grid. Returns list of cell images."""
    h, w = img.shape[:2]
    cell_h = h // rows
    cell_w = w // cols

    cells = []
    for r in range(rows):
        for c in range(cols):
            y1 = r * cell_h
            x1 = c * cell_w
            y2 = y1 + cell_h if r < rows - 1 else h
            x2 = x1 + cell_w if c < cols - 1 else w
            cells.append(img[y1:y2, x1:x2])
    return cells


def preprocess_structural_features(img):
    """
    Preprocess image to enhance structural features and reduce grid noise.
    Returns preprocessed grayscale image.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # 1. Gaussian blur to reduce fine grid noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 2. CLAHE for contrast enhancement (enhances walls/lines)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)

    return enhanced


def detect_structural_keypoints(img):
    """
    Detect structural keypoints: corners, intersections, T-junctions.
    Filters out long straight lines.
    """
    # Preprocess
    enhanced = preprocess_structural_features(img)

    # Detect edges using Canny
    edges = cv2.Canny(enhanced, 50, 150)

    # Detect corners (Harris corner detector)
    corners = cv2.cornerHarris(enhanced, blockSize=2, ksize=3, k=0.04)
    corners = cv2.dilate(corners, None)

    # Threshold for corner detection
    corner_threshold = 0.01 * corners.max()
    corner_mask = corners > corner_threshold

    # Combine edges with corner emphasis
    # This emphasizes intersections and corners while reducing straight lines
    structural_features = np.zeros_like(enhanced)
    structural_features[corner_mask] = 255
    structural_features = cv2.bitwise_or(structural_features, edges)

    return structural_features


def structural_feature_match(img_roi, img_template, min_matches=6):
    """
    Match using structural features (corners, intersections, T-junctions).
    This is more robust against grid lines.
    Returns (match_score, H).
    """
    # Extract structural features from both images
    roi_features = detect_structural_keypoints(img_roi)
    tpl_features = detect_structural_keypoints(img_template)

    # Use ORB on the structural feature images
    orb = cv2.ORB_create(6000)  # More features for better matching

    kp1, des1 = orb.detectAndCompute(roi_features, None)
    kp2, des2 = orb.detectAndCompute(tpl_features, None)

    # More lenient descriptor check
    if des1 is None or des2 is None or len(des1) < 5 or len(des2) < 5:
        return 0, None

    # Match features
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    if len(des1) < 2 or len(des2) < 2:
        return 0, None

    matches = bf.knnMatch(des1, des2, k=2)

    # More lenient ratio test for structural features
    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.80 * n.distance:  # More lenient
                good.append(m)

    if len(good) < min_matches:
        return 0, None

    # Calculate homography
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None or mask is None:
        return 0, None

    inliers = int(mask.sum())

    # More lenient threshold
    if inliers < min_matches:
        return 0, None

    return inliers, H


def color_histogram_match(img_roi, img_template):
    """
    Compare images using color histogram correlation.
    Returns a score between 0-100 (higher is better).
    """
    # Resize both to same size for fair comparison
    target_size = (200, 200)
    roi_resized = cv2.resize(img_roi, target_size)
    tpl_resized = cv2.resize(img_template, target_size)

    # Calculate histograms for each channel
    hist_roi = []
    hist_tpl = []

    for i in range(3):  # BGR channels
        hist_roi.append(cv2.calcHist([roi_resized], [i], None, [32], [0, 256]))
        hist_tpl.append(cv2.calcHist([tpl_resized], [i], None, [32], [0, 256]))

        # Normalize
        cv2.normalize(hist_roi[i], hist_roi[i], alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist_tpl[i], hist_tpl[i], alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    # Compare histograms using correlation
    scores = []
    for i in range(3):
        score = cv2.compareHist(hist_roi[i], hist_tpl[i], cv2.HISTCMP_CORREL)
        scores.append(score)

    # Average score across channels, convert to 0-100 scale
    avg_score = np.mean(scores)
    return int(avg_score * 100)


def orb_ransac_match(img_roi, img_template, min_inliers=12, use_color_fallback=False):
    """
    Enhanced ORB matching with preprocessing for better grid map detection.
    Returns (inliers, H).
    """
    # Preprocess both images to enhance features
    def preprocess_for_orb(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # Apply slight Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # CLAHE for better contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        # Sharpen to enhance edges
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)

        return sharpened

    roi_processed = preprocess_for_orb(img_roi)
    tpl_processed = preprocess_for_orb(img_template)

    # Use more ORB features for better accuracy
    orb = cv2.ORB_create(
        nfeatures=6000,           # More features for better matching
        scaleFactor=1.2,          # Better scale invariance
        nlevels=8,                # More pyramid levels
        edgeThreshold=15,         # Detect features closer to edges
        firstLevel=0,
        WTA_K=2,
        scoreType=cv2.ORB_HARRIS_SCORE,  # Better corner detection
        patchSize=31,
        fastThreshold=20
    )

    kp1, des1 = orb.detectAndCompute(roi_processed, None)
    kp2, des2 = orb.detectAndCompute(tpl_processed, None)

    if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
        if use_color_fallback:
            color_score = color_histogram_match(img_roi, img_template)
            return color_score, None
        return 0, None

    # Use FLANN matcher for better performance
    FLANN_INDEX_LSH = 6
    index_params = dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12, multi_probe_level=1)
    search_params = dict(checks=50)

    flann = cv2.FlannBasedMatcher(index_params, search_params)

    if len(des1) < 2 or len(des2) < 2:
        if use_color_fallback:
            color_score = color_histogram_match(img_roi, img_template)
            return color_score, None
        return 0, None

    try:
        matches = flann.knnMatch(des1, des2, k=2)
    except:
        # Fallback to BFMatcher if FLANN fails
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = bf.knnMatch(des1, des2, k=2)

    # Lowe's ratio test with balanced threshold
    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good.append(m)

    if len(good) < min_inliers:
        if use_color_fallback:
            color_score = color_histogram_match(img_roi, img_template)
            return color_score, None
        return 0, None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if H is None or mask is None:
        if use_color_fallback:
            color_score = color_histogram_match(img_roi, img_template)
            return color_score, None
        return 0, None

    inliers = int(mask.sum())

    if inliers < min_inliers:
        if use_color_fallback:
            color_score = color_histogram_match(img_roi, img_template)
            return color_score, None
        return 0, None

    return inliers, H


def _match_single_cell(cell_idx, cell, templates, cached_result=None, early_stop=None, min_cache_confidence=None):
    """Helper function to match a single cell (for threading).
    Early stops if match quality exceeds threshold.

    Args:
        cached_result: Tuple of (location, rotation, confidence) if cached
        early_stop: Confidence threshold for early stopping (0-100 scale)
        min_cache_confidence: Minimum confidence to accept cached result
    """
    # Load settings if not provided
    from utils.settings import get_settings
    settings = get_settings()

    if early_stop is None:
        early_stop = settings.get('early_stop_threshold', 75)  # Default 75% confidence

    if min_cache_confidence is None:
        min_cache_confidence = settings.get('min_cache_confidence', 60)  # Default 60% confidence

    # Check cached result confidence
    if cached_result is not None:
        location, rotation, cached_confidence = cached_result
        # Only use cache if confidence is high enough
        if cached_confidence >= min_cache_confidence:
            return (cell_idx, (location, rotation), cached_confidence)
        # Otherwise re-match

    # Identify new cell - STAGE 1: Try enhanced ORB
    cell_best_orb_inliers = 0
    cell_best_location = None
    cell_best_rotation = 0
    cell_best_confidence = 0
    used_color = False

    for location_name, tpl in templates:
        # Try all 4 rotations for this cell
        for rotation in [0, 90, 180, 270]:
            rotated_cell = rotate_image(cell, rotation)
            orb_inliers, H = orb_ransac_match(rotated_cell, tpl, min_inliers=5, use_color_fallback=False)

            if orb_inliers > 0:
                # Normalize ORB score to 0-100 confidence
                confidence = _normalize_confidence(orb_inliers, 'orb')

                if confidence > cell_best_confidence:
                    cell_best_orb_inliers = orb_inliers
                    cell_best_confidence = confidence
                    cell_best_location = location_name
                    cell_best_rotation = rotation

                    # Early stop if we found a very good match
                    if cell_best_confidence >= early_stop:
                        return (cell_idx, (cell_best_location, cell_best_rotation), cell_best_confidence)

    # STAGE 2: If ORB failed, try color matching
    if cell_best_orb_inliers < 5:
        used_color = True
        for location_name, tpl in templates:
            for rotation in [0, 90, 180, 270]:
                rotated_cell = rotate_image(cell, rotation)
                color_score = color_histogram_match(rotated_cell, tpl)

                # Normalize color score to 0-100 confidence
                confidence = _normalize_confidence(color_score, 'color')

                if confidence > cell_best_confidence:
                    cell_best_confidence = confidence
                    cell_best_location = location_name
                    cell_best_rotation = rotation

    # Accept if we have at least 40% confidence (50% for ORB, 32% for color after scaling)
    if cell_best_confidence >= 40:
        # Log the confidence score for analysis
        score_type = 'color' if used_color else 'orb'
        if _identified_map:
            log_confidence(_identified_map, cell_idx, cell_best_location, cell_best_rotation, cell_best_confidence, score_type)
        return (cell_idx, (cell_best_location, cell_best_rotation), cell_best_confidence)
    return (cell_idx, None, 0)


def match_cells_to_known_map(roi_bgr, map_folder, grid_config, use_cache=True):
    """
    Fast path: match cells when we already know which map it is (multithreaded).
    Uses session cache to skip already identified cells.
    Returns (avg_confidence, cell_locations, cell_confidences).

    Args:
        use_cache: If True, use and update global cache. If False, ignore cache (for auto-detect).

    Returns:
        Tuple of (average_confidence, cell_locations, cell_confidences)
        - average_confidence: 0-100 scale
        - cell_locations: {cell_idx: (location, rotation)}
        - cell_confidences: {cell_idx: confidence}
    """
    global _identified_cells

    # Load settings for threading
    from utils.settings import get_settings
    settings = get_settings()
    threading_enabled = settings.get('threading_enabled', True)
    thread_count = settings.get('thread_count', 8)

    rows, cols = grid_config
    cells = split_into_grid(roi_bgr, rows, cols)

    # Use cached templates
    templates = load_templates(map_folder)

    total_confidence = 0
    matched_cells = 0
    cell_locations = {}
    cell_confidences = {}  # {cell_idx: confidence_score}

    # Use threading if enabled
    if threading_enabled:
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = []
            for cell_idx, cell in enumerate(cells):
                # Only use cache if enabled (don't use during auto-detect!)
                cached = _identified_cells.get(cell_idx) if use_cache else None
                future = executor.submit(_match_single_cell, cell_idx, cell, templates, cached)
                futures.append(future)

            for future in as_completed(futures):
                cell_idx, result, confidence = future.result()
                if result is not None:
                    location, rotation = result
                    total_confidence += confidence
                    matched_cells += 1
                    cell_locations[cell_idx] = (location, rotation)
                    cell_confidences[cell_idx] = confidence
                    # Only cache if enabled (don't cache during auto-detect!)
                    if use_cache:
                        _identified_cells[cell_idx] = (location, rotation, confidence)
    else:
        # Single-threaded execution
        for cell_idx, cell in enumerate(cells):
            cached = _identified_cells.get(cell_idx) if use_cache else None
            cell_idx, result, confidence = _match_single_cell(cell_idx, cell, templates, cached)
            if result is not None:
                location, rotation = result
                total_confidence += confidence
                matched_cells += 1
                cell_locations[cell_idx] = (location, rotation)
                cell_confidences[cell_idx] = confidence
                if use_cache:
                    _identified_cells[cell_idx] = (location, rotation, confidence)

    # Return average confidence (0-100 scale)
    avg_confidence = int(total_confidence / matched_cells) if matched_cells > 0 else 0
    return (avg_confidence, cell_locations, cell_confidences)


def _check_first_cell_for_map(map_name, map_folder, roi_bgr, early_stop=None):
    """Helper function to check first cell against one map (for threading).
    Early stops if match quality exceeds threshold.

    Returns: (map_name, confidence, grid_config, best_match_name) or None
    """
    # Load early_stop from settings if not provided
    if early_stop is None:
        from utils.settings import get_settings
        settings = get_settings()
        early_stop = settings.get('early_stop_threshold', 75)  # Default 75% confidence

    # Load grid config
    grid_config = load_grid_config(map_folder)
    if grid_config is None:
        grid_config = (5, 5)

    # Split into grid and take ONLY first cell
    rows, cols = grid_config
    cells = split_into_grid(roi_bgr, rows, cols)
    if not cells:
        return None
    first_cell = cells[0]

    # Load templates for this map
    templates = load_templates(map_folder)

    # STAGE 1: Try enhanced ORB on first cell
    best_orb_inliers = 0
    best_confidence = 0
    best_match_name = None

    for location_name, tpl in templates:
        for rotation in [0, 90, 180, 270]:
            rotated_cell = rotate_image(first_cell, rotation)
            orb_inliers, H = orb_ransac_match(rotated_cell, tpl, min_inliers=5, use_color_fallback=False)

            if orb_inliers > 0:
                # Normalize ORB score to 0-100 confidence
                confidence = _normalize_confidence(orb_inliers, 'orb')

                if confidence > best_confidence:
                    best_orb_inliers = orb_inliers
                    best_confidence = confidence
                    best_match_name = location_name

                    # Early stop if we found a very good match
                    if best_confidence >= early_stop:
                        return (map_name, best_confidence, grid_config, best_match_name)

    # STAGE 2: If ORB failed, try color matching
    if best_orb_inliers < 5:
        for location_name, tpl in templates:
            for rotation in [0, 90, 180, 270]:
                rotated_cell = rotate_image(first_cell, rotation)
                color_score = color_histogram_match(rotated_cell, tpl)

                # Normalize color score to 0-100 confidence
                confidence = _normalize_confidence(color_score, 'color')

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_name = location_name

    # Accept if we have at least 40% confidence
    if best_confidence >= 40:
        # Log the confidence score for analysis
        score_type = 'color' if best_orb_inliers < 5 else 'orb'
        log_confidence(map_name, 0, best_match_name, 0, best_confidence, score_type)
        return (map_name, best_confidence, grid_config, best_match_name)
    return None


def identify_map_from_first_cell(roi_bgr, maps_root):
    """
    Identify which map by checking ONLY the first cell (multithreaded).
    Returns list of candidates: [(map_name, confidence_score, grid_config), ...]
    sorted by confidence (highest first).
    """
    if not os.path.isdir(maps_root):
        return []

    # Load settings for threading
    from utils.settings import get_settings
    settings = get_settings()
    threading_enabled = settings.get('threading_enabled', True)
    thread_count = settings.get('thread_count', 8)

    # Collect all map folders
    map_folders = []
    for map_name in sorted(os.listdir(maps_root)):
        map_folder = os.path.join(maps_root, map_name)
        if os.path.isdir(map_folder):
            map_folders.append((map_name, map_folder))

    candidates = []

    # Use threading if enabled
    if threading_enabled:
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {
                executor.submit(_check_first_cell_for_map, map_name, map_folder, roi_bgr): map_name
                for map_name, map_folder in map_folders
            }

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    candidates.append(result)
    else:
        # Single-threaded execution
        for map_name, map_folder in map_folders:
            result = _check_first_cell_for_map(map_name, map_folder, roi_bgr)
            if result is not None:
                candidates.append(result)

    # Sort by confidence (highest first)
    candidates.sort(key=lambda x: x[1], reverse=True)

    return candidates


def identify_map(roi_bgr, maps_root, max_tiles_per_map=None):
    """
    Identify which map ROI belongs to, using grid-based ORB+RANSAC with session caching.
    Each cell can be rotated independently.
    Cache expires after 15 minutes.
    Returns (best_map_name, avg_confidence, grid_config, cell_locations).
    cell_locations is a dict: {cell_idx: (location_name, rotation)}
    avg_confidence is normalized to 0-100 scale.
    """
    global _identified_map, _cache_timestamp

    if not os.path.isdir(maps_root):
        return (None, 0, None, {})

    # Check if cache has expired (15 minutes)
    if is_cache_expired():
        reset_session()

    # Fast path: if we already know the map, only check that map
    if _identified_map is not None:
        map_folder = os.path.join(maps_root, _identified_map)
        if os.path.isdir(map_folder):
            grid_config = load_grid_config(map_folder)
            if grid_config is None:
                grid_config = (5, 5)

            avg_confidence, cell_locations, cell_confidences = match_cells_to_known_map(roi_bgr, map_folder, grid_config)

            # Accept if average confidence >= 40%
            if avg_confidence >= 40:
                return (_identified_map, avg_confidence, grid_config, cell_locations)

    # Full search: try all maps
    best = (None, 0, None, {})  # (name, avg_confidence, grid_config, cell_locations)

    for map_name in sorted(os.listdir(maps_root)):
        map_folder = os.path.join(maps_root, map_name)
        if not os.path.isdir(map_folder):
            continue

        # Load grid config
        grid_config = load_grid_config(map_folder)
        if grid_config is None:
            grid_config = (5, 5)  # default 5x5

        # Use fast path with cached templates (DON'T cache during auto-detect!)
        avg_confidence, cell_locations, cell_confidences = match_cells_to_known_map(roi_bgr, map_folder, grid_config, use_cache=False)

        if avg_confidence > best[1]:
            best = (map_name, avg_confidence, grid_config, cell_locations)

    # Acceptance threshold: average confidence >= 40%
    if best[1] >= 40:
        # Cache the identified map with timestamp
        import time
        _identified_map = best[0]
        if _cache_timestamp is None:
            _cache_timestamp = time.time()
        return best
    return (None, best[1], best[2], best[3])
