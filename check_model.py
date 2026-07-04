"""사용 가능한 Gemini 모델 목록 출력"""
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

client = genai.Client(api_key=api_key)

# generateContent 지원 모델 목록 출력
for model in client.models.list():
    actions = model.supported_actions or []
    if "generateContent" in actions:
        print(model.name)
