import requests
import json
import time
import sys

# --- Configuration ---
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct" # Can also test qwen2.5:3b-instruct

SYSTEM_PROMPT = """你是字幕翻译引擎。
只输出中文翻译。
不要解释。
不要补充。
不要改写语气。"""

def translate_text(english_text):
    prompt = f"English: {english_text}\nTranslation:"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_predict": 100 # limit output length to prevent hallucinated essays
        }
    }
    
    start_time = time.time()
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=3.0)
        response.raise_for_status()
        
        result = response.json()
        translation = result.get("response", "").strip()
        elapsed = time.time() - start_time
        
        return translation, elapsed
        
    except requests.exceptions.RequestException as e:
        print(f"[API Error] {e}")
        return None, time.time() - start_time

def main():
    print(f"Testing local translation using Ollama ({OLLAMA_MODEL})...")
    print("Ensure Ollama is running (`ollama serve`).\n")
    
    test_sentences = [
        "Hello everyone, welcome back to my channel.",
        "Today we are going to look at the new M4 Max chip from Apple.",
        "It's absolutely incredible how fast this thing is.",
        "The unified memory architecture allows for some crazy bandwidth.",
        "Let me know what you think in the comments below."
    ]
    
    for idx, sentence in enumerate(test_sentences):
        print(f"Test {idx+1}/{len(test_sentences)}")
        print(f"Original: {sentence}")
        
        translation, elapsed = translate_text(sentence)
        
        if translation is not None:
            print(f"Translated: {translation}")
            print(f"Time Taken: {elapsed:.3f}s")
            if elapsed > 0.4:
                print(f"  -> Warning: Latency exceeded 400ms target ({elapsed*1000:.0f}ms)")
        else:
            print("Translation failed.")
        print("-" * 40)
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        print("Interactive mode. Type English sentences to translate (Ctrl+C to exit):")
        try:
            while True:
                text = input("> ")
                if not text.strip(): continue
                translation, elapsed = translate_text(text)
                print(f"< {translation} [{elapsed:.3f}s]\n")
        except KeyboardInterrupt:
            print("\nExiting.")
    else:
        main()
        print("\nYou can also run this interactively: python test_translate.py --interactive")
