import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from . import prompt

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # 当前目录路径
load_dotenv(BASE_DIR / ".env")


API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")


client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def _parse_json_object(content):
    text = (content or "").strip()
    if not text:
        raise ValueError("AI returned empty response")

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            raise ValueError("AI response must be a JSON object")
        return value

    raise ValueError("AI response did not contain a JSON object")


def analyse(propmt, query):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": propmt},
            {"role": "user", "content": query},
        ],
        stream=False
    )
    result = response.choices[0].message.content
    # print(result)
    return result


def inquire_idiom(idiom):
    data = analyse(prompt.idiom_inquire, idiom)
    data = _parse_json_object(data)
    result = {"word": idiom, **data}

    return result


def inquire_words(words):
    data = analyse(prompt.words_inquire, words)
    data = _parse_json_object(data)
    result = {"word": words, **data}

    return result


if __name__ =="__main__":
    text =input("请输入要处理的词语:")
    print("开始分析")
    analyse(text)
