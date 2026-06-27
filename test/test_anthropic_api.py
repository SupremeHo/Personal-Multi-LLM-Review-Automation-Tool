from anthropic import Anthropic

client = Anthropic()

system_prompt = "You are a helpful assistant."
user_question = "Hello. I'm currently testing if the Anthropic API works well in the terminal CLI environment. If you see this message, could you please create a short English sentence for the current date and time, with the phrase 'API connection successful!'?"


def createMessage(system_prompt, user_question):
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_question}],
    )

    print(message.content[0].text)


def main():
    createMessage(system_prompt, user_question)


if __name__ == "__main__":
    main()
