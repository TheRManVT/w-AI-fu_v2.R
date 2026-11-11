import sys
import threading
import time
import re
import wave

import pyaudio
import speech_recognition as sr
from pynput.keyboard import Key, KeyCode, Listener
from websockets.sync.client import connect

# Dictionary of words to replace
# e.g. said "Ronika", get recognized as "Ronica", will be replaced to "Ronika" which gets send to the AI
word_replacements = {
    "From speech": "To AI"
}


def apply_replacements(text: str) -> str:
    for word, replacement in word_replacements.items():
        # \b ensures whole word match, re.IGNORECASE makes it case-insensitive
        text = re.sub(rf"\b{word}\b", replacement, text, flags=re.IGNORECASE)
    return text


def log(message: str):
    print(message, file=sys.stderr, flush=True)


def arg(position: int, default: str) -> str:
    try:
        return sys.argv[position]
    except IndexError:
        return default


# Arguments are passed by source/app/input/input_voice.ts
use_ptt = int(arg(1, "0")) == 1

try:
    index = int(sys.argv[2])
except (IndexError, ValueError):
    index = None

provider = arg(3, "google")
api_key = arg(4, "")
stt_language = arg(5, "en-US")
ptt_key_name = arg(6, "ctrl_r")      # hold to record
toggle_key_name = arg(7, "shift_r")  # press to start, press again to stop
port = arg(8, "8711")                # must match STT_PORT in input_voice.ts

ws = None
PTT_KEY = None
TOGGLE_KEY = None

# Audio format used for push-to-talk. 16 kHz mono is what speech recognition needs,
# and it uploads faster than 44.1 kHz.
RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
SAMPLE_WIDTH = 2                     # bytes per sample for paInt16
MIN_FRAMES = 5                       # ignore taps shorter than about 0.3 s


def key_from_name(name: str):
    """Converts a key name from the config (e.g. "ctrl_r", "f9", "v") to a pynput key."""
    if name == "":
        return None
    if hasattr(Key, name):
        return getattr(Key, name)
    if len(name) == 1:
        return KeyCode.from_char(name)
    log(f"Unknown key name in config: {name!r}")
    return None


def matches(pressed, target) -> bool:
    if target is None:
        return False
    if isinstance(target, KeyCode):
        # Compare characters so letter keys match regardless of Shift/Caps state
        return (
            isinstance(pressed, KeyCode)
            and pressed.char is not None
            and pressed.char.lower() == target.char.lower()
        )
    return pressed == target


def connect_to_app(retries: int = 50, delay: float = 0.2):
    """The app opens the WebSocket server just after starting this process, so retry briefly."""
    for _ in range(retries):
        try:
            return connect(f"ws://localhost:{port}")
        except OSError:
            time.sleep(delay)
    raise RuntimeError(f"Could not reach the w-AI-fu app on port {port}. Is it running?")


def main():
    global ws, PTT_KEY, TOGGLE_KEY

    with connect_to_app() as websocket:
        ws = websocket
        if use_ptt:
            PTT_KEY = key_from_name(ptt_key_name)
            TOGGLE_KEY = key_from_name(toggle_key_name)
            print(
                f"Using push-to-talk ({ptt_key_name or 'disabled'}) "
                f"and toggle-to-talk ({toggle_key_name or 'disabled'}).",
                flush=True,
            )
            threading.Thread(target=mic_loop, daemon=True).start()
            push_to_talk()
        else:
            print("Using speech recognition.", flush=True)
            speech_recognition()


# --- Push-to-talk / toggle-to-talk ------------------------------------------

recording = threading.Event()   # set while audio is being captured
recording_source = None         # "ptt" or "toggle": which key started the recording
ptt_held = False                # tracks held keys so auto-repeat is ignored
toggle_held = False
current_frames = []             # audio chunks of the recording in progress


