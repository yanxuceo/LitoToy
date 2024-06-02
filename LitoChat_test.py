import os
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler

openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

# 1. Create assistant
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="You are a personal math tutor. Write and run code to answer math questions.",
    tools=[{"type": "code_interpreter"}],
    model="gpt-4o",
)

# Define the EventHandler class to handle the events in the response stream.
class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant(t_c) > ", end="", flush=True)

    @override
    def on_text_delta(self, delta, snapshot):
        # Streaming output
        print(delta.value, end="", flush=True)

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
    with client.beta.threads.runs.stream(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Please address the user as Jane Doe. The user has a premium account.",
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()
