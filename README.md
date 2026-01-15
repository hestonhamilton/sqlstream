# sqlstream

This is a project created to verify the feasibility of using a relational database management system (RDBMS) as a real-time video display engine. It serves as a proof of concept following a discussion regarding the limitations of database tables in multimedia contexts.

The system treats the database not just as a storage medium, but as the active video buffer. By pre-calculating frames into a library table and utilizing a high-speed SQL UPDATE loop to synchronize a display table, the script uses SQLite to drive terminal-based video playback.

### System Logic
1. Ingestion: The script retrieves video data from local files or YouTube URLs via yt-dlp.
2. Conversion: Frames are processed into ANSI TrueColor escape sequences or grayscale ASCII characters based on user configuration.
3. Relational Storage: Every line of every frame is stored as an individual row in a 'frame_library' table.
4. Playback Loop: The engine executes a continuous loop that performs a SQL UPDATE to synchronize the 'display' table with the next frame index, then SELECTs those rows for terminal rendering.

### Example

Here is a short example of the script in action:

[![asciicast](https://asciinema.org/a/NTTy08pK9vMORE1l.svg)](https://asciinema.org/a/NTTy08pK9vMORE1l)



---

### Installation
1. Clone the repository.
2. Create a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

### Usage Instructions

#### 1. Instant Playback (Transient Memory)
To run a video immediately in RAM without generating a persistent database file, use the --source flag.

Example (Grayscale):
python3 sqlstream.py --source "https://www.youtube.com/watch?v=FtutLA63Cp8"

Example (Color):
python3 sqlstream.py --source "https://www.youtube.com/watch?v=djV11Xbc914" --color

#### 2. Persistence Mode (Disk Export)
To save processed frame data to a SQLite .db file for archival or later demonstration:

Example:
python3 sqlstream.py --source "video_file.mp4" --out project_proof.db --color

#### 3. Database Playback (RAM-Loaded)
To play back an existing database file. The engine utilizes sqlite3.backup() to clone the disk-based data into RAM for maximum query throughput during playback.

Example:
python3 sqlstream.py --play-db project_proof.db --fps 30

---

### CLI Options
| Flag | Description |
| :--- | :--- |
| --source | Path to local video file or YouTube URL. |
| --play-db | Path to an existing .db file for immediate playback. |
| --duration | Max duration of video to process in seconds (default: 60). |
| --fps | Target playback frame rate (default: 30). |
| --color | Enables ANSI TrueColor background rendering. |
| --out | Path to save the database to disk (disables immediate play). |

### Performance Optimization
For optimal visual fidelity, decrease the terminal font size. This increases the character density per row, resulting in higher effective resolution for the relational rendering engine.
