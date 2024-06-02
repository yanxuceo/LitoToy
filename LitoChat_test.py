import os
import asyncio
import re
from openai import OpenAI
from openai import AssistantEventHandler
import edge_tts
import tempfile

openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)


def contains_chinese(text):
    # Check if the text contains Chinese characters
    return any('\u4e00' <= char <= '\u9fff' for char in text)



def remove_emojis(text):
    # Remove emojis from the text
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


class CustomEventHandler(AssistantEventHandler):
    def __init__(self):
        super().__init__()
        self.response_text = ""
        self.accumulated_text = ""
        self.initial_text_processed = False

    def on_text_created(self, text) -> None:
        print(f"\nassistant(t_c) > ", end="", flush=True)
        if isinstance(text, str):
            self.response_text += text
            self.accumulated_text += text
            asyncio.run(self.text_to_speech(self.accumulated_text))
            self.accumulated_text = ""

    def on_text_delta(self, delta, snapshot):
        # Extract the text content from delta
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
                    # Trigger on major punctuation, accumulate on minor punctuation
                    if re.search(r'[。！？;!?]', text):  # Major punctuation marks
                        asyncio.run(self.text_to_speech(self.accumulated_text))
                        self.accumulated_text = ""
                else:
                    print(f"DEBUG: Non-string delta text: {text}")
                    if isinstance(text, str):
                        self.response_text += text
                        self.accumulated_text += text
                        if re.search(r'[。！？;!?]', text):  # Major punctuation marks
                            asyncio.run(self.text_to_speech(self.accumulated_text))
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

    async def text_to_speech(self, text):
        """Convert text to speech and play the audio."""
        if not isinstance(text, str):
            text = str(text)  # Ensure text is converted to a string

        # Choose the voice based on the text content
        if contains_chinese(text):
            voice = "zh-CN-XiaoyiNeural"
        else:
            voice = "en-GB-SoniaNeural"

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            output_file = temp_audio_file.name

        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                with open(output_file, "ab") as file:
                    file.write(chunk["data"])

        os.system(f"mpg123 {output_file}")


assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
thread_id = os.getenv('OPENAI_THREAD_ID')

# Start the chat loop
while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ['exit', 'quit']:
        print("Exiting the chat. Goodbye!")
        break

    # Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    # Create a Run and stream the response.
    event_handler = CustomEventHandler()
    with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="你扮演一个孩子的小伙伴，名字叫小小新，性格和善，说话活泼可爱，对孩子充满爱心，经常赞赏和鼓励孩子，用5岁孩子容易理解语言提供有趣和创新的回答，每次回复根据聊天主题询问她的看法以激发她的思考和好奇心。",
        event_handler=event_handler,
    ) as stream:
        stream.until_done()

    # Debug output to check the type of response_text
    print(f"DEBUG: Final response_text type: {type(event_handler.response_text)}")
    print(f"DEBUG: Final response_text: {event_handler.response_text}")
