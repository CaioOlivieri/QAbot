import os

from dotenv import load_dotenv
from google import genai


def main() -> int:
    load_dotenv(".env.keys")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Responda apenas: API funcionando.",
    )
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
