"""Utility to optimize template images for faster matching.

Run this once to resize all map template images to a consistent size.
This improves matching speed without significantly affecting accuracy.

Usage:
    python optimize_templates.py
"""
import os
import cv2
import glob


def shrink_images_in_folder(root, size=(256, 256), exts=(".png", ".jpg", ".jpeg")):
    """Recursively resize all images in root to fixed size."""
    count = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(exts):
                path = os.path.join(dirpath, fn)
                try:
                    img = cv2.imread(path)
                    if img is None:
                        continue

                    # Skip if already at target size
                    if img.shape[:2] == size:
                        continue

                    resized = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
                    cv2.imwrite(path, resized)
                    print(f"✓ Resized {path}")
                    count += 1
                except Exception as e:
                    print(f"✗ Error processing {path}: {e}")

    return count


if __name__ == "__main__":
    maps_root = "./maps"

    if not os.path.isdir(maps_root):
        print(f"Error: '{maps_root}' directory not found")
        exit(1)

    print("=== Template Image Optimizer ===")
    print(f"Processing all images in '{maps_root}'...")
    print("Target size: 256x256")
    print()

    count = shrink_images_in_folder(maps_root)

    print()
    print(f"Done! Optimized {count} images.")
    if count == 0:
        print("All images are already optimized.")
