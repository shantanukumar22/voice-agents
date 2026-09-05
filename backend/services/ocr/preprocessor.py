import cv2
import numpy as np

class ImagePreprocessor:
    @staticmethod
    def check_quality(image_path: str):
        """
        Analyzes image for blurriness and orientation.
        Returns (is_ok, message)
        """
        image = cv2.imread(image_path)
        if image is None:
            return False, "Could not read image file."

        # 1. Blurriness Check (Laplacian Variance)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Typical threshold for 'blurry' is < 100
        if variance < 100:
            return False, "Image is too blurry. Please hold the camera steady and try again."

        # 2. Basic Contrast Check
        # Calculate histogram to see if image is too dark or washed out
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        mean_brightness = np.mean(gray)
        if mean_brightness < 40:
            return False, "Image is too dark. Please scan in a brighter light."
        if mean_brightness > 220:
            return False, "Image is overexposed. Please avoid direct flash on the paper."

        return True, "Image quality is good."

    @staticmethod
    def normalize_image(image_path: str, output_path: str):
        """
        Performs basic grayscale and noise reduction for better OCR.
        """
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Denoising
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Adaptive Thresholding to handle shadows/uneven lighting
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        cv2.imwrite(output_path, thresh)
        return output_path
