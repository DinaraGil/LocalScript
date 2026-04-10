import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from litellm import completion

MODEL = "ollama_chat/codellama:7b"
API_BASE = "http://localhost:11434"
SYSTEM_PROMPT = '''
You are an AI agent that generates working Lua code from natural language tasks.

Understand the request and ask short clarifying questions if needed.
Produce correct, runnable Lua code and check it for obvious mistakes.
Help the user iteratively improve the solution.

Be concise. Avoid long explanations.
If information is missing, ask instead of guessing.
Use code blocks for Lua.
Explanations: 1 short sentence maximum.
'''
MAX_CONTEXT_LENGTH = 4096

app = FastAPI()

class Prompt(BaseModel):
    prompt: str

defaultContext = [
            { "role": "system", "content": SYSTEM_PROMPT },
]



contextLength = len(SYSTEM_PROMPT)

class Context:
    def __init__(self):
        self.contextLength = len(SYSTEM_PROMPT)
        self.contextMessages = [{ "role": "system", "content": SYSTEM_PROMPT }]
        self.defaultContext = [{ "role": "system", "content": SYSTEM_PROMPT }]
    


@app.post("/generate")
def hello(prompt: Prompt):
    ctx = Context()

    contextResetFlag = False

    promptLength = len(prompt.prompt)
    if ctx.contextLength + promptLength > MAX_CONTEXT_LENGTH:
        ctx.contextMessages = defaultContext
        ctx.contextLength = len(SYSTEM_PROMPT)
        contextResetFlag = True

    ctx.contextLength += promptLength
    ctx.contextMessages.append({ "role": "user", "content": prompt.prompt })
    response = completion(
        model=MODEL,
        messages=ctx.contextMessages,
        api_base = API_BASE,
        request_timeout = 120,
        options={
            "num_ctx": 4096, 
            "num_predict": 256,
            "batch": 1,
            "parallel": 1
        }
    )

    contextResponse = response.choices[0].message.content
    if contextResetFlag:
        contextResponse = "WARNING: CONTEXT HAS BEEN RESET\n\n" + contextResponse

    ctx.contextMessages.append({ "role": "assistant", "content": contextResponse})

    return contextResponse
    # return { prompt.prompt }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
