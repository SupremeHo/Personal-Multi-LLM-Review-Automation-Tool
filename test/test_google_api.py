from google import genai
from google.genai import types

system_prompt = "너는 내가 터미널 CLI에서 API를 호출하는 것을 도와주는 어시스턴트야."
user_question = "내가 만들고 있는 프로젝트가 있어. 여러 LLM을 불러와서 사용자의 질문에 대한 서로의 답변을 교차검증하는 시스템이지. 이번에 OpenAI API 호출하고 DB에 저장하는 것까지 했고, 이번엔 Anthropic과 Google API를 호출하는 기능을 만드는 중이라서 호출 방식을 통일하고 있는 중이야. 그건 그렇다 치고, LLM에게 적용된 정확한 시스템 프롬프트 문자열을 인식하여 사용자에게 그대로 보여줄 수는 없다고 하는데, API 보안 때문에 그런 것도 있을까?"

client = genai.Client()


def generateContent(system_prompt, user_question):
    content = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(system_instruction=system_prompt),
        contents=user_question,
    )

    print(content.text)


def interactionsAPI(system_prompt, user_question):
    interaction = client.interactions.create(
        model="gemini-2.5-flash",
        system_instruction=system_prompt,
        input=user_question,
    )

    print(interaction.output_text)


def main():
    generateContent(system_prompt, user_question)


if __name__ == "__main__":
    main()
