import os
import json
from openai import OpenAI,AsyncOpenAI
from dotenv import load_dotenv
from functools import wraps
from . import prompt

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # 当前目录路径
load_dotenv(BASE_DIR / ".env")


API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")


client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
def analyse(propmt,query):
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
    try:
        data = analyse(prompt.idiom_inquire,idiom)
        print (data)
        data = json.loads(data)
        result = {'word':idiom ,**data}

        return result
    except Exception as e:
        print(f"error:{e}")

def inquire_words(words):
    data = analyse(prompt.idiom_inquire,words)
    data = json.loads(data)
    result = {'word':words ,**data}

    return result


if __name__ =="__main__":
    text =input("请输入要处理的词语:")
    print("开始分析")
    analyse(text)