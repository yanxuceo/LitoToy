import pyaudio
import queue
from google.cloud import speech
from google.oauth2 import service_account

# Audio recording parameters
RATE = 44100
CHUNK = int(RATE / 10)  # 100ms

# Credentials for Google Cloud Speech API
credentials = service_account.Credentials.from_service_account_file('google_speech_config.json')

class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.closed = True

    def __enter__(self):
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer
        )
        self._buff = queue.Queue()
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.closed = True
        self._buff.put(None)  # Signal the generator to terminate

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            yield chunk

def main():
    client = speech.SpeechClient(credentials=credentials)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code='en-US'
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    while True:
        print("Say something:")
        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator()
            requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
            responses = client.streaming_recognize(streaming_config, requests)

            for response in responses:
                for result in response.results:
                    if result.is_final:
                        print(f"Final Transcript: {result.alternatives[0].transcript}")
                        print("End of utterance.")
                        break


if __name__ == "__main__":
    main()




if __name__ == "__main__":
    main()
