import code
import os
import json
from datetime import datetime
from json import JSONEncoder
from urllib.request import Request

import uvicorn
from typing import Any
from fastapi import FastAPI
from openai import OpenAI
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel
import logging  # 日志

logging.basicConfig(
    level=logging.INFO,
    format = "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="汉字迷盒")
# 挂载静态文件的存放目录
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_file(session_id):
    return f"sessions/{session_id}.json"

def generate_session_id():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

system_prompt="你是一个游戏机器人，接下来我会和你进行猜字谜游戏，答对夸奖并且问我要不要再来，答错给我答案的小提示，每次题目必须随机且不重复"

client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")

# 1 创建会话目录
if not os.path.exists("sessions"):
    os.mkdir("sessions")


@app.get("/")
def  root():
    logging.info("访问项目主页")
    return FileResponse("./static/index.html")

class ApiResponse(BaseModel):# api返回给客户端
    code: int
    message: str
    data:Any

# 接受前端传递的json格式{}
class ChatRequest(BaseModel):
    session_id: str
    message: str


#----------------------------------------------------------------------
@app.post("/api/sessions")
def create_session()->ApiResponse:
    logging.info("创建会话")
    session_id = generate_session_id()
    session_data={
        "current_session":session_id,
        "message":[]

    }
    with open("sessions/"+session_id+".json",'w',encoding="utf-8") as f:
        json.dump(session_data,f,ensure_ascii=False,indent=2)

    # return数据
    return ApiResponse(code=200,message="创建会话成功",data=session_id)
    #             编码     返回给前端的提示       数据

@app.post("/api/chat")
def chat(request:ChatRequest):
    logging.info(f"与ai交互：{request.session_id}：{request.message}")  # 前端传递的数据
    #{"session_id":"2026-10-25_18-39-57","message":"不知道"}

    # 1 加载消息列表
    session_path = get_file(request.session_id) # 获取文件名
    with open(session_path,"r",encoding="utf-8") as f:
        session_data = json.load(f)
    logging.info("------->上次数据加载完成")
    # 2 与ai交互数据
    messages = [{"role": "system", "content":system_prompt}]
    # messages -->整合内容发给ai
    for data in session_data["message"]:
        messages.append(data)
        logging.info(f"输出上次数据{data}，拼接到会话列表\n")
    messages.append({"role": "user", "content":request.message})#拼接上用户最新请求的数据

    # 3获取响应数据，调用ai
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
        temperature=1.5 # ai创造性
    )
    ai_response = response.choices[0].message.content
    logging.info(f"ai的回应：{ai_response}\n")

    # 4 更新message
    messages.append({"role":"assistant","content":ai_response})

    # 5 message -->保存至json(session_data)
    messages.remove({"role": "system", "content":system_prompt})
    session_data["message"]=messages

    """
    # 把用户这次发的消息，按照格式追加到 session_data 里
    session_data["message"].append({"role": "user", "content": request.message})
    # 把 AI 这次回复的消息，追加到 session_data 里
    session_data["message"].append({"role": "assistant", "content": ai_response})
    """
    with open(session_path,"w",encoding="utf-8") as f:
        json.dump(session_data,f,ensure_ascii=False,indent=2)
    logging.info("----------------------写入json完成")

    return ApiResponse(code=200,message="请求成功",data=ai_response)


@app.get("/api/sessions")
def get_sessions()->ApiResponse:
    logging.info("加载会话列表")
    # 查看seesion下所有文件 返回列表
    session_files = os.listdir("sessions")
    session_ids = [file[:-5]for file in session_files]
    session_id = session_ids[::-1]# 倒序

    return ApiResponse(code=200,message="会话列表创建成功",data=session_id)

@app.get("/api/sessions/{session_id}")  # 路径参数
def get_message(session_id:str)->ApiResponse:
    logging.info(f"获取{session_id}会话信息")

    session_file = get_file(session_id)
    with open(session_file,"r",encoding="utf-8") as f:
        session_data = json.load(f)

    return ApiResponse(code=200,message="会话展示成功",data=session_data)

@app.delete("/api/sessions/{session_id}")
def delete_message(session_id:str)->ApiResponse:
    logging.info(f"删除{session_id}")

    session_file = get_file(session_id)
    os.remove(session_file)


    return ApiResponse(code=200,message="会话删除成功",data=None)

# 异常处理器
@app.exception_handler(Exception) #捕获所有异常
def exception_handler(request: Request, exc: Exception):  # 哪部分错，错什么
    logging.error(f"异常路径：{request.full_url}错误：{exc}")
    return JSONResponse(content={code:500,"message":"对不起，我又写错了。。。","data":None})




















if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0",port=8000)