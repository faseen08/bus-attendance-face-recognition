import os
from typing import Dict, List, Tuple

import cv2
import numpy as np


class FaceModel:
    """
    InsightFace face detector/embedding wrapper (CPU).

    Expected input: BGR images (OpenCV default).
    Output: list of dicts with "bbox" and L2-normalized "embedding".
    """

    def __init__(self, det_size: Tuple[int, int] = (640, 640)):
        self.det_size = det_size
        self._app = None

        import insightface

        self._app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        # InsightFace expects BGR images and handles detection + embedding.
        self._app.prepare(ctx_id=0, det_size=det_size)
        print("[FACE_MODEL] Using InsightFace backend (CPU)")

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    def detect_and_embed(self, frame_bgr: np.ndarray) -> List[Dict[str, np.ndarray]]:
        """
        Returns list of detections:
        - bbox: (left, top, right, bottom) int
        - embedding: L2-normalized embedding vector
        """
        detections: List[Dict[str, np.ndarray]] = []

        faces = self._app.get(frame_bgr)
        for face in faces:
            x1, y1, x2, y2 = face.bbox.astype(int)
            emb = getattr(face, "normed_embedding", None)
            if emb is None:
                emb = self._normalize(face.embedding.astype(np.float32))
            detections.append(
                {
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "embedding": emb.astype(np.float32),
                }
            )
        return detections

    def image_embeddings(self, image_path: str) -> List[np.ndarray]:
        """
        Returns a list of embeddings found in the image file.
        Empty list if file missing, unreadable, or no faces found.
        """
        if not os.path.exists(image_path):
            return []
        image = cv2.imread(image_path)
        if image is None:
            return []
        return [item["embedding"] for item in self.detect_and_embed(image)]
