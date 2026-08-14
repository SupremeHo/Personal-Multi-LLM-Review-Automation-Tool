"""Personal Multi-LLM Review Automation Tool"""

from resources.env import load_env

__version__ = "0.1.925"

# Runs before any resources.* submodule is imported, so the .env fallback is in
# os.environ before the provider modules construct their SDK clients at import
# time. Moving this into a command body reintroduces that ordering bug.
load_env()
