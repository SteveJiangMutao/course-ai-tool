import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import io
import json
import time

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(page_title="AI 课程助手 v6.0", page_icon="🎓", layout="wide")

st.title("🎓 留学课程描述生成 (v6.0 完美合并版)")
st.sidebar.markdown("### 🚀 版本: v6.0")
st.sidebar.markdown("✅ **模型**: `gemini-3-pro-preview`")
st.sidebar.markdown("✅ **Excel**: 学校/专业均合并 + 无边框")

# ==========================================
# 2. 设置与输入
# ==========================================
with st.sidebar:
    st.header("⚙️ API 设置")
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Key 已加载")
    else:
        api_key = st.text_input("Gemini API Key", type="password")
    
    # 🔒 锁定模型
    model_name = "gemini-3-pro-preview"

col1, col2 = st.columns(2)
with col1:
    user_school = st.text_input("🏫 学校名称", placeholder="例如: 港大")
with col2:
    user_program = st.text_input("🎓 专业名称", placeholder="例如: CS")

uploaded_files = st.file_uploader("📤 上传资料", type=['png', 'jpg', 'jpeg', 'txt'], accept_multiple_files=True)

# ==========================================
# 3. 核心逻辑
# ==========================================
def clean_json_text(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

def get_gemini_response(file_obj, mime_type, prompt, api_key, model_name):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    try:
        content_part = Image.open(file_obj) if mime_type.startswith("image") else file_obj.getvalue().decode("utf-8")
        response = model.generate_content([prompt, content_part])
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

if st.button("🚀 生成最终 Excel", type="primary"):
    if not uploaded_files or not api_key:
        st.error("❌ 请检查文件或 Key")
        st.stop()
    
    all_data = []
    progress_bar = st.progress(0)
    
    prompt = f"""
    你是一个教务长。请分析图片提取课程，并利用知识库补充大纲。

    【输入】学校: "{user_school}", 专业: "{user_program}" (Master Level)

    【任务】
    1. 提取所有课程名称。
    2. **强制撰写**：如果图片无描述，必须根据知识库撰写一段**中文**课程介绍（约100字，包含核心理论与工具）。
    3. **标准化**：生成学校和专业的正式中英文全称。

    【输出格式 JSON】
    [
        {{
            "School_CN": "中文校名",
            "School_EN": "英文校名",
            "Program_CN": "中文专业名",
            "Program_EN": "英文专业名",
            "Course_Name_EN": "Deep Learning",
            "Course_Content_CN": "本课程讲解深度学习的核心算法...(必须生成中文)"
        }}
    ]
    """

    for i, file in enumerate(uploaded_files):
        try:
            mime = file.type or ("image/png" if file.name.endswith(('.png','.jpg')) else "text/plain")
            res = get_gemini_response(file, mime, prompt, api_key, model_name)
            data = json.loads(clean_json_text(res))
            all_data.extend(data)
        except Exception as e:
            st.error(f"Error: {e}")
        progress_bar.progress((i + 1) / len(uploaded_files))

    if all_data:
        df = pd.DataFrame(all_data)

        # --- 1. 强制统一数据 (这是合并的关键) ---
        if not df.empty:
            first = df.iloc[0]
            # 强制所有行的学校和专业信息完全一致
            df['School_CN'] = first.get('School_CN', user_school)
            df['School_EN'] = first.get('School_EN', user_school)
            df['Program_CN'] = first.get('Program_CN', user_program)
            df['Program_EN'] = first.get('Program_EN', user_program)

        # --- 2. 构造合并列 (换行显示) ---
        df['School_Name'] = df['School_CN'] + '\n' + df['School_EN']
        df['Program_Name'] = df['Program_CN'] + '\n' + df['Program_EN']

        # --- 3. 筛选列 ---
        target_cols = ['School_Name', 'Program_Name', 'Course_Name_EN', 'Course_Content_CN']
        for c in target_cols:
            if c not in df.columns: df[c] = ""
        
        df = df[target_cols]
        
        # --- 4. 设置多级索引 (School 和 Program 都会被合并) ---
        df_indexed = df.set_index(['School_Name', 'Program_Name'])

        st.success("✅ 处理完成！")
        st.dataframe(df_indexed, use_container_width=True)

        # --- 5. 导出 Excel ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # merge_cells=True 会自动合并索引列 (即 School 和 Program)
            df_indexed.to_excel(writer, sheet_name='List', merge_cells=True)
            
            wb = writer.book
            ws = writer.sheets['List']
            
            # 样式 A：索引列 (学校 & 专业) -> 居中 + 垂直居中 + 无边框
            fmt_index = wb.add_format({
                'valign': 'vcenter', 
                'align': 'center', 
                'text_wrap': True,
                'border': 0 
            })
            
            # 样式 B：内容列 (课程 & 描述) -> 靠上对齐 + 无边框
            fmt_content = wb.add_format({
                'valign': 'top', 
                'text_wrap': True,
                'border': 0
            })
            
            # 应用样式
            # A列(School) 和 B列(Program) 都应用 fmt_index
            ws.set_column('A:B', 25, fmt_index) 
            
            # C列(Course)
            ws.set_column('C:C', 30, fmt_content)
            
            # D列(Content)
            ws.set_column('D:D', 60, fmt_content)

        st.download_button(
            "📥 下载 Excel (v6.0)", 
            output.getvalue(), 
            f"{user_school}_Courses_v6.xlsx", 
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
