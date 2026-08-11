# Module for checking environment variables for application startup.

import os
import sys

# Required environment variables per provider. Driven by one table so adding a
# provider is a single entry instead of three more parallel blocks.
REQUIRED_VARS = {
    "OpenAI": ["OPENAI_API_KEY"],
    "Anthropic": ["ANTHROPIC_API_KEY"],
    "Google": ["GEMINI_API_KEY"],
}


def missing_environment_variables() -> dict[str, list[str]]:
    """
    Which required variables each provider is missing (an empty list = all set).

    Kept apart from check_environment_variables() so the check can be exercised
    without driving that function's interactive prompt.

    Reads os.environ only. The .env fallback is already loaded by env.load_env()
    at package import - reading a .env here instead would report on an
    environment the providers never saw, since their clients are built first.
    """
    return {
        provider: [env_var for env_var in keys if not os.getenv(env_var)]
        for provider, keys in REQUIRED_VARS.items()
    }


def check_environment_variables():
    """
    Report which OpenAI, Claude and Gemini API keys are missing, then optionally
    show the tail of each one.

    Missing keys are warnings and the exit status stays 0: a missing key disables
    one provider rather than the tool (see each provider_*.py), so a non-zero exit
    would call a supported single-provider setup a failure.
    """
    print("\nChecking environment variables...\n")

    missing_by_provider = missing_environment_variables()

    # 1) Providers are optional (each provider_*.py sets its client to None instead of
    # failing when its key is missing), so warn about missing keys instead of exiting.
    for provider, missing_vars in missing_by_provider.items():
        if missing_vars:
            sys.stderr.write(
                "Warning: Environment Variable Missing: "
                + ", ".join(missing_vars)
                + "\n"
            )
            # Name both sources: the OS environment is the recommended one and
            # wins over .env, so pointing only at .env sends anyone following the
            # README to the file that does not decide this.
            sys.stderr.write(
                f"{provider} stays disabled until it is set. Provide it as an OS "
                "environment variable (recommended), or in .env - see .env.example.\n"
            )

    # 2) If all required environment variables are set, print a confirmation message.
    if not any(missing_by_provider.values()):
        print("All environment variables are set.\n")

    # 3) Optionally, show the last 4 characters of APIs' required environment variables for verification (avoid printing the entire key for security reasons).
    while True:
        try:
            check_values = input(
                "Would you want to check the API values of the environment variables?\nIf yes, print the last 4 characters of the API key for verification (avoid printing the entire key for security reasons) (y/n): "
            ).lower()

            if check_values == "y":
                for keys in REQUIRED_VARS.values():
                    show_key_values_4_chars(keys)
                break
            elif check_values == "n":
                print("\nSkipping validation for environment variables...\n")
                break
            else:
                print("\nPlease try to input correctly.\n")
                continue
        except EOFError:
            sys.exit("Error Message: Read beyond end of file. Exit the program.")

        except KeyboardInterrupt:
            # Ctrl+C at this prompt used to end the command on a traceback, while
            # the same prompt in list_models.py exited cleanly.
            sys.exit("Error Message: Program interrupted by user. Exit the program.")


def show_key_values_4_chars(required_vars):
    """
    Show the last 4 characters of each required environment variable.
    """
    for env_var in required_vars:
        key_value = os.getenv(env_var)
        key_value_4_chars = key_value[-4:] if key_value else "(not set)"
        print(f"\n{env_var}: ...{key_value_4_chars}")
