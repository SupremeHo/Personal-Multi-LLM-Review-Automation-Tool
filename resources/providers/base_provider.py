# This module abstracts and defines only the common protocols of providers offering APIs that allow LLM to be called, such as OpenAI, Anthropic, and Google.
# API differences for each provider are not defined here; instead, each 'provider_*name*.py' absorbs API differences and returns them to LLMCallResult.
