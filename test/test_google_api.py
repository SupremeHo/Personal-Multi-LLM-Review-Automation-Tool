from google import genai
from google.genai import types

client = genai.Client()

system_prompt = "You are a helpful assistant."
user_question = "Hello. I'm currently testing if the Google API works well in the terminal CLI environment. If you see this message, could you please create a short English sentence for the current date and time, with the phrase 'API connection successful!'?"


def generateContent(system_prompt, user_question):
    content = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(system_instruction=system_prompt),
        contents=user_question,
    )

    print(content.text)


def main():
    generateContent(system_prompt, user_question)


if __name__ == "__main__":
    main()
