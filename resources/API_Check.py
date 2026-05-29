# from anthropic import Anthropic
# from google import genai

# client_claude = Anthropic()
# client_gemini = genai.Client()

# def list_available_models_claude(client_claude: Anthropic):
#     if input("Do you want to list the Claude API's available models? (y/n): ").lower() == "y":
#         models = client_claude.models.list()
#         print("\n" + "======== Available Claude Models ========")
#         for model in models:
#             if 'claude' in model.id:
#                 print(model.id)
#         print("======== End of Claude Models ========\n")
#     else:
#         print("\nSkipping model listing...\n")

# def list_available_models_gemini(client_gemini: genai.Client):
#     if input("Do you want to list the Gemini API's all available models? (y/n): ").lower() == "y":
#         models = client_gemini.models.list()
#         print("\n" + "======== Available Gemini Models ========")
#         for model in models:
#             if 'gemini' in model.name:
#                 print(model.name)
#         print("======== End of Gemini Models ========\n")
#     else:
#         print("\nSkipping model listing...\n")

# message_claude = client_claude.messages.create(
#     model = "claude-haiku-4-5-20251001",
#     max_tokens = 256,
#     messages = [
#         {"role": "user", "content": "Hello, Claude. I'm testing the Claude API. Can you tell me about yourself?"}
#     ]
# )

# message_gemini = client_gemini.models.generate_content(
#     model = "gemini-2.5-flash",
#     contents = [
#         {"Hello, Gemini. I'm testing the Gemini API. Can you tell me about yourself?"}
#     ]
# )

# print(message_claude.content)
# print(message_gemini.text)

# #messages = client_claude.chat.creates()

