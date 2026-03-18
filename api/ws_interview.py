import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.gemini_service import GeminiLiveClient

router = APIRouter()


@router.websocket("/ws/interview")
async def interview_endpoint(websocket: WebSocket):
    await websocket.accept()

    gemini_client = None
    is_paused = False  # 面试暂停状态标志

    # 定义回调：将数据从 Gemini 推送给前端
    async def send_to_frontend(data: dict):
        try:
            await websocket.send_text(json.dumps(data))
        except RuntimeError:
            pass  # 捕获连接已断开的异常

    try:
        while True:
            # 接收前端消息
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            action = msg.get("action")
            payload = msg.get("payload", {})

            # 1. 初始化面试
            if action == "start":
                language = payload.get("language", "中文")
                position = payload.get("position", "前端开发工程师")
                voice_name = payload.get("voice", "Aoede")

                # 实例化并连接 Gemini
                gemini_client = GeminiLiveClient(
                    language=language,
                    position=position,
                    voice_name=voice_name,
                    send_to_frontend_cb=send_to_frontend
                )

                # ====== 新增错误捕获 ======
                try:
                    await gemini_client.connect()
                    # 通知前端 AI 已准备就绪
                    await send_to_frontend({
                        "event": "status",
                        "payload": {
                            "code": 200,
                            "status": "ready",
                            "message": "面试初始化成功，AI已准备好"
                        }
                    })
                except Exception as e:
                    print(f"连接 Gemini 失败: {e}")
                    await send_to_frontend({
                        "event": "status",
                        "payload": {
                            "code": 500,
                            "status": "error",
                            "message": f"连接 Google AI 失败: {str(e)}"
                        }
                    })
                # =========================
                await gemini_client.connect()

                # 通知前端 AI 已准备就绪
                await send_to_frontend({
                    "event": "status",
                    "payload": {
                        "code": 200,
                        "status": "ready",
                        "message": "面试初始化成功，AI已准备好"
                    }
                })

            # 2. 接收并转发实时音频片段
            elif action == "audio":
                if is_paused:
                    continue  # 暂停状态下丢弃前端音频包

                if gemini_client and gemini_client.is_connected:
                    audio_b64 = payload.get("data")
                    if audio_b64:
                        await gemini_client.send_audio(audio_b64)

            # 3. 流程控制指令
            elif action == "control":
                command = payload.get("command")
                if command == "pause":
                    is_paused = True
                    await send_to_frontend(
                        {"event": "status", "payload": {"status": "paused", "message": "面试已暂停"}})

                elif command == "resume":
                    is_paused = False
                    await send_to_frontend({"event": "status", "payload": {"status": "ready", "message": "面试已恢复"}})

                elif command == "end":
                    # 向前端发送结束状态，后续进行清理
                    await send_to_frontend(
                        {"event": "status", "payload": {"status": "ended", "message": "面试已结束，正在生成报告..."}})
                    break  # 退出循环，关闭连接

            else:
                print(f"Unknown action received: {action}")

    except WebSocketDisconnect:
        print("Frontend client disconnected.")
    except Exception as e:
        print(f"Error handling websocket: {e}")
        await send_to_frontend({
            "event": "status",
            "payload": {"code": 500, "status": "error", "message": str(e)}
        })
    finally:
        # 清理工作：关闭与 Gemini 的连接
        if gemini_client:
            await gemini_client.close()

        # 尝试安全关闭前端 WebSocket
        try:
            await websocket.close()
        except Exception:
            pass