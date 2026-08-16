# Module for checking environment variables for application startup.

import os
import sys

# Credentials each provider accepts, in the order they are reported. Driven by one
# table so adding a provider is a single entry instead of three more parallel
# blocks. A provider is configured when ANY ONE of its variables is set - Anthropic
# lists two because its SDK honours either (see provider_anthropic._build_default_client).
CREDENTIAL_VARS = {
    "OpenAI": ["OPENAI_API_KEY"],
    "Anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
    "Google": ["GEMINI_API_KEY"],
}


def missing_environment_variables() -> dict[str, list[str]]:
    """
    Which credentials each provider is missing (an empty list = configured).

    One variable is enough, so the answer is all-or-nothing per provider: the list
    is either empty or names every variable that would have satisfied it. Calling
    ANTHROPIC_API_KEY missing while ANTHROPIC_AUTH_TOKEN is set would report a
    working provider as broken, since the client is built from either one.

    Kept apart from check_environment_variables() so the check can be exercised
    without driving that function's interactive prompt.

    Reads os.environ only. The .env fallback is already loaded by env.load_env()
    at package import - reading a .env here instead would report on an
    environment the providers never saw, since their clients are built first.
    """
    return {
        provider: [] if any(os.getenv(var) for var in variables) else list(variables)
        for provider, variables in CREDENTIAL_VARS.items()
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
            # " or ", not ", ": one of them is enough, and a comma-separated list
            # reads as a set of variables that all have to be set.
            sys.stderr.write(
                "Warning: Environment Variable Missing: "
                + " or ".join(missing_vars)
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
                for variables in CREDENTIAL_VARS.values():
                    show_key_values_4_chars(variables)
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


def show_key_values_4_chars(variables):
    """
    Show the last 4 characters of each of a provider's credential variables.
    """
    for env_var in variables:
        key_value = os.getenv(env_var)
        key_value_4_chars = key_value[-4:] if key_value else "(not set)"
        print(f"\n{env_var}: ...{key_value_4_chars}")
