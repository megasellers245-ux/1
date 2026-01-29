import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import json
import time
from openai import OpenAI
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import *

# ================= 1. 配置信息 =================
# 飞书配置 (根据你提供的信息)
APP_ID = "cli_a9f1a525307a9cbd"
APP_SECRET = "TKhwibOVNhoEdyCrkCnWPdxZOjPka3Rf"
APP_TOKEN = "P0WpbMHLBa6zaQsyyvPcy2eqnuf" 
# 【需修改】请填入你通过“复制数据表ID”获取到的 tbl... 开头的字符串
TABLE_ID = "tbl0MFhSZr8yuIsk" 

# AI 配置 (DeepSeek 方案)
# 【需修改】请填入你在 DeepSeek 官网申请到的 sk-xxxxxx
DEEPSEEK_API_KEY = "sk-6f3ff713536f45c0a6fc702ffa77eebf"

client_ai = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ================= 2. 核心逻辑函数 =================

def extract_pdf_text(uploaded_file):
    """提取 PDF 文本"""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    # 通常论文的前 3-4 页包含了大部分关键参数，限制长度提高响应速度
    for page in doc[:5]: 
        text += page.get_text()
    return text

def ai_extract_parameters(text, keywords):
    """调用 DeepSeek 提取数据"""
    prompt = f"""
    你是一个专业的电池/化学材料科研助手。
    请从以下提供的论文文本中，提取出指定参数的数值和单位。
    
    提取要求：
    1. 必须严格按照参数清单提取。
    2. 返回格式必须是纯 JSON，没有任何 Markdown 标识。
    3. 如果文中没有提到该参数，请返回 "N/A"。
    4. 字段名必须是中文参数名。
    
    参数清单：{", ".join(keywords)}
    
    论文文本：
    {text[:8000]} 
    """
    
    try:
        response = client_ai.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI 提取出错: {e}")
        return None

def upload_to_feishu(data_dict):
    """将结果写入飞书多维表格"""
    sdk_client = Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
    
    # 构造飞书的写入格式
    # 注意：确保飞书表格中的列名与 data_dict 的 Key 完全一致
    request = CreateAppTableRecordRequest.builder() \
        .app_token(APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(AppTableRecord.builder().fields(data_dict).build()) \
        .build()

    response = sdk_client.bitable.v1.app_table_record.create(request)
    return response.success()

# ================= 3. Streamlit 前端界面 =================

st.set_page_config(page_title="论文参数全自动提取器", layout="wide")
st.title("📚 论文参数全自动提取 & 飞书同步")

# 读取本地的关键词列表
try:
    keywords_df = pd.read_csv("参数关键字.xlsx - Sheet1.csv")
    keywords_list = keywords_df['参数（中文）'].tolist()
    st.sidebar.success(f"已加载 {len(keywords_list)} 个关键词")
except:
    st.sidebar.error("请确保 '参数关键字.xlsx - Sheet1.csv' 文件在脚本同目录下")
    keywords_list = []

uploaded_files = st.file_uploader("上传论文 PDF (支持批量拖入)", type="pdf", accept_multiple_files=True)

if st.button("开始提取并提交至飞书"):
    if not uploaded_files:
        st.warning("请先上传 PDF 文件")
    elif not keywords_list:
        st.error("关键词列表为空")
    else:
        progress_bar = st.progress(0)
        for i, pdf_file in enumerate(uploaded_files):
            with st.status(f"正在处理: {pdf_file.name}...", expanded=True) as status:
                # 1. 提取文本
                st.write("正在读取文本...")
                text = extract_pdf_text(pdf_file)
                
                # 2. AI 提取
                st.write("AI 正在深度解析关键词数据...")
                result = ai_extract_parameters(text, keywords_list)
                
                if result:
                    # 添加文件名作为记录名
                    result["论文标题"] = pdf_file.name 
                    
                    # 3. 提交飞书
                    st.write("正在将数据写入飞书多维表格...")
                    success = upload_to_feishu(result)
                    
                    if success:
                        status.update(label=f"✅ {pdf_file.name} 已同步至飞书", state="complete")
                    else:
                        status.update(label=f"❌ {pdf_file.name} 同步飞书失败", state="error")
                
                # 更新进度条
                progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.balloons()
        st.success("所有任务已完成！请检查你的飞书多维表格。")
