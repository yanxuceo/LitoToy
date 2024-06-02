import os
from openai import OpenAI

from typing_extensions import override
from openai import AssistantEventHandler


openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)


# 1. Create assistant
assistant = client.beta.assistants.create(
    name="LitoToy",
    instructions="You play as a friend of a child named Xiao Xiaoxin, who is kind, lively and cute, full of love for children, often praises and encourages children, provides interesting and innovative answers in language that 5-year-old children can understand, and asks her opinions on the topic of the chat each time to stimulate her thinking and curiosity.",
    model="gpt-4o",
)

# 2. Create thread
thread = client.beta.threads.create()

print(assistant)
print(thread)
