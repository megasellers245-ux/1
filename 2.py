import streamlit as st
import pandas as pd
# 从核心逻辑文件中导入功能
from core_processor import extract_pdf_text, ai_extract_parameters, upload_to_feishu

st.set_page_config(page_title="论文参数全自动提取器", layout="wide")
st.title("📚 论文参数全自动提取 & 飞书同步")

# 侧边栏：加载关键词
try:
    keywords_df = pd.read_csv("参数关键字.xlsx - Sheet1.csv")
    keywords_list = keywords_df['参数（中文）'].tolist()
    st.sidebar.success(f"已加载 {len(keywords_list)} 个关键词")
except Exception as e:
    st.sidebar.error("请检查 CSV 文件是否存在")
    keywords_list = []

# 主界面：文件上传
uploaded_files = st.file_uploader("上传论文 PDF", type="pdf", accept_multiple_files=True)

if st.button("开始提取并提交至飞书"):
    if not uploaded_files or not keywords_list:
        st.warning("请检查文件上传和关键词列表")
    else:
        progress_bar = st.progress(0)
        for i, pdf_file in enumerate(uploaded_files):
            with st.status(f"正在处理: {pdf_file.name}...") as status:
                # 调用核心逻辑
                text = extract_pdf_text(pdf_file, is_stream=True)
                result = ai_extract_parameters(text, keywords_list)
                
                if result:
                    result["论文标题"] = pdf_file.name 
                    success = upload_to_feishu(result)
                    if success:
                        status.update(label=f"✅ {pdf_file.name} 已同步", state="complete")
                    else:
                        status.update(label=f"❌ {pdf_file.name} 同步失败", state="error")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
        st.balloons()
