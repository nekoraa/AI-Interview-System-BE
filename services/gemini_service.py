import json
import asyncio
import websockets
from typing import Callable, Optional
from core.config import settings


class GeminiLiveClient:
    def __init__(self, language: str, position: str, voice_name: str, send_to_frontend_cb: Callable):
        self.language = language
        self.position = position
        self.voice_name = voice_name
        self.send_to_frontend_cb = send_to_frontend_cb
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self.is_connected = False

    async def connect(self):
        ws_url = settings.GEMINI_WS_URL.format(api_key=settings.GEMINI_API_KEY)
        self.ws = await websockets.connect(ws_url)
        self.is_connected = True

        sys_instruction = (
            f"You are a professional technical interviewer interviewing a candidate for the '{self.position}' position. "
            f"Please conduct the interview in {self.language}. "
            "Ask one question at a time, wait for the user to answer, and provide brief feedback. Keep your responses conversational and concise."
        )

        setup_message = {
            "setup": {
                "model": f"models/{settings.MODEL_NAME}",
                "systemInstruction": {
                    "parts": [{"text": sys_instruction}]
                },
                "generationConfig": {
                    # 【修复点 1】: 添加 "TEXT" 模态，否则 AI 不会返回文本，只有声音
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.voice_name
                            }
                        }
                    }
                }
            }
        }
        await self.ws.send(json.dumps(setup_message))
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, base64_audio_data: str):
        if not self.is_connected or not self.ws:
            return

        # 【修复点 2】: 严格遵守 Gemini API 规范，使用 mediaChunks 数组
        audio_message = {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": base64_audio_data
                    }
                ]
            }
        }
        await self.ws.send(json.dumps(audio_message))

    async def _receive_loop(self):
        try:
            async for message in self.ws:
                response = json.loads(message)

                # 调试建议：取消注释下面这行可以查看完整的服务端返回
                print("Received from Gemini:", response)

                if "serverContent" in response:
                    server_content = response["serverContent"]

                    # 【修复点 3】: 处理服务端发出的“被打断”信号
                    # 当 VAD 识别到用户开始说话，Gemini 会中断当前输出，并发送 interrupted 标记
                    if server_content.get("interrupted"):
                        await self.send_to_frontend_cb({
                            "event": "interrupted",
                            "payload": {"message": "User started speaking, clear audio buffer."}
                        })
                        # 注意：前端收到这个 event 时，必须立即 stop() 并清空正在播放的音频队列！

                    # 解析 AI 返回的具体内容 (音频 + 文本)
                    model_turn = server_content.get("modelTurn", {})
                    if "parts" in model_turn:
                        for part in model_turn["parts"]:

                            # 1. 接收 AI 语音数据
                            if "inlineData" in part:
                                await self.send_to_frontend_cb({
                                    "event": "audio",
                                    "payload": {
                                        "data": part["inlineData"]["data"],
                                        "mimeType": "audio/pcm;rate=16000"
                                    }
                                })

                            # 2. 【修复点 4】: 接收 AI 的实时文本 (字幕)
                            # Gemini 不使用 outputTranscription，而是直接放在 part["text"] 中
                            elif "text" in part:
                                await self.send_to_frontend_cb({
                                    "event": "transcript",
                                    "payload": {"speaker": "ai", "text": part["text"]}
                                })

        except websockets.exceptions.ConnectionClosed:
            print("Gemini WebSocket connection closed.")
        except Exception as e:
            print(f"Error in Gemini receive loop: {e}")
        finally:
            self.is_connected = False

    async def close(self):
        self.is_connected = False
        if self._receive_task:
            self._receive_task.cancel()
        if self.ws:
            await self.ws.close()