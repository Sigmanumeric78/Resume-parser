import glob
import os
import time

import requests

API_ENDPOINT = "http://localhost:8000/upload-resume"
TARGET_DIR = "/home/flynntag/Documents/resumeresq/data/raw_resumes_clean"
FILE_EXTENSION = "*.pdf"


def main() -> None:
    pattern = os.path.join(TARGET_DIR, FILE_EXTENSION)
    file_paths = sorted(glob.glob(pattern))
    total = len(file_paths)

    if total == 0:
        print("[FAILED] No PDF files found.")
        return

    for idx, file_path in enumerate(file_paths, start=1):
        filename = os.path.basename(file_path)
        print(f"({idx} / {total}) -> {filename}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "application/pdf")}
                response = requests.post(API_ENDPOINT, files=files, timeout=120)

            try:
                payload = response.json()
            except Exception:
                payload = response.text

            if response.status_code >= 200 and response.status_code < 300:
                print(f"[SUCCESS] {response.status_code} -> {payload}")
            else:
                print(f"[FAILED] {response.status_code} -> {payload}")

        except Exception as exc:
            print(f"[FAILED] Exception for {filename}: {exc}")

        time.sleep(2.5)


if __name__ == "__main__":
    main()
