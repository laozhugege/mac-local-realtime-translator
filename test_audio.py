import pyaudio
import numpy as np
import time

def main():
    print("Initializing PyAudio...")
    p = pyaudio.PyAudio()

    # List all available audio devices
    print("\n--- Available Audio Devices ---")
    blackhole_index = None
    multi_output_index = None
    
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        name = dev_info.get('name')
        inputs = dev_info.get('maxInputChannels')
        print(f"Device {i}: {name} (Inputs: {inputs})")
        
        if "BlackHole" in name and inputs > 0:
            blackhole_index = i

    print("\n------------------------------\n")

    if blackhole_index is None:
        print("Warning: Could not find BlackHole as an input device.")
        print("Please ensure it is installed and functioning.")
        print("Using system default input device for now...")
        device_index = p.get_default_input_device_info()['index']
    else:
        print(f"Found BlackHole at index {blackhole_index}. Using it for capture.")
        device_index = blackhole_index

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    # Mac BlackHole usually supports 44100 or 48000
    RATE = 16000 # Whisper prefers 16kHz, let's capture at 16kHz if possible, otherwise we resample. PyAudio can handle some resampling.

    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK)
        print(f"\nSuccessfully opened audio stream (Rate: {RATE}Hz, Channels: {CHANNELS}).")
        print("Listening to audio... (Press Ctrl+C to stop)")
        print("Play some video or music to see the volume meter react.\n")

        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # Calculate RMS volume
            if len(audio_data) > 0:
                rms = np.sqrt(np.mean(np.square(audio_data.astype(np.float32))))
                # simple visual volume bar
                bar_length = int(rms / 100) # adjust denominator for sensitivity
                bar = '#' * min(bar_length, 50)
                print(f"\rVolume: {rms:8.2f} | {bar:<50}", end='', flush=True)
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nStopping...")
    except Exception as e:
        print(f"\nError opening stream: {e}")
    finally:
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
