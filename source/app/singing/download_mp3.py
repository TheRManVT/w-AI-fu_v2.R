import os
import sys
import subprocess
import pytube

# Called from sing_onthefly.ts

OUT_PATH = os.environ["LOCALAPPDATA"] + "\\w-AI-fu_v2_tmp\\dl"
FINAL_PATH = os.environ["LOCALAPPDATA"] + "\\w-AI-fu_v2_tmp\\in"

QUERY = sys.argv[1]
MIN_VIEWS = int(sys.argv[2])
CAPTIONS_LANG = sys.argv[3]
SKIP_AGE_RESTRICTED = int(sys.argv[4])

print("Searching for:", QUERY)

search = pytube.Search(query=QUERY)
results: list[pytube.YouTube] = search.results

if not results:
    print("ERROR: Results were None.", file=sys.stderr)
    exit(1)

if not len(results):
    print("ERROR: Failed to get search results.", file=sys.stderr)
    exit(1)

video: pytube.YouTube = results[0]
print("Found URL:", video.watch_url)

if video.age_restricted and SKIP_AGE_RESTRICTED:
    print("ERROR: Video is age restricted.", file=sys.stderr)
    exit(1)

try:
    video.check_availability()
except:
    print("ERROR: Video is unavailable.", file=sys.stderr)
    exit(1)

if video.views < MIN_VIEWS:
    print(f"ERROR: Video has less than {MIN_VIEWS} views.", file=sys.stderr)
    exit(1)

audio = video.streams.filter(only_audio=True).first()

caption = None
if CAPTIONS_LANG in video.captions:
    caption = video.captions[CAPTIONS_LANG]
else:
    print("No captions were found for the selected language.")

if os.path.exists(OUT_PATH + "\\audio.mp3"):
    os.remove(OUT_PATH + "\\audio.mp3")

if os.path.exists(OUT_PATH + f"\\captions ({CAPTIONS_LANG}).xml"):
    os.remove(OUT_PATH + f"\\captions ({CAPTIONS_LANG}).xml")

print("Downloading audio...")

if caption:
    caption.download(title="captions", output_path=OUT_PATH, srt=False)

audio.download(filename="audio.mp3", output_path=OUT_PATH)

ffmpeg = os.path.abspath(os.environ["CWD"] + '/bin/ffmpeg/ffmpeg.exe')
subprocess.run([ffmpeg, '-loglevel', 'quiet', '-y', '-i', f'{OUT_PATH}\\audio.mp3', f'{FINAL_PATH}\\audio.wav'])

print("Done.")
exit(0)