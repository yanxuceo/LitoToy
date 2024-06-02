import os

assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
thread_id = os.getenv('OPENAI_THREAD_ID')

import asyncio
import re
import tempfile
import queue
import pyaudio

from google.cloud import speech
from google.oauth2 import service_account

from openai import OpenAI
from openai import AssistantEventHandler
import edge_tts

# Google Cloud Speech setup
credentials = service_account.Credentials.from_service_account_file('google_speech_config.json')
client_speech = speech.SpeechClient(credentials=credentials)

# Audio parameters
RATE = 44100
CHUNK = int(RATE / 10)  # 100ms

# OpenAI client setup
openai_api_key = os.getenv('OPENAI_API_KEY')
client_openai = OpenAI(api_key=openai_api_key)

class MicrophoneStream:
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
        self._buff.put(None)

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            yield chunk

def contains_chinese(text):
    return any('\u4e00' <= char <= '\u9fff' for char in text)

def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"  # other symbols
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

async def text_to_speech(text):
    """Convert text to speech and play the audio."""
    if not isinstance(text, str):
        text = str(text)  # Ensure text is converted to a string

    # Choose the voice based on the text content
    if contains_chinese(text):
        voice = "zh-CN-XiaoyiNeural"
    else:
        voice = "en-GB-SoniaNeural"

    communicate = edge_tts.Communicate(text, voice)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
        output_file = temp_audio_file.name
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    with open(output_file, "ab") as file:
                        file.write(chunk["data"])
            os.system(f"mpg123 -q {output_file}")
        except edge_tts.exceptions.NoAudioReceived as e:
            print(f"No audio received: {e}")

class CustomEventHandler(AssistantEventHandler):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.response_text = ""
        self.accumulated_text = ""
        self.initial_text_processed = False
        self.responses = queue.Queue()

    async def text_to_speech(self, text):
        await text_to_speech(text)

    def on_text_created(self, text) -> None:
        print(f"\nassistant(t_c) > ", end="", flush=True)
        if isinstance(text, str):
            self.responses.put(text)
            self.response_text += text
            self.accumulated_text += text
            #asyncio.run_coroutine_threadsafe(self.text_to_speech(self.accumulated_text), self.loop)
            self.accumulated_text = ""

    def on_text_delta(self, delta, snapshot):
        print(f"DEBUG: Received delta: {delta}")
        text = getattr(delta, 'value', None)
        if text:
            print(f"DEBUG: Delta text type: {type(text)}")
            if not self.initial_text_processed and isinstance(text, str):
                self.response_text += text
                self.accumulated_text += text
                self.initial_text_processed = True
            else:
                if isinstance(text, str):
                    self.response_text += text
                    self.accumulated_text += text
                    print(text, end="", flush=True)
                    if re.search(r'[。！？;!?]', text):
                        #asyncio.run_coroutine_threadsafe(self.text_to_speech(self.accumulated_text), self.loop)
                        self.accumulated_text = ""

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant(t_c_c) > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                print(f"\nassistant(c_i_i) > ", end="", flush=True)
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\nassistant(c_i_o) > ", end="", flush=True)
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

async def handle_speech():
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code='cmn-Hans-CN'
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
        responses = client_speech.streaming_recognize(streaming_config, requests)

        for response in responses:
            for result in response.results:
                if result.is_final:
                    input_text = result.alternatives[0].transcript
                    print(f"Recognized: {input_text}")
                    response_text = await ask_chatbot(input_text)
                    await text_to_speech(response_text)

def ask_chatbot_sync(input_text, loop):
    message = client_openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=input_text
    )

    event_handler = CustomEventHandler(loop)
    with client_openai.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="你扮演一个孩子的小伙伴，名字叫小小新，性格和善，说话活泼可爱，对孩子充满爱心，经常赞赏和鼓励孩子，用5岁孩子容易理解语言提供有趣和创新的回答，不要超过50字。",
        event_handler=event_handler
    ) as stream:
        stream.until_done()

    
    return event_handler.response_text

async def ask_chatbot(input_text):
    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(None, ask_chatbot_sync, input_text, loop)
    return response_text

def main():
    loop = asyncio.get_event_loop()
    asyncio.run(handle_speech())

if __name__ == "__main__":
    main()
