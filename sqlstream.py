#!/usr/bin/env python3
import cv2
import sqlite3
import time
import sys
import shutil
import yt_dlp
import argparse
import os

class SQLVideoEngine:
    def __init__(self, db_path=":memory:", width=None, height=None, chars="@%#*+=-:. "):
        """
        Initializes the SQL Video Engine.
        :param db_path: Path to the SQLite database file or ':memory:' for transient storage.
        """
        self.db_path = db_path
        self.chars = chars
        self.display_w = width
        self.display_h = height
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._set_performance_pragmas(self.conn)

    def _set_performance_pragmas(self, conn):
        """Applies SQLite optimizations for high-frequency data throughput."""
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA journal_mode = MEMORY")

    def _prepare_tables(self):
        """Initializes the relational schema for frame storage and active display."""
        self.cursor.execute("DROP TABLE IF EXISTS frame_library")
        self.cursor.execute("DROP TABLE IF EXISTS display")
        self.cursor.execute("CREATE TABLE frame_library (frame_id INTEGER, line_no INTEGER, content TEXT)")
        self.cursor.execute("CREATE TABLE display (line_no INTEGER PRIMARY KEY, content TEXT)")
        self.conn.commit()

    def get_stream_url(self, url):
        """Extracts direct video stream URL from a YouTube link using yt-dlp."""
        ydl_opts = {'format': 'best[height<=360]', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)['url']

    def frame_to_ansi(self, frame, use_color=True):
        """Converts image frames into ANSI-formatted text or color escape sequences."""
        resized = cv2.resize(frame, (self.display_w, self.display_h), interpolation=cv2.INTER_AREA)
        lines = []
        for row in resized:
            if use_color:
                # Generates TrueColor ANSI background escape sequences
                line = "".join([f"\033[48;2;{r};{g};{b}m " for b, g, r in row]) + "\033[0m"
            else:
                # Maps pixel brightness to character density
                gray = cv2.cvtColor(row.reshape(1, -1, 3), cv2.COLOR_BGR2GRAY)[0]
                line = "".join([self.chars[p // 32] for p in gray])
            lines.append(line)
        return lines

    def ingest(self, source, duration, fps_target, use_color):
        """Processes video source into the relational frame_library table."""
        self._prepare_tables()
        is_url = source.startswith(('http://', 'https://'))
        video_src = self.get_stream_url(source) if is_url else source
        
        cap = cv2.VideoCapture(video_src)
        if not cap.isOpened(): return False

        cols, rows = shutil.get_terminal_size()
        self.display_w = self.display_w or cols
        self.display_h = self.display_h or (rows - 3)

        video_fps = cap.get(cv2.CAP_PROP_FPS) or fps_target
        max_frames = int(video_fps * duration)
        
        frame_id = 0
        batch = []
        while cap.isOpened() and frame_id < max_frames:
            ret, frame = cap.read()
            if not ret: break
            lines = self.frame_to_ansi(frame, use_color)
            for i, line in enumerate(lines):
                batch.append((frame_id, i, line))
            frame_id += 1
            if frame_id % 30 == 0:
                print(f"[*] Buffering frames: {frame_id}/{max_frames}", end='\r')

        self.cursor.executemany("INSERT INTO frame_library VALUES (?, ?, ?)", batch)
        self.cursor.executemany("INSERT INTO display VALUES (?, '')", [(i,) for i in range(self.display_h)])
        self.conn.commit()
        cap.release()
        print(f"\n[*] Ingestion complete. {frame_id} frames committed to SQLite.")
        return True

    def play(self, fps_target):
        """Executes the playback loop using SQL UPDATE and SELECT operations."""
        self.cursor.execute("SELECT MAX(frame_id) FROM frame_library")
        total = self.cursor.fetchone()[0]
        cols, _ = shutil.get_terminal_size()

        for f_id in range(total + 1):
            start = time.perf_counter()
            # Synchronizes the display table with the next frame from the library
            self.cursor.execute("""
                UPDATE display SET content = (
                    SELECT content FROM frame_library 
                    WHERE frame_id = ? AND line_no = display.line_no
                )
            """, (f_id,))
            
            # Retrieves current display state for terminal output
            self.cursor.execute("SELECT content FROM display ORDER BY line_no")
            frame_data = self.cursor.fetchall()
            output = "\n".join(r[0] for r in frame_data)
            
            # Displays frame and session metadata
            stats = f" [ FRAME {f_id}/{total} | SQL UPDATES: {(f_id+1)*len(frame_data):,} ] "
            sys.stdout.write("\033[H" + output + "\n" + stats.center(cols, "="))
            sys.stdout.flush()
            
            delay = (1/fps_target) - (time.perf_counter() - start)
            if delay > 0: time.sleep(delay)

def main():
    parser = argparse.ArgumentParser(description="Relational Database Video Playback Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Path to video file or YouTube URL")
    group.add_argument("--play-db", help="Path to existing .db file for playback")
    
    parser.add_argument("--duration", type=int, default=60, help="Max video length in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Target playback frame rate")
    parser.add_argument("--color", action="store_true", help="Use ANSI TrueColor formatting")
    parser.add_argument("--out", help="Optional output path for the database file")
    
    args = parser.parse_args()

    # Mode 1: Playback from existing database
    if args.play_db:
        if not os.path.exists(args.play_db):
            print(f"Error: Database file {args.play_db} not found.")
            sys.exit(1)
        # Load persistent database into RAM to minimize disk I/O latency
        engine = SQLVideoEngine(db_path=":memory:")
        disk_conn = sqlite3.connect(args.play_db)
        disk_conn.backup(engine.conn)
        disk_conn.close()
        engine.play(args.fps)

    # Mode 2: Immediate ingestion and optional persistence
    else:
        # Defaults to :memory: if no --out path is provided
        db_destination = args.out if args.out else ":memory:"
        engine = SQLVideoEngine(db_path=db_destination)
        try:
            if engine.ingest(args.source, args.duration, args.fps, args.color):
                engine.play(args.fps)
        except KeyboardInterrupt:
            print("\033[0m\nProcess interrupted by user.")

if __name__ == "__main__":
    main()
