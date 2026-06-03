"""Module for checking environment variables for application startup."""

import os
import sys

from dotenv import load_dotenv


def check_environment_variables():
    print("Checking environment variables...\n")

    load_dotenv()  # 1) Load environment variables from a .env file into the application's environment using the load_dotenv function from the python-dotenv library.

    # 2) Define a list of required environment variables that the application needs to function properly.
    REQUIRED_VARS = ["OPENAI_API_KEY"]
    missing_vars = [env_var for env_var in REQUIRED_VARS if not os.getenv(env_var)]

    # 3) If any required environment variable is missing, print an error message and exit the program.
    if missing_vars:
        sys.stderr.write(
            "Environment Variable Missing: " + ", ".join(missing_vars) + "\n"
        )
        sys.stderr.write(
            ".env file is missing required variables.Please check .env.example for the required variables.\n"
        )
        sys.exit(1)

    print(
        "All environment variables are set.\n"
    )  # 4) If all required environment variables are set, print a confirmation message.

    show_key_values_16_chars(
        REQUIRED_VARS
    )  # 5) Optionally, show the first 16 characters of each required environment variable for verification (avoid printing the entire key for security reasons).


def show_key_values_16_chars(required_vars):
    """
    Show the first 16 characters of each required environment variable.
    """

    check_values = (
        input(
            "Would you want to check the values of the environment variables? (Print the first 16 characters of the API key for verification (avoid printing the entire key for security reasons)) (y/n): "
        ).lower()
        == "y"
    )

    if check_values:
        for env_var in required_vars:
            key_value_16_chars = os.getenv(env_var)[:16]
            print(f"{env_var}: {key_value_16_chars}" + "\n")
    else:
        print("\nSkipping validation for environment variables...\n")
