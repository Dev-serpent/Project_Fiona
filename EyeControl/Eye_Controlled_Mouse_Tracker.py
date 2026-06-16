from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any

DEFAULT_CAMERA_URL = "http://192.168.0.103:8080/shot.jpg"


@dataclass(frozen=True)
class EyeTrackerConfig:
    """Runtime configuration for the optional eye-controlled mouse tracker."""

    url: str | None = DEFAULT_CAMERA_URL
    camera_index: int | None = None
    window_width: int = 800
    window_height: int = 600
    click_threshold: float = 0.015
    click_sleep_seconds: float = 0.5
    enable_clicks: bool = True
    window_name: str = "Fiona Eye Control"
    request_timeout_seconds: float = 5.0


def dependency_status() -> dict[str, Any]:
    """Return dependency availability without importing camera/GUI libraries."""

    dependencies = {
        "requests": find_spec("requests") is not None,
        "cv2": find_spec("cv2") is not None,
        "numpy": find_spec("numpy") is not None,
        "mediapipe": find_spec("mediapipe") is not None,
        "pyautogui": find_spec("pyautogui") is not None,
    }
    return {
        "ready": all(dependencies.values()),
        "requires_camera": True,
        "dependencies": dependencies,
        "default_url": DEFAULT_CAMERA_URL,
    }


def _require_runtime_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    missing = [name for name, available in dependency_status()["dependencies"].items() if not available]
    if missing:
        raise RuntimeError(
            "EyeControl requires optional runtime dependencies: "
            + ", ".join(missing)
            + ". Install them before running the camera tracker."
        )

    import cv2
    import mediapipe
    import numpy as np
    import pyautogui
    import requests

    return requests, cv2, np, mediapipe, pyautogui


def _frame_from_url(requests: Any, cv2: Any, np: Any, url: str, timeout_seconds: float) -> Any:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    image_array = np.array(bytearray(response.content), dtype=np.uint8)
    return cv2.imdecode(image_array, -1)


def run_eye_tracker(config: EyeTrackerConfig | None = None) -> None:
    """Run the eye-controlled mouse tracker loop.

    OpenCV, MediaPipe, and PyAutoGUI are imported only here so normal Fiona
    imports and tests keep working on machines without camera support.
    """

    config = config or EyeTrackerConfig()
    requests, cv2, np, mediapipe, pyautogui = _require_runtime_dependencies()

    face_mesh = mediapipe.solutions.face_mesh.FaceMesh(refine_landmarks=True)
    screen_w, screen_h = pyautogui.size()
    capture = cv2.VideoCapture(config.camera_index) if config.camera_index is not None else None

    try:
        while True:
            if capture is not None:
                ok, image = capture.read()
                if not ok:
                    raise RuntimeError(f"Could not read frame from camera index {config.camera_index}")
            else:
                if not config.url:
                    raise RuntimeError("EyeControl requires either a camera URL or a camera index.")
                image = _frame_from_url(requests, cv2, np, config.url, config.request_timeout_seconds)

            if image is None:
                raise RuntimeError("EyeControl received an empty camera frame.")

            image = cv2.flip(image, 1)
            window_h, window_w, _ = image.shape
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            processed_image = face_mesh.process(rgb_image)
            face_landmarks = processed_image.multi_face_landmarks

            if face_landmarks:
                points = face_landmarks[0].landmark
                for point_index, landmark_point in enumerate(points[474:478]):
                    x = int(landmark_point.x * window_w)
                    y = int(landmark_point.y * window_h)
                    if point_index == 1:
                        mouse_x = int(screen_w / window_w * x)
                        mouse_y = int(screen_h / window_h * y)
                        pyautogui.moveTo(mouse_x, mouse_y)
                    cv2.circle(image, (x, y), 3, (0, 0, 255))

                left_eye = [points[145], points[159]]
                for landmark_point in left_eye:
                    x = int(landmark_point.x * window_w)
                    y = int(landmark_point.y * window_h)
                    cv2.circle(image, (x, y), 6, (0, 255, 0))

                if config.enable_clicks and (left_eye[0].y - left_eye[1].y) < config.click_threshold:
                    pyautogui.click()
                    pyautogui.sleep(config.click_sleep_seconds)
                    print("Mouse Clicked")

            resized_image = cv2.resize(image, (config.window_width, config.window_height))
            cv2.imshow(config.window_name, resized_image)
            if cv2.waitKey(1) == 27:
                break
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_eye_tracker(EyeTrackerConfig())
