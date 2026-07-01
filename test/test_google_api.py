import os

from openai import OpenAI

system_prompt = "You are a helpful assistant."
user_question = "Hello. I'm currently testing if the Google API works well in the terminal CLI environment. If you see this message, could you please create a short English sentence for the current date and time, with the phrase 'API connection successful!'?"


def generateChatGoogle(system_prompt, user_question):
    client = OpenAI(
        api_key=os.environ.get("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",  # the Google Gemini API endpoint
    )

    response = client.chat.completions.create(
        model="gemini-2.5-flash",  # Gemini model name
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
    )

    print(response.choices[0].message.content)


def main():
    generateChatGoogle(system_prompt, user_question)


if __name__ == "__main__":
    main()
