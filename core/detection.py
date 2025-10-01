"""Real-time map detection module."""
import threading
import time


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

            settings = get_settings()
            map_folder = f"./maps/{map_name}"

            # Split into cells
            rows, cols = grid_config
            cells = matcher.split_into_grid(roi_img, rows, cols)
            templates = matcher.load_templates(map_folder)

            update_interval = settings.get("update_interval_cells", 3)
            total_cells = len(cells)

            self.status_callback(f"[Detecting] 0/{total_cells} cells...")

            # Process each cell
            for cell_idx, cell in enumerate(cells):
                if not self.is_running:
                    self.status_callback("[Cancelled] Detection stopped")
                    return

                # Check cache first
                if cell_idx in matcher._identified_cells:
                    self.current_results[cell_idx] = matcher._identified_cells[cell_idx]
                else:
                    # Match this cell
                    best_score = 0
                    best_location = None
                    best_rotation = 0

                    for location_name, tpl in templates:
                        for rotation in [0, 90, 180, 270]:
                            if not self.is_running:
                                return

                            rotated_cell = matcher.rotate_image(cell, rotation)
                            inliers, H = matcher.orb_ransac_match(
                                rotated_cell, tpl,
                                min_inliers=settings.get("min_inliers", 6)
                            )

                            if inliers > best_score:
                                best_score = inliers
                                best_location = location_name
                                best_rotation = rotation

                    if best_score > 0:
                        result = (best_location, best_rotation)
                        self.current_results[cell_idx] = result
                        matcher._identified_cells[cell_idx] = result

                # Update overlay periodically
                if (cell_idx + 1) % update_interval == 0 or cell_idx == total_cells - 1:
                    completed = len(self.current_results)
                    self.status_callback(f"[Detecting] {completed}/{total_cells} cells")
                    self.overlay_callback(roi_rect, grid_config, self.current_results.copy())

            self.status_callback(f"[Complete] {len(self.current_results)}/{total_cells} locations found")

        except Exception as e:
            self.status_callback(f"[Error] Detection failed: {str(e)}")
        finally:
            self.is_running = False
