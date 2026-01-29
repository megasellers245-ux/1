import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import json
from openai import OpenAI
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import *

# ================= 1. 配置信息 =================
# 填入你之前获得的真实信息
CONFIG = {
    "APP_ID": "cli_a9f1a525307a9cbd",
    "APP_SECRET": "TKhwibOVNhoEdyCrkCnWPdxZOjPka3Rf",
    "APP_TOKEN": "P0WpbMHLBa6zaQsyyvPcy2eqnuf",
    "TABLE_ID": "tbl0MFhSZr8yuIsk",
    "DEEPSEEK_API_KEY": "sk-6f3ff713536f45c0a6fc702ffa77eebf",
    "BASE_URL": "https://api.deepseek.com"
}

# 初始化 AI 客户端
client_ai = OpenAI(api_key=CONFIG["DEEPSEEK_API_KEY"], base_url=CONFIG["BASE_URL"])

# ================= 2. 核心逻辑函数 =================

def extract_pdf_text(uploaded_file):
    """提取 PDF 的全部文本内容"""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def ai_extract_parameters(text, keywords):
    """调用 DeepSeek 提取数据"""
    # 限制文本长度，防止超出 AI 处理极限
    safe_text = text[:40000] 
    
    prompt = f"""
    你是一个专业的电池/化学材料科研助手。
    请从以下提供的论文文本中，精准提取出指定参数的数值和单位。
    
    提取要求：
    1. 必须严格按照参数清单提取。
    2. 返回格式必须是纯 JSON，没有任何 Markdown 标识。
    3. 如果文中没有提到该参数，请返回 "N/A"。
    4. 字段名必须是中文参数名。
    
    参数清单：{", ".join(keywords)}
    
    论文文本：
    {safe_text} 
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
    sdk_client = Client.builder().app_id(CONFIG["APP_ID"]).app_secret(CONFIG["APP_SECRET"]).build()
    
    request = CreateAppTableRecordRequest.builder() \
        .app_token(CONFIG["APP_TOKEN"]) \
        .table_id(CONFIG["TABLE_ID"]) \
        .request_body(AppTableRecord.builder().fields(data_dict).build()) \
        .build()

    response = sdk_client.bitable.v1.app_table_record.create(request)
    return response.success()

# ================= 3. Streamlit 前端界面 =================

st.set_page_config(page_title="论文参数全自动提取器", layout="wide")
st.title("📚 论文参数全自动提取 & 飞书同步")

# 读取本地的关键词列表
try:
    # 确保 CSV 文件与此 app.py 在同一个文件夹
    keywords_df = pd.read_csv("参数关键字.xlsx - Sheet1.csv")
    keywords_list = keywords_df['参数（中文）'].tolist()
    st.sidebar.success(f"已加载 {len(keywords_list)} 个关键词")
except Exception as e:
    st.sidebar.error(f"读取 CSV 失败，请检查文件名或路径。错误: {e}")
    keywords_list = []

uploaded_files = st.file_uploader("上传论文 PDF", type="pdf", accept_multiple_files=True)

if st.button("开始提取并提交至飞书"):
    if not uploaded_files:
        st.warning("请先上传 PDF 文件")
    elif not keywords_list:
        st.error("关键词列表为空，请检查 CSV 文件")
    else:
        progress_bar = st.progress(0)
        for i, pdf_file in enumerate(uploaded_files):
            with st.status(f"正在处理: {pdf_file.name}...", expanded=True) as status:
                st.write("正在读取全文文本...")
                text = extract_pdf_text(pdf_file)
                
                st.write("AI 正在解析数据...")
                result = ai_extract_parameters(text, keywords_list)
                
                if result:
                    result["论文标题"] = pdf_file.name 
                    st.write("正在同步至飞书...")
                    success = upload_to_feishu(result)
                    
                    if success:
                        status.update(label=f"✅ {pdf_file.name} 已同步至飞书", state="complete")
                    else:
                        status.update(label=f"❌ {pdf_file.name} 同步飞书失败", state="error")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.balloons()
        st.success("全部任务完成！")