def mic_loop():
    """Keeps the microphone open for the whole session, so pressing a key starts recording instantly."""
    global current_frames
    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            format=FORMAT,
            channels=1,
            rate=RATE,
            input=True,
            output=True,
            frames_per_buffer=CHUNK,
            input_device_index=index,
            output_device_index=None,
        )
        log("Microphone ready.")
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            if recording.is_set():
                current_frames.append(data)
    except Exception as e:
        log(f"Microphone error: {e}")
    finally:
        pa.terminate()


def start_recording(source: str):
    global recording_source, current_frames
    if recording.is_set():
        return
    recording_source = source
    current_frames = []
    recording.set()
    print("Recording...", flush=True)


def stop_recording():
    global current_frames
    if not recording.is_set():
        return
    recording.clear()
    frames = current_frames
    current_frames = []
    print("Finished recording.", flush=True)
    # Recognition takes a moment, so run it in its own thread instead of blocking the key listener
    threading.Thread(target=send_recording, args=(frames,), daemon=True).start()


def send_recording(frames):
    if len(frames) < MIN_FRAMES:
        return
    audio = sr.AudioData(b"".join(frames), RATE, SAMPLE_WIDTH)
    text = recognize_audio(audio, sr.Recognizer(), throw=False)
    if text.strip() != "":
        ws.send(text)


def on_press(key):
    global ptt_held, toggle_held

    if matches(key, PTT_KEY) and not ptt_held:
        ptt_held = True
        start_recording("ptt")
    elif matches(key, TOGGLE_KEY) and not toggle_held:
        toggle_held = True
        if recording.is_set() and recording_source == "toggle":
            stop_recording()
        elif not recording.is_set():
            start_recording("toggle")


def on_release(key):
    global ptt_held, toggle_held

    if matches(key, PTT_KEY):
        ptt_held = False
        if recording_source == "ptt":
            stop_recording()
    if matches(key, TOGGLE_KEY):
        toggle_held = False


def push_to_talk():
    with Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
        log("PTT Listener has joined.")


# --- Continuous listening (used when push-to-talk is off) -------------------

last_received = 0
reset_next = False
recognized_text = ""


def callback(recognizer, audio):
    global last_received, recognized_text, reset_next
    log("CALLBACK")
    if reset_next:
        recognized_text = ""
        reset_next = False
    last_received = time.time()
    ws.send("")
    text = recognize_audio(audio, recognizer, throw=False)
    ws.send("")
    log(text)
    recognized_text = recognized_text + text + " "
    last_received = time.time()
    log(recognized_text)


def speech_recognition():
    global last_received, recognized_text, reset_next
    recognizer = sr.Recognizer()

    recognizer.energy_threshold = 1400
    recognizer.pause_threshold = 0.35
    recognizer.non_speaking_duration = 0.35
    recognizer.dynamic_energy_threshold = False

    recognizer.whisper_model = "tiny.en"  # "base.en" <- better accuracy but may lead to undesired translation to french
    recognizer.operation_timeout = 2

    mic = sr.Microphone(device_index=index)
    recognizer.listen_in_background(mic, callback)

    while True:
        time.sleep(0.01)
        if (time.time() - last_received > 1.5) and (recognized_text != ""):
            log("SENT TEXT TO AI")
            ws.send(recognized_text)
            recognized_text = ""
            reset_next = True


# --- Recognition -------------------------------------------------------------

def recognize_audio(audio: sr.AudioData, recognizer: sr.Recognizer, throw: bool) -> str:
    text = ""
    start_time = time.time()
    try:
        match provider:
            case "google":
                text = recognizer.recognize_google(audio, language=stt_language)
            case "openai":
                text = recognizer.recognize_whisper_api(audio, api_key=api_key)
    except sr.exceptions.SetupError:
        if throw:
            raise Exception()
        log("Incorrect OpenAI token.")
    except sr.exceptions.UnknownValueError:
        if throw:
            raise Exception()
        log("Could not understand audio.")
    except sr.exceptions.RequestError:
        if throw:
            raise Exception()
        log("Could not contact audio recognition API.")

    log(f"Recognition took: {round((time.time() - start_time) * 1_000)} ms")

    return apply_replacements(text)


if __name__ == "__main__":
    main()