import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from litellm import completion

MODEL = "ollama_chat/qwen2.5:3b"
API_BASE = "http://localhost:11434"


app = FastAPI()

class Prompt(BaseModel):
    prompt: str

@app.post("/generate")
def hello(prompt: Prompt):
    response = completion(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt.prompt}
        ],
        api_base=API_BASE,
        request_timeout=120,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
