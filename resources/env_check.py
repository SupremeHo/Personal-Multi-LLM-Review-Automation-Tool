# Module for checking environment variables for application startup.

import os
import sys

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    print("Error: 'python-dotenv' package is not installed.")
    print("Please run and install 'pipe install python-dotenv' on the terminal.")


def check_environment_variables():
    """
    Check OpenAI, Claude and Gemini API environment variables.
    """
    print("\nChecking environment variables...\n")

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
        sys.stderr.write(
            ".env file is missing OpenAI API's required variables. Please check .env.example for the required variables.\n"
        )
        sys.exit(1)
    if missing_vars_claude:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars_claude) + "\n")
        sys.stderr.write(
            ".env file is missing Anthropic API's required variables. Please check .env.example for the required variables.\n"
        )
        sys.exit(1)
    if missing_vars_gemini:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars_gemini) + "\n")
        sys.stderr.write(
            ".env file is missing Google API's required variables. Please check .env.example for the required variables.\n"
        )
        sys.exit(1)

    # 4) If all required environment variables are set, print a confirmation message.
    print("All environment variables are set.\n")

    # 5) Optionally, show the first 12 characters of APIs' required environment variables for verification (avoid printing the entire key for security reasons).
    while True:
        try:
            check_values = input(
                "Would you want to check the API values of the environment variables?\nIf yes, print the first 12 characters of the API key for verification (avoid printing the entire key for security reasons) (y/n): "
            ).lower()

            if check_values == "y":
                show_key_values_12_chars(REQUIRED_VARS_OPENAI)
                show_key_values_12_chars(REQUIRED_VARS_CLAUDE)
                show_key_values_12_chars(REQUIRED_VARS_GEMINI)
                break
            elif check_values == "n":
                print("\nSkipping validation for environment variables...\n")
                break
            else:
                print("\nPlease try to input correctly.\n")
                continue

        except EOFError as e:
            print(f"\n{e}. Please try to input correctly\n")
            continue


def show_key_values_12_chars(required_vars):
    """
    Show the first 12 characters of each required environment variable.
    """
    for env_var in required_vars:
        key_value_12_chars = os.getenv(env_var)[:12]
        print(f"\n{env_var}: {key_value_12_chars}")


# if __name__ == "__main__":
#     check_environment_variables()
