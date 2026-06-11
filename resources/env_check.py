# Module for checking environment variables for application startup.

import os
import sys

from dotenv import load_dotenv


def check_environment_variables():
    """
    Check OpenAI, Claude and Gemini API environment variables.
    """
    print("Checking environment variables...\n")

    load_dotenv()  # 1) Load environment variables from a .env file into the application's environment using the load_dotenv function from the python-dotenv library.

    # 2) Define a list of required environment variables that the application needs to function properly.
    REQUIRED_VARS_OPENAI = ["OPENAI_API_KEY"]
    REQUIRED_VARS_CLAUDE = ["ANTHROPIC_API_KEY"]
    REQUIRED_VARS_GEMINI = ["GEMINI_API_KEY"]

    missing_vars_openai = [env_var for env_var in REQUIRED_VARS_OPENAI if not os.getenv(env_var)]
    missing_vars_claude = [env_var for env_var in REQUIRED_VARS_CLAUDE if not os.getenv(env_var)]
    missing_vars_gemini = [env_var for env_var in REQUIRED_VARS_GEMINI if not os.getenv(env_var)]

    # 3) If any required environment variable is missing, print an error message and exit the program.
    if missing_vars_openai:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars_openai) + "\n")
        sys.stderr.write(".env file is missing required variables. Please check .env.example for the required variables.\n")
        sys.exit(1)
    if missing_vars_claude:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars_claude) + "\n")
        sys.stderr.write(".env file is missing required variables. Please check .env.example for the required variables.\n")
        sys.exit(1)
    if missing_vars_gemini:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars_gemini) + "\n")
        sys.stderr.write(".env file is missing required variables. Please check .env.example for the required variables.\n")
        sys.exit(1)

    # 4) If all required environment variables are set, print a confirmation message.
    print("All environment variables are set.\n")

    # 5) Optionally, show the first 12 characters of APIs' required environment variables for verification (avoid printing the entire key for security reasons).
    check_values = (
        input(
            "Would you want to check the API values of the environment variables?\n(Print the first 12 characters of the API key for verification (avoid printing the entire key for security reasons)) (y/n): "
        ).lower()
        == "y"
    )

    if check_values:
        show_key_values_12_chars(REQUIRED_VARS_OPENAI)
        show_key_values_12_chars(REQUIRED_VARS_CLAUDE)
        show_key_values_12_chars(REQUIRED_VARS_GEMINI)
    else:
        print("\nSkipping validation for environment variables...\n")


def show_key_values_12_chars(required_vars):
    """
    Show the first 12 characters of each required environment variable.
    """
    for env_var in required_vars:
        key_value_12_chars = os.getenv(env_var)[:12]
        print(f"\n{env_var}: {key_value_12_chars}")
