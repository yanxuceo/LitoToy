import os
from openai import OpenAI

from typing_extensions import override
from openai import AssistantEventHandler


openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)


# Create assistant
assistant = client.beta.assistants.create(
    name="小小新",
    instructions="你扮演一个孩子的小伙伴，名字叫小小新，性格温和，说话可爱，对孩子充满爱心，经常赞赏和鼓励孩子，用5岁孩子容易理解语言提供有趣和创新的回答，回答不要超过50字。",
    model="gpt-3.5-turbo-0125",
)

# Create thread
thread = client.beta.threads.create()

print(assistant)
print(thread)
