import pyaudio
import wave
import openai
import os
from openai import OpenAI


# Audio recording parameters

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096  # Increased buffer size
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"

def list_audio_devices():
    audio = pyaudio.PyAudio()
    info = audio.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print("Input Device id ", i, " - ", audio.get_device_info_by_host_api_device_index(0, i).get('name'))

def record_audio(device_index=None):
    audio = pyaudio.PyAudio()

    # Start recording
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True, input_device_index=device_index,
                        frames_per_buffer=CHUNK)
    print("Recording...")
    frames = []

    try:
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
    except IOError as e:
        print(f"Error recording audio: {e}")

    print("Finished recording.")

    # Stop recording
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save the recorded data as a WAV file
    with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))


openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)


def transcribe_audio(filename):
    with open(filename, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    print(transcription.text)


if __name__ == "__main__":
    print("Available audio devices:")
    list_audio_devices()
    
    # Set the device index for your microphone. You can get this from the list printed above.
    device_index = None
    try:
        device_index = int(input("Enter the device index to use for recording (or press Enter to use default): ") or None)
    except ValueError:
        device_index = None

    record_audio(device_index)
    print("Transcribing audio...")
    transcript = transcribe_audio(WAVE_OUTPUT_FILENAME)
    