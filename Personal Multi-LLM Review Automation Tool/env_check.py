# Environment variable check for application startup

import os
import sys
from dotenv import load_dotenv

# This code checks if the required environment variables are set before proceeding with the rest of the application. It uses the python-dotenv library to load environment variables from a .env file, which is a common practice for managing sensitive information like API keys. If any required environment variable is missing, it prints an error message and exits the program.
load_dotenv()

# Define the required environment variables. In this case, we require the OPENAI_API_KEY to be set in the environment for the application to function properly.
REQUIRED_VARS = ["OPENAI_API_KEY"]
missing_vars = [env_var for env_var in REQUIRED_VARS if not os.getenv(env_var)]

# If any required environment variable is missing, print an error message and exit the program. This helps ensure that the application has all the necessary configuration before it runs, preventing runtime errors related to missing configuration.
if missing_vars:
    sys.stderr.write("Environment Variable Missing: " + ", ".join(missing_vars) + "\n")
    sys.stderr.write(".env file is missing required variables. Please check .env.example for the required variables.\n")
    sys.exit(1)

# If all required environment variables are set, print a confirmation message. This indicates that the application is ready to proceed with its main functionality.
print("All environment variables are set.\n")
response = input("Would you want to check the values of the environment variables? (Print the first 16 characters of the API key for verification (avoid printing the entire key for security reasons)) (y/n): ")

# If the user chooses to check the values of the environment variables, print the first 16 characters of each required environment variable. This allows the user to verify that the correct values have been loaded without exposing sensitive information like API keys.
if response.lower() == "y":
    for env_var in REQUIRED_VARS:
        key_value_16_chars = os.getenv(env_var)[:16]
        print(f"{env_var}: {key_value_16_chars}")

# I'm considering whether to create a function to overwrite existing values.
#load_dotenv(override=True) 
