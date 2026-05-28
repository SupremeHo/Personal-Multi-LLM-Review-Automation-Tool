# Environment variable check for application startup

import os
import sys
from dotenv import load_dotenv

print("Checking environment variables...\n")

def check_environment_variables():
    # 1) Load environment variables from .env file.
    load_dotenv()

    # 2) Define a list of required environment variables that the application needs to function properly. In this case, it includes "OPENAI_API_KEY", which is likely necessary for making API calls to OpenAI's services.
    REQUIRED_VARS = ["OPENAI_API_KEY"]
    missing_vars = [env_var for env_var in REQUIRED_VARS if not os.getenv(env_var)]

    # 3) If any required environment variable is missing, print an error message and exit the program. This helps ensure that the application has all the necessary configuration before it runs, preventing runtime errors related to missing configuration.
    if missing_vars:
        sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars) + "\n")
        sys.stderr.write(".env file is missing required variables. Please check .env.example for the required variables.\n")
        sys.exit(1)

    # 4) If all required environment variables are set, print a confirmation message. This indicates that the application is ready to proceed with its main functionality.
    print("All environment variables are set.\n")

    # 5) If the user chooses to check the values of the environment variables, print the first 16 characters of each required environment variable. This allows the user to verify that the correct values have been loaded without exposing sensitive information like API keys.
    check_values = input("Would you want to check the values of the environment variables? (Print the first 16 characters of the API key for verification (avoid printing the entire key for security reasons)) (y/n): ").lower() == "y"

    if check_values:
        for env_var in REQUIRED_VARS:
            key_value_16_chars = os.getenv(env_var)[:16]
            print(f"{env_var}: {key_value_16_chars}" + "\n")
    else:
        print("\nSkipping environment variable value check...\n")

# I'm considering whether to create a function to overwrite existing values.
#load_dotenv(override=True) 
