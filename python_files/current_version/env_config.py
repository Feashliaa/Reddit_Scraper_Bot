from dotenv import load_dotenv
import os
import logging
import sys
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential


def load_env_variables():
    load_dotenv()
    return {
        "REDDIT_CLIENT_ID": os.getenv("REDDIT_CLIENT_ID"),
        "REDDIT_CLIENT_SECRET": os.getenv("REDDIT_CLIENT_SECRET"),
        "REDDIT_USER_AGENT": os.getenv("REDDIT_USER_AGENT"),
        "REDDIT_USERNAME": os.getenv("REDDIT_USERNAME"),
        "REDDIT_PASSWORD": os.getenv("REDDIT_PASSWORD"),
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "WEBHOOK": os.getenv("WEBHOOK")
    }
