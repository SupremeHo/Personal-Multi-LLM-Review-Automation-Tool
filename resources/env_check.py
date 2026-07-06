# Module for checking environment variables for application startup.

import os
import sys

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    print("Error Message: 'python-dotenv' package is not installed.")
    print("Please run and install 'pip install python-dotenv' on the terminal.")
    sys.exit(1)


def check_environment_variables():
    """
    Check OpenAI, Claude and Gemini API environment variables.
    """
    print("\nChecking environment variables...\n")

    load_dotenv()  # 1) Load environment variables from a .env file into the application's environment using the load_dotenv function from the python-dotenv library.

    # 2) Required environment variables per provider. Driven by one table so adding
    #    a provider is a single entry instead of three more parallel blocks.
    REQUIRED_VARS = {
        "OpenAI": ["OPENAI_API_KEY"],
        "Anthropic": ["ANTHROPIC_API_KEY"],
        "Google": ["GEMINI_API_KEY"],
    }

    missing_by_provider = {
        provider: [env_var for env_var in keys if not os.getenv(env_var)]
        for provider, keys in REQUIRED_VARS.items()
    }

    # 3) Providers are optional (each provider_*.py sets its client to None instead of
    # failing when its key is missing), so warn about missing keys instead of exiting.
    for provider, missing_vars in missing_by_provider.items():
        if missing_vars:
            sys.stderr.write(
                "Warning: Environment Variable Missing: "
                + ", ".join(missing_vars)
                + "\n"
            )
            sys.stderr.write(
                f".env file is missing {provider} API's required variables. Please check .env.example for the required variables.\n"
            )

    # 4) If all required environment variables are set, print a confirmation message.
    if not any(missing_by_provider.values()):
        print("All environment variables are set.\n")

    # 5) Optionally, show the first 12 characters of APIs' required environment variables for verification (avoid printing the entire key for security reasons).
    while True:
        try:
            check_values = input(
                "Would you want to check the API values of the environment variables?\nIf yes, print the first 12 characters of the API key for verification (avoid printing the entire key for security reasons) (y/n): "
            ).lower()

            if check_values == "y":
                for keys in REQUIRED_VARS.values():
                    show_key_values_12_chars(keys)
                break
            elif check_values == "n":
                print("\nSkipping validation for environment variables...\n")
                break
            else:
                print("\nPlease try to input correctly.\n")
                continue
        except EOFError:
            sys.exit("Error Message: Read beyond end of file. Exit the program.")


def show_key_values_12_chars(required_vars):
    """
    Show the first 12 characters of each required environment variable.
    """
    for env_var in required_vars:
        key_value = os.getenv(env_var)
        key_value_12_chars = key_value[:12] if key_value else "(not set)"
        print(f"\n{env_var}: {key_value_12_chars}")
