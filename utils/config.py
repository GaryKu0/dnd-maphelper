import json
import os

DEFAULT_GRID = (5, 5)

class Config:
    def __init__(self, path="config.json"):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"roi_by_resolution": {}, "maps": {}, "monitor_index": None}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ----- ROI by resolution -----
    def get_roi(self, res_key:str):
        return self.data.get("roi_by_resolution", {}).get(res_key)

    def set_roi(self, res_key:str, roi):
        if "roi_by_resolution" not in self.data:
            self.data["roi_by_resolution"] = {}
        self.data["roi_by_resolution"][res_key] = list(map(int, roi))

    def has_roi(self, res_key:str):
        return self.get_roi(res_key) is not None

    # ----- Map grid / translation -----
    def get_grid(self, map_name:str):
        m = self.data.get("maps", {}).get(map_name, {})
        g = m.get("grid")
        if g and isinstance(g, list) and len(g) == 2:
            return (int(g[0]), int(g[1]))
        return DEFAULT_GRID

    def set_grid(self, map_name:str, rows:int, cols:int):
        if "maps" not in self.data:
            self.data["maps"] = {}
        if map_name not in self.data["maps"]:
            self.data["maps"][map_name] = {}
        self.data["maps"][map_name]["grid"] = [int(rows), int(cols)]

    def get_translation(self, map_name:str):
        return self.data.get("maps", {}).get(map_name, {}).get("translation", {})

    def set_translation(self, map_name:str, mapping:dict):
        if "maps" not in self.data:
            self.data["maps"] = {}
        if map_name not in self.data["maps"]:
            self.data["maps"][map_name] = {}
        self.data["maps"][map_name]["translation"] = mapping

    # ----- Monitor selection -----
    def get_monitor_index(self):
        """Get the stored monitor index, or None if not set."""
        return self.data.get("monitor_index")

    def set_monitor_index(self, monitor_index:int):
        """Set the monitor index."""
        self.data["monitor_index"] = int(monitor_index)

    def has_monitor_index(self):
        """Check if monitor index is configured."""
        return "monitor_index" in self.data and self.data["monitor_index"] is not None
