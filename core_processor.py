import fitz  # PyMuPDF
import pandas as pd
import json
from openai import OpenAI
from lark_oapi import Client
from lark_oapi.api.bitable.v1 import *

# ================= 配置信息 =================
# 建议将密钥统一放在这里管理
CONFIG = {
    APP_ID = "cli_a9f1a525307a9cbd"
APP_SECRET = "TKhwibOVNhoEdyCrkCnWPdxZOjPka3Rf"
APP_TOKEN = "P0WpbMHLBa6zaQsyyvPcy2eqnuf"
# 【需修改】请填入你通过“复制数据表ID”获取到的 tbl... 开头的字符串
TABLE_ID = "tbl0MFhSZr8yuIsk"
    "DEEPSEEK_API_KEY": "sk-6f3ff713536f45c0a6fc702ffa77eebf",
    "BASE_URL": "https://api.deepseek.com"
}

client_ai = OpenAI(api_key=CONFIG["DEEPSEEK_API_KEY"], base_url=CONFIG["BASE_URL"])

def extract_pdf_text(file_source, is_stream=True):
    """提取 PDF 文本（支持文件流或本地路径）"""
    if is_stream:
        doc = fitz.open(stream=file_source.read(), filetype="pdf")
    else:
        doc = fitz.open(file_source)
        
    text = ""
    # 若需阅读全部页码，请将 doc[:5] 改为 doc
    for page in doc: 
        text += page.get_text()
    return text

def ai_extract_parameters(text, keywords):
    """调用 DeepSeek 提取数据"""
    prompt = f"""
    你是一个专业的电池/化学材料科研助手。请从以下文本中提取指定参数的数值和单位。
    要求：1. 严格按清单提取；2. 纯 JSON 格式；3. 没提到设为 "N/A"。
    参数清单：{", ".join(keywords)}
    论文文本：{text[:12000]} 
    """
    try:
        response = client_ai.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI 提取出错: {e}")
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

# 如果你直接运行这个文件，它会执行以下批量处理逻辑
if __name__ == "__main__":
    import os
    # 示例：批量处理当前文件夹下所有的 pdf
    keywords_df = pd.read_csv("参数关键字.xlsx - Sheet1.csv")
    k_list = keywords_df['参数（中文）'].tolist()
    
    for file in os.listdir("."):
        if file.endswith(".pdf"):
            print(f"正在处理: {file}")
            content = extract_pdf_text(file, is_stream=False)
            result = ai_extract_parameters(content, k_list)
            if result:
                result["论文标题"] = file
                upload_to_feishu(result)
