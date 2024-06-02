import os
import asyncio
import re
from openai import OpenAI
from openai import AssistantEventHandler
import edge_tts
import tempfile

openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

# 1. Create assistant
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="You are a personal math tutor. Write and run code to answer math questions.",
    tools=[{"type": "code_interpreter"}],
    model="gpt-4o",
)

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
                self.initial_text_processed = True
            if isinstance(text, str):
                self.response_text += text
                self.accumulated_text += text
                print(text, end="", flush=True)
                # Trigger on punctuation excluding commas
                if re.search(r'[.;!?]', text):
                    asyncio.run(self.text_to_speech(self.accumulated_text))
                    self.accumulated_text = ""
            else:
                print(f"DEBUG: Non-string delta text: {text}")
                if isinstance(text, str):
                    self.response_text += text
                    self.accumulated_text += text
                    if re.search(r'[.;!?]', text):  # Trigger on punctuation excluding commas
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

        voice = "en-GB-SoniaNeural"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            output_file = temp_audio_file.name

        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                with open(output_file, "ab") as file:
                    file.write(chunk["data"])

        os.system(f"mpg123 {output_file}")

# Start the chat loop
while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ['exit', 'quit']:
        print("Exiting the chat. Goodbye!")
        break

    # 2. Create thread
    thread = client.beta.threads.create()

    # 3. Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input
    )

    # 4. Create a Run and stream the response.
    event_handler = CustomEventHandler()
    with client.beta.threads.runs.stream(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Please address the user as Jane Doe. The user has a premium account.",
        event_handler=event_handler,
    ) as stream:
        stream.until_done()

    # Debug output to check the type of response_text
    print(f"DEBUG: Final response_text type: {type(event_handler.response_text)}")
    print(f"DEBUG: Final response_text: {event_handler.response_text}")
import os
import asyncio
import re
from openai import OpenAI
from openai import AssistantEventHandler
import edge_tts
import tempfile

openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

# 1. Create assistant
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="You are a personal math tutor. Write and run code to answer math questions.",
    tools=[{"type": "code_interpreter"}],
    model="gpt-4o",
)

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
                self.initial_text_processed = True
            if isinstance(text, str):
                self.response_text += text
                self.accumulated_text += text
                print(text, end="", flush=True)
                # Trigger on punctuation excluding commas
                if re.search(r'[.;!?]', text):
                    asyncio.run(self.text_to_speech(self.accumulated_text))
                    self.accumulated_text = ""
            else:
                print(f"DEBUG: Non-string delta text: {text}")
                if isinstance(text, str):
                    self.response_text += text
                    self.accumulated_text += text
                    if re.search(r'[.;!?]', text):  # Trigger on punctuation excluding commas
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

        voice = "zh-CN-shaanxi-XiaoniNeural"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            output_file = temp_audio_file.name

        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                with open(output_file, "ab") as file:
                    file.write(chunk["data"])

        os.system(f"mpg123 {output_file}")

# Start the chat loop
while True:
    user_input = input("\nYou: ")

    if user_input.lower() in ['exit', 'quit']:
        print("Exiting the chat. Goodbye!")
        break

    # 2. Create thread
    thread = client.beta.threads.create()

    # 3. Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input
    )

    # 4. Create a Run and stream the response.
    event_handler = CustomEventHandler()
    with client.beta.threads.runs.stream(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Please address the user as Jane Doe. The user has a premium account.",
        event_handler=event_handler,
    ) as stream:
        stream.until_done()

    # Debug output to check the type of response_text
    print(f"DEBUG: Final response_text type: {type(event_handler.response_text)}")
    print(f"DEBUG: Final response_text: {event_handler.response_text}")
