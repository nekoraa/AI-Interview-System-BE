import uvicorn
from fastapi import FastAPI
from api.ws_interview import router as interview_router

app = FastAPI(title="AI Interviewer API", description="WebSocket Backend for AI Interview with Gemini Live API")

# 注册 WebSocket 路由
app.include_router(interview_router)

@app.get("/")
async def health_check():
    return {"status": "Running", "service": "AI Interviewer Backend"}

if __name__ == "__main__":
    # 使用 Uvicorn 运行服务
    # host 设为 0.0.0.0 以允许外部访问，端口 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)