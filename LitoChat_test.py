import os
import asyncio
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

    def on_text_created(self, text) -> None:
        print(f"\nassistant(t_c) > ", end="", flush=True)
        self.response_text = text

    def on_text_delta(self, delta, snapshot):
        # Extract the text content from delta
        print(f"DEBUG: Received delta: {delta}")
        text = getattr(delta, 'text', None)
        if text:
            print(f"DEBUG: Delta text type: {type(text)}")
            if isinstance(text, str):
                self.response_text += text
                print(text, end="", flush=True)
            else:
                print(f"DEBUG: Non-string delta text: {text}")

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

async def text_to_speech(text):
    """Convert text to speech and play the audio."""
    voice = "en-GB-SoniaNeural"
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
        output_file = temp_audio_file.name

    communicate = edge_tts.Communicate(text, voice)
    async with communicate.stream() as stream:
        with open(output_file, "wb") as file:
            async for chunk in stream:
                if chunk["type"] == "audio":
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

    # Convert the assistant's response to speech
    asyncio.run(text_to_speech(event_handler.response_text))
