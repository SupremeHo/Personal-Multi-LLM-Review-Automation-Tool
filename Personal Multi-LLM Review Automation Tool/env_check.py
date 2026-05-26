# Check if the required environment variables are set
# For Easy Debugging, check the key variables at the start of execution.

import os
import sys
from dotenv import load_dotenv

# This code checks if the required environment variables are set before proceeding with the rest of the application. It uses the python-dotenv library to load environment variables from a .env file, which is a common practice for managing sensitive information like API keys. If any required environment variable is missing, it prints an error message and exits the program.
load_dotenv()

# Define the required environment variables. In this case, we require the OPENAI_API_KEY to be set in the environment for the application to function properly.
REQUIRED = ["OPENAI_API_KEY"]
missing = [k for k in REQUIRED if not os.getenv(k)]

# If any required environment variable is missing, print an error message and exit the program. This helps ensure that the application has all the necessary configuration before it runs, preventing runtime errors related to missing configuration.
if missing:
    print("Environment Variable Missing:", missing)
    print(".env file is missing required variables. Please check .env.example for the required variables.")
    sys.exit(1)

# If all required environment variables are set, print a confirmation message. This indicates that the application is ready to proceed with its main functionality.
print("All environment variables are set.")

# I'm considering whether to create a function to overwrite existing values.
# load_dotenv() does not overwrite pre-set environment variables by default; when moving back and forth between development and operation keys, the old values may be maintained.
#load_dotenv(override=True) 
