import pyaudio
import wave
from openai import OpenAI
import os
import sys

class LitoSpeechToText:
    def __init__(self, device_index=1, format=pyaudio.paInt16, channels=1, rate=44100, chunk=4096, record_seconds=5, wave_output_filename="output.wav"):
        self.device_index = device_index
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.record_seconds = record_seconds
        self.wave_output_filename = wave_output_filename
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def list_audio_devices(self):
        audio = pyaudio.PyAudio()
        info = audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            if (audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print("Input Device id ", i, " - ", audio.get_device_info_by_host_api_device_index(0, i).get('name'))

    def record_audio(self):
        audio = pyaudio.PyAudio()

        # Redirect stderr to /dev/null to suppress ALSA/JACK logs
        fnull = open(os.devnull, 'w')
        original_stderr = sys.stderr
        sys.stderr = fnull

        # Start recording
        stream = audio.open(format=self.format, channels=self.channels,
                            rate=self.rate, input=True, input_device_index=self.device_index,
                            frames_per_buffer=self.chunk)
        print("Recording...")
        frames = []

        try:
            for _ in range(0, int(self.rate / self.chunk * self.record_seconds)):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)
        except IOError as e:
            print(f"Error recording audio: {e}")

        print("Finished recording.")

        # Stop recording
        stream.stop_stream()
        stream.close()
        audio.terminate()

        # Save the recorded data as a WAV file
        with wave.open(self.wave_output_filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))

        # Restore stderr
        sys.stderr = original_stderr
        fnull.close()

    def transcribe_audio(self):
        with open(self.wave_output_filename, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return transcription.text

    def get_speech_input(self):
        self.record_audio()
        print("Transcribing audio...")
        try:
            transcript = self.transcribe_audio()
            print("Transcription:")
            print(transcript)
            return transcript
        except Exception as e:
            print(f"Error during transcription: {e}")
            return None

# Usage example:
if __name__ == "__main__":
    stt = LitoSpeechToText()
    stt.list_audio_devices()
    
    while True:
        print("\nListening for user input...")
        user_input = stt.get_speech_input()

        if not user_input or user_input.lower() in ['exit', 'quit']:
            print("Exiting the test. Goodbye!")
            break

        print(f"User input: {user_input}")
