import os
from io import BytesIO

import requests
from PIL import Image, ImageStat
from pyairtable import Api
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

# Setup Airtable connection
AIRTABLE_API_KEY = require_env("AIRTABLE_API_KEY")
BASE_ID = require_env("AIRTABLE_BASE_ID")
TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Published Feed Cache")
VIEW_NAME = os.getenv("AIRTABLE_VIEW_NAME", "Thumbnail Analysis Queue")

api = Api(AIRTABLE_API_KEY)
table = api.table(BASE_ID, TABLE_NAME)

# --- Image Processing Helper Functions ---

def avg_brightness(img: Image.Image) -> float:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    return stat.mean[0]

def std_brightness(img: Image.Image) -> float:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    return stat.stddev[0]

def dark_pixel_ratio(img: Image.Image, threshold: int = 40) -> float:
    gray = img.convert("L")
    arr = np.array(gray)
    return float((arr < threshold).mean())


# --- Main Analysis Function ---

def analyze_thumbnail(
    url: str,
    title: str = "",
    description: str = "",
    duration_seconds: int | float | None = None
) -> dict:
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content)).convert("RGB")
    width, height = img.size

    text = f"{title or ''} {description or ''}".lower()

    # Detect explicit text signals
    has_shorts_text_signal = (
        "#shorts" in text
        or "#short" in text
        or "youtube shorts" in text
    )

    # Crop images into sections for analysis
    left = img.crop((0, 0, int(width * 0.22), height))
    right = img.crop((int(width * 0.78), 0, width, height))
    center = img.crop((int(width * 0.35), 0, int(width * 0.65), height))

    # Calculate statistics
    left_brightness = avg_brightness(left)
    right_brightness = avg_brightness(right)
    center_brightness = avg_brightness(center)

    left_std = std_brightness(left)
    right_std = std_brightness(right)
    center_std = std_brightness(center)

    left_dark_ratio = dark_pixel_ratio(left)
    right_dark_ratio = dark_pixel_ratio(right)

    side_brightness = (left_brightness + right_brightness) / 2
    side_std = (left_std + right_std) / 2
    side_dark_ratio = (left_dark_ratio + right_dark_ratio) / 2

    black_side_ratio = max(0, center_brightness - side_brightness)

    vertical_score = 0

    # Build vertical probability score
    if side_brightness < 55:
        vertical_score += 25

    if side_dark_ratio > 0.35:
        vertical_score += 30
    elif side_dark_ratio > 0.25:
        vertical_score += 15

    if black_side_ratio > 18:
        vertical_score += 25
    elif black_side_ratio > 10:
        vertical_score += 12

    if side_std < center_std:
        vertical_score += 10

    if center_brightness > side_brightness:
        vertical_score += 10

    # --- Classification Logic ---

    if has_shorts_text_signal:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: detected from strong title/description Shorts signal "
            "(#shorts/#short/youtube shorts)."
        )

    elif (
        side_brightness < 15
        and center_brightness < 45
        and center_std < 40
        and duration_seconds is not None
        and duration_seconds <= 60
    ):
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: very dark thumbnail, but duration <= 60s strongly suggests Shorts. "
            f"duration_seconds={duration_seconds}, "
            f"side_brightness={side_brightness:.1f}, "
            f"center_brightness={center_brightness:.1f}."
        )

    elif black_side_ratio < 25 and center_brightness < 95:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: low center-side contrast, even if side areas are dark/noisy. "
            f"black_side_ratio={black_side_ratio:.2f}, "
            f"center_brightness={center_brightness:.1f}, "
            f"side_brightness={side_brightness:.1f}."
        )

    elif vertical_score >= 85 and side_dark_ratio >= 0.60 and side_brightness < 45:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: very strong dark-side signal. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_dark_ratio={side_dark_ratio:.2f}, side_brightness={side_brightness:.1f}."
        )

    elif black_side_ratio >= 100 and side_brightness < 70 and center_brightness >= 150:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: strong Disney vertical thumbnail pattern. "
            f"black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}, "
            f"center_brightness={center_brightness:.1f}."
        )

    elif vertical_score >= 70 and black_side_ratio >= 55 and side_brightness < 70:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: strong centered-brightness signal with dark side framing. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}."
        )

    elif black_side_ratio < 10 and abs(center_brightness - side_brightness) < 10:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: no meaningful center-side brightness contrast. "
            f"black_side_ratio={black_side_ratio:.2f}, "
            f"center_brightness={center_brightness:.1f}, "
            f"side_brightness={side_brightness:.1f}."
        )

    elif black_side_ratio < 55 and side_brightness >= 80:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: side areas are too bright for Disney vertical side framing. "
            f"black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}."
        )

    elif vertical_score <= 35 and black_side_ratio < 40:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: low centered-brightness contrast. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}."
        )

    elif vertical_score >= 90 and black_side_ratio >= 50 and side_brightness < 55 and side_dark_ratio >= 0.45 and center_std >= 50:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: very strong score with dark side framing and detailed center. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}, side_dark_ratio={side_dark_ratio:.2f}, "
            f"center_std={center_std:.1f}."
        )

    elif vertical_score >= 90 and black_side_ratio >= 50 and side_brightness < 55 and center_std >= 50:
        video_format = "Vertical / Shorts"
        status = "Analyzed"
        reason = (
            "Vertical: very strong score with dark side framing and detailed center. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}, center_std={center_std:.1f}."
        )

    elif black_side_ratio < 75 and side_brightness >= 75 and center_brightness >= 130:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: bright sides and high center brightness, not a vertical side-frame pattern. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}, center_brightness={center_brightness:.1f}."
        )
    
    elif side_brightness >= 55 and side_dark_ratio <= 0.50:
        video_format = "Horizontal"
        status = "Analyzed"
        reason = (
            "Horizontal: side areas are relatively bright and lack the strong dark pixel ratio "
            "typical of vertical side bars. "
            f"score={vertical_score}, side_brightness={side_brightness:.1f}, "
            f"side_dark_ratio={side_dark_ratio:.2f}."
        )

    elif side_brightness < 15 and center_brightness < 45 and center_std < 40:
        video_format = "Unknown"
        status = "Needs Review"
        reason = (
            "Very dark thumbnail. Duration did not confirm Shorts, so orientation is uncertain. "
            f"duration_seconds={duration_seconds}."
        )

    else:
        video_format = "Unknown"
        status = "Needs Review"
        reason = (
            "Unknown: ambiguous thumbnail. "
            f"score={vertical_score}, black_side_ratio={black_side_ratio:.2f}, "
            f"side_brightness={side_brightness:.1f}, side_dark_ratio={side_dark_ratio:.2f}."
        )

    notes = (
        f"score={vertical_score}, "
        f"black_side_ratio={black_side_ratio:.2f}, "
        f"side_brightness={side_brightness:.1f}, "
        f"center_brightness={center_brightness:.1f}, "
        f"side_dark_ratio={side_dark_ratio:.2f}, "
        f"side_std={side_std:.1f}, "
        f"center_std={center_std:.1f}."
    )

    return {
        "video_format": video_format,
        "status": status,
        "black_side_ratio": round(black_side_ratio, 2),
        "side_dark_ratio": round(side_dark_ratio, 4),
        "orientation_score": round(vertical_score, 2),
        "side_brightness": round(side_brightness, 2),
        "center_brightness": round(center_brightness, 2),
        "side_std": round(side_std, 2),
        "center_std": round(center_std, 2),
        "detection_reason": reason,
        "notes": notes,
    }

