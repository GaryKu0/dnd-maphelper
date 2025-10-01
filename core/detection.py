"""Real-time map detection module."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class RealtimeDetector:
    """Handles real-time cell detection with progressive updates."""

    def __init__(self, overlay_callback, status_callback):
        self.overlay_callback = overlay_callback  # Function to update overlay
        self.status_callback = status_callback    # Function to update status
        self.is_running = False
        self.current_results = {}

    def start_detection(self, roi_img, map_name, grid_config, roi_rect):
        """Start background detection with real-time updates."""
        self.is_running = True
        self.current_results = {}

        thread = threading.Thread(
            target=self._detect_worker,
            args=(roi_img, map_name, grid_config, roi_rect),
            daemon=True
        )
        thread.start()
        return thread

    def stop_detection(self):
        """Stop the current detection."""
        self.is_running = False

    def _detect_worker(self, roi_img, map_name, grid_config, roi_rect):
        """Worker thread for detection."""
        try:
            import matcher
            from utils.settings import get_settings
            from utils.resource_path import resource_path

            settings = get_settings()
            MAPS_ROOT = resource_path("maps")
            map_folder = f"{MAPS_ROOT}/{map_name}"

            # Split into cells
            rows, cols = grid_config
            cells = matcher.split_into_grid(roi_img, rows, cols)
            templates = matcher.load_templates(map_folder)

            total_cells = len(cells)
            min_inliers = settings.get("min_inliers", 6)

            self.status_callback(f"[Detecting] 0/{total_cells} cells...")

            # Function to process a single cell
            def process_cell(cell_idx, cell):
                if not self.is_running:
                    return None

                # Check cache first
                if cell_idx in matcher._identified_cells:
                    return (cell_idx, matcher._identified_cells[cell_idx])

                # Match this cell
                best_score = 0
                best_location = None
                best_rotation = 0

                for location_name, tpl in templates:
                    if not self.is_running:
                        return None

                    for rotation in [0, 90, 180, 270]:
                        if not self.is_running:
                            return None

                        rotated_cell = matcher.rotate_image(cell, rotation)
                        inliers, H = matcher.orb_ransac_match(
                            rotated_cell, tpl,
                            min_inliers=min_inliers
                        )

                        if inliers > best_score:
                            best_score = inliers
                            best_location = location_name
                            best_rotation = rotation

                if best_score > 0:
                    result = (best_location, best_rotation)
                    return (cell_idx, result)
                return None

            # Process cells in parallel
            max_workers = min(8, total_cells)  # Use up to 8 threads
            completed_count = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all cell processing tasks
                future_to_idx = {
                    executor.submit(process_cell, idx, cell): idx
                    for idx, cell in enumerate(cells)
                }

                # Process results as they complete
                for future in as_completed(future_to_idx):
                    if not self.is_running:
                        executor.shutdown(wait=False)
                        self.status_callback("[Cancelled] Detection stopped")
                        return

                    result = future.result()
                    if result is not None:
                        cell_idx, cell_result = result
                        self.current_results[cell_idx] = cell_result
                        matcher._identified_cells[cell_idx] = cell_result

                    completed_count += 1

                    # Update overlay immediately on every cell completion
                    found = len(self.current_results)
                    self.status_callback(f"[Detecting] {found}/{total_cells} cells")
                    self.overlay_callback(roi_rect, grid_config, self.current_results.copy())

            self.status_callback(f"[Complete] {len(self.current_results)}/{total_cells} locations found")

        except Exception as e:
            self.status_callback(f"[Error] Detection failed: {str(e)}")
        finally:
            self.is_running = False
