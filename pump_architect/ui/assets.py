import base64
import os

# Assets (icons) live in the project root alongside the package directory
# pump_architect/ui/assets.py  →  pump_architect/ui  →  pump_architect  →  project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_base64_image(image_path):
    """Return a base64-encoded string for the given image file.

    The path is resolved relative to the project root directory so that it
    works regardless of the working directory Streamlit is launched from.
    """
    try:
        abs_file_path = os.path.join(_PROJECT_ROOT, image_path)
        with open(abs_file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""