# --- Automation Loop ---

def main():
    records = table.all(view=VIEW_NAME)
    print(f"Records to analyze: {len(records)}")

    for record in records:
        record_id = record["id"]
        fields = record.get("fields", {})
        
        if fields.get("Matched?") is True:
            continue

        analysis_status = fields.get("Thumbnail Analysis Status")
        reanalyze = fields.get("Reanalyze Thumbnail", False)

        should_analyze = (
            not analysis_status
            or analysis_status == "Pending"
            or reanalyze is True
        )

        if not should_analyze:
            continue

        thumbnail_url = fields.get("Thumbnail URL")
        title = fields.get("Title", "Untitled")

        if not thumbnail_url:
            continue

        print(f"Analyzing: {title}")

        try:
            description = fields.get("Description", "")
            duration_seconds = fields.get("Duration (Seconds)")
            result = analyze_thumbnail(thumbnail_url, title, description, duration_seconds)

            table.update(record_id, {
                "Video Format": result["video_format"],
                # 🛠️ IS_SHORT REMOVED HERE
                "Thumbnail Analysis Status": result["status"],
                "Format Detection Method": "Thumbnail Analysis",
                "Format Detection Notes": result["notes"],
                "Black Side Ratio": result["black_side_ratio"],
                "Thumbnail Orientation Score": result["orientation_score"],
                "Side Brightness": result["side_brightness"],
                "Center Brightness": result["center_brightness"],
                "Side Dark Ratio": result["side_dark_ratio"],
                "Side Std": result["side_std"],
                "Center Std": result["center_std"],
                "Detection Reason": result["detection_reason"],
                "Reanalyze Thumbnail": False,
            })

            print(f"Analyzed: {title}")

        except Exception as e:
            table.update(record_id, {
                "Thumbnail Analysis Status": "Error",
                "Format Detection Notes": f"Thumbnail analysis error: {str(e)}",
                "Reanalyze Thumbnail": False,
            })
            print(f"Error analyzing {title}: {e}")

if __name__ == "__main__":
    main()