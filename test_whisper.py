import pyaudio
import numpy as np
import webrtcvad
import time
import queue
import threading
from faster_whisper import WhisperModel

# --- Configuration ---
WHISPER_MODEL = "small" # or "base"
SAMPLE_RATE = 16000 # Whisper and VAD require 16kHz
CHUNK_DURATION_MS = 30 # VAD requires 10, 20, or 30 ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000) # 480 frames
VAD_MODE = 1 # 0: Normal, 1: Low Bitrate, 2: Aggressive, 3: Very Aggressive

# VAD Settings (from V2.0 specs)
SILENCE_TRIGGER_MS = 250 # 0.25 seconds of silence triggers inference
MAX_CHUNK_DURATION_S = 5.0 # Force inference after 5 seconds
SILENCE_CHUNKS_THRESHOLD = int(SILENCE_TRIGGER_MS / CHUNK_DURATION_MS) # ~8 chunks
MAX_CHUNKS = int(MAX_CHUNK_DURATION_S * 1000 / CHUNK_DURATION_MS) # ~166 chunks

audio_queue = queue.Queue()

def transcribe_worker():
    print(f"[Transcriber] Loading faster-whisper model '{WHISPER_MODEL}'...")
    # Using float16 computation if supported, else int8
    # On M-series Macs, compute_type="default" or "int8" usually works best on CPU
    # ctranslate2 might not fully utilize M4 GPU via CoreML yet, so it defaults to CPU
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    print("[Transcriber] Model loaded. Waiting for audio chunks...")

    while True:
        try:
            # Wait for audio to process
            audio_data = audio_queue.get()
            if audio_data is None:
                break # Exit signal
            
            # Type assertion to help IDE type checker understand it's a numpy array here
            if not isinstance(audio_data, np.ndarray):
                continue

            # Normalize audio to [-1.0, 1.0] as expected by Whisper
            audio_float32 = audio_data.astype(np.float32) / 32768.0 # type: ignore

            start_time = time.time()
            # Transcribe
            segments, info = model.transcribe(audio_float32, beam_size=5, language="en")
            
            # Print results
            text = "".join([segment.text for segment in segments])
            elapsed_time = time.time() - start_time
            
            if text.strip():
                print(f"[Whisper] ({info.language} {info.language_probability:.2f}) [{elapsed_time:.3f}s]: {text.strip()}")
            
            audio_queue.task_done()
        except Exception as e:
            print(f"[Transcriber Error] {e}")

def main():
    print("Initializing VAD and PyAudio...")
    vad = webrtcvad.Vad(VAD_MODE)
    p = pyaudio.PyAudio()

    # Find BlackHole Device
    device_index = p.get_default_input_device_info()['index']
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        if "BlackHole" in dev_info.get('name') and dev_info.get('maxInputChannels') > 0:
            device_index = i
            break

    print(f"Using Audio Device Index: {device_index}")

    # Start Transcriber Thread
    transcriber_thread = threading.Thread(target=transcribe_worker, daemon=True)
    transcriber_thread.start()

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    print("\n[Audio] Listening... Play some English voice audio. (Ctrl+C to stop)")
    
    current_audio_buffer = []
    silence_counter = 0

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            
            # webrtcvad needs a bytes object of length corresponding to 10, 20, or 30ms at 16kHz
            is_speech = vad.is_speech(data, SAMPLE_RATE)

            if is_speech:
                silence_counter = 0
                current_audio_buffer.append(data)
            else:
                silence_counter += 1
                if current_audio_buffer: # We have some speech recorded
                    current_audio_buffer.append(data) # append a bit of silence for padding

            # Determine if we should push to transcription queue
            force_cut = len(current_audio_buffer) >= MAX_CHUNKS
            silence_cut = (silence_counter >= SILENCE_CHUNKS_THRESHOLD) and len(current_audio_buffer) > 10 # at least ~300ms of audio
            
            if force_cut or silence_cut:
                reason = "Force 5s cut" if force_cut else "0.25s Silence"
                # print(f"[Audio] Segment triggered ({reason}). Sending to Whisper...")
                
                # Combine bytes
                combined_audio = b"".join(current_audio_buffer)
                audio_np = np.frombuffer(combined_audio, dtype=np.int16)
                
                # Push to queue
                audio_queue.put(audio_np.copy())
                
                # Reset buffer
                current_audio_buffer = []
                silence_counter = 0

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        p.terminate()
        audio_queue.put(None) # Signal transcriber to stop
        transcriber_thread.join()

if __name__ == "__main__":
    main()
