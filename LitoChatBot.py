import os

assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
thread_id = os.getenv('OPENAI_THREAD_ID')


import os
import asyncio
import re
import tempfile
import queue
import threading
import pyaudio
from google.cloud import speech
from google.oauth2 import service_account
import openai
import edge_tts

# Google Cloud Speech setup
credentials = service_account.Credentials.from_service_account_file('google_speech_config.json')
client_speech = speech.SpeechClient(credentials=credentials)

# Audio parameters
RATE = 44100
CHUNK = int(RATE / 10)  # 100ms

# OpenAI client setup
openai_api_key = os.getenv('OPENAI_API_KEY')
client_openai = openai.OpenAI(api_key=openai_api_key)

# Global TTS task and interaction task references
tts_task = None
interaction_task = None

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
    global tts_task

    if not isinstance(text, str):
        text = str(text)  # Ensure text is converted to a string

    # Cancel the previous TTS task if it exists
    if tts_task:
        tts_task.cancel()
        try:
            await tts_task
        except asyncio.CancelledError:
            print("Previous TTS task cancelled")

    async def tts_task_fn(text_segment):
        # Choose the voice based on the text content
        if contains_chinese(text_segment):
            voice = "zh-CN-XiaoyiNeural"
        else:
            voice = "en-GB-SoniaNeural"

        communicate = edge_tts.Communicate(text_segment, voice)
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

    # Create a new TTS task
    tts_task = asyncio.create_task(tts_task_fn(text))
    await tts_task

class CustomEventHandler(openai.AssistantEventHandler):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.response_text = ""
        self.accumulated_text = ""
        self.initial_text_processed = False
        self.responses = queue.Queue()
        self.tts_queue = asyncio.Queue()
        self.tts_task = None
        self.sentence_end_pattern = re.compile(r'[。！？.!?]')

    async def process_tts_queue(self):
        while True:
            text = await self.tts_queue.get()
            if self.tts_task:
                self.tts_task.cancel()
                try:
                    await self.tts_task
                except asyncio.CancelledError:
                    print("Previous TTS task cancelled")
            self.tts_task = asyncio.create_task(text_to_speech(text))
            await self.tts_task
            self.tts_queue.task_done()

    def on_text_created(self, text) -> None:
        print(f"\nassistant(t_c) > ", end="", flush=True)
        if isinstance(text, str):
            self.responses.put(text)
            self.response_text += text
            self.accumulated_text += text
            # 直接将完整的响应文本放入 TTS 队列
            asyncio.run_coroutine_threadsafe(self.tts_queue.put(self.accumulated_text), self.loop)
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
                    # 在句子结束标点时，将累积的文本放入队列
                    if self.sentence_end_pattern.search(text):
                        asyncio.run_coroutine_threadsafe(self.tts_queue.put(self.accumulated_text), self.loop)
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
    global interaction_task, tts_task

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

        async for response in async_responses(responses):
            for result in response.results:
                if result.is_final:
                    if interaction_task:
                        interaction_task.cancel()
                        try:
                            await interaction_task
                        except asyncio.CancelledError:
                            print("Previous interaction task cancelled")
                    if tts_task:
                        tts_task.cancel()
                        try:
                            await tts_task
                        except asyncio.CancelledError:
                            print("Previous TTS task cancelled")
                    input_text = result.alternatives[0].transcript
                    print(f"Recognized: {input_text}")
                    interaction_task = asyncio.create_task(handle_interaction(input_text))

async def handle_interaction(input_text):
    response_text = await ask_chatbot(input_text)
    print(f"Bot response: {response_text}")

async def async_responses(responses):
    loop = asyncio.get_event_loop()
    while True:
        try:
            response = await loop.run_in_executor(None, next, responses)
            yield response
        except StopIteration:
            break

def ask_chatbot_sync(input_text, loop):
    global assistant_id, thread_id

    message = client_openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=input_text
    )

    event_handler = CustomEventHandler(loop)
    # 启动 TTS 队列处理任务
    asyncio.run_coroutine_threadsafe(event_handler.process_tts_queue(), loop)

    with client_openai.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="你扮演一个孩子的小伙伴，名字叫小小新，性格和善，说话活泼可爱，对孩子充满爱心，经常赞赏和鼓励孩子，用5岁孩子容易理解语言提供有趣和创新的回答，回答不要超过50字。",
        event_handler=event_handler
    ) as stream:
        stream.until_done()

    return event_handler.response_text

async def ask_chatbot(input_text):
    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(None, ask_chatbot_sync, input_text, loop)
    return response_text

async def main():
    global interaction_task
    loop = asyncio.get_event_loop()

    while True:
        if interaction_task:
            interaction_task.cancel()
            try:
                await interaction_task
            except asyncio.CancelledError:
                print("Previous interaction task cancelled")

        interaction_task = asyncio.create_task(handle_speech())
        await interaction_task

if __name__ == "__main__":
    asyncio.run(main())