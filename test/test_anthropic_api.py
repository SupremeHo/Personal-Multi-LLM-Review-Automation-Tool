import os

from openai import OpenAI

system_prompt = "You are a helpful assistant."
user_question = "Hello. I'm currently testing if the Anthropic API works well in the terminal CLI environment. If you see this message, could you please create a short English sentence for the current date and time, with the phrase 'API connection successful!'?"


def generateChatAnthropic(system_prompt, user_question):
    client = OpenAI(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url="https://api.anthropic.com/v1/",  # the Claude API endpoint
    )

    response = client.chat.completions.create(
        model="claude-haiku-4-5",  # Claude model name
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
    )

    print(response.choices[0].message.content)


def main():
    generateChatAnthropic(system_prompt, user_question)


if __name__ == "__main__":
    main()
