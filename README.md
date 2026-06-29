# YouTube Thumbnail Analyzer

An automated Python script that connects to an Airtable queue, analyzes YouTube thumbnails via their URLs, and determines whether the video is formatted as a **Vertical / Short** or a **Horizontal** video based on image heuristics.

## 📌 Project Overview

This tool is designed to run automatically (e.g., via a daily cron job at 9:05 AM) after a fresh batch of YouTube RSS feed data is cached in Airtable. It uses the `Pillow` (PIL) library to crop thumbnails into sections (Left, Center, Right) and calculates brightness, standard deviation, and dark pixel ratios to confidently categorize the video format.

### Key Features
* **Airtable Integration:** Automatically fetches un-analyzed records and updates them with the final status, scores, and detection reasoning.
* **Intelligent Image Scoring:** Detects "black bars" typical of YouTube Shorts by comparing side brightness to center brightness.
* **Redirect & Error Handling:** Safely handles HTTP redirects and gracefully reports failed downloads back to Airtable.
* **Text Signal Detection:** Scans video titles and descriptions for `#shorts` or similar tags for instant classification.

---

## 📂 Project Structure

```text
/thumbnail-analyzer
│
├── .venv/                  # Python virtual environment
├── .env                    # Environment variables (API keys)
├── .gitignore              # Ignored files for version control
├── analyze_thumbnails.py   # Main execution script
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation

⚙️ Prerequisites
Python 3.8+

An Airtable account with a Base and Table configured with the proper fields (e.g., "Thumbnail URL", "Video Format", "Is Short?", etc.).

An Airtable Personal Access Token (API Key).

🚀 Setup & Installation
1. Clone or download the repository

2. Create and activate a virtual environment

```
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

3. Install Dependencies

```bash
pip install -r requirements.txt
```

(Dependencies include requests, Pillow, pyairtable, numpy, and python-dotenv)

4. Configure Environment Variables
Create a .env file in the root directory and add your Airtable credentials:

```Ini,TOML
AIRTABLE_API_KEY="your_personal_access_token_here"
AIRTABLE_BASE_ID="your_base_id_here"
AIRTABLE_TABLE_NAME="Published Feed Cache"
AIRTABLE_VIEW_NAME="Thumbnail Analysis Queue"

💻 Usage
To run the script manually, simply execute:
```bash
python analyze_thumbnails.py
```

Automation (Cron Job Example)
If you want to automate this to run daily at 9:05 AM, you can add the following to your crontab (crontab -e on Linux/macOS):
```bash
5 9 * * * cd /path/to/thumbnail-analyzer && /path/to/thumbnail-analyzer/.venv/bin/python analyze_thumbnails.py >> cron.log 2>&1

```

🧠 How the Logic Works
Fetch: The script pulls records from the Airtable view that are marked as "Pending" or need re-analysis.

Download: Images are fetched into memory (handling redirects and mimicking a standard browser User-Agent to avoid 403 errors).

Analyze: * The image is sliced into left (22%), center (30%), and right (22%) columns.

It calculates average brightness and dark pixel ratios for these columns.

A vertical_score is tallied. High contrast between a bright center and pitch-black sides strongly indicates a Vertical/Shorts format.

Update: The logic tree classifies the video (Horizontal, Vertical / Shorts, or Unknown) and patches the Airtable record with the result and the statistical reasoning.

---

### 3. The `requirements.txt` File

Just to be absolutely sure your project is complete, if you haven't generated your `requirements.txt` yet, you can create it by running this in your terminal (while your virtual environment is activated):

```bash
pip freeze > requirements.txt
```

Alternatively, based on your imports, your requirements.txt should look exactly like this:

requests
Pillow
pyairtable
numpy
python-dotenv