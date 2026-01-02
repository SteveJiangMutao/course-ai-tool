import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import io
import json
import time

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(page_title="AI 课程助手 v3.0", page_icon="🎓", layout="wide")

st.title("🎓 留学课程描述智能生成工具 (v3.0 强力版)")

# --- 🔴 版本检测标记 (如果你没看到这个，说明代码没更新) ---
st.sidebar.markdown("### 🚀 当前版本: v3.0 (自动合并+智能撰写)")
st.sidebar.info("如果不显示 v3.0，请点击右上角三个点 -> 'Clear cache' 或 'Reboot app'")

# ==========================================
# 2. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ API 设置")
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 系统 Key 已加载")
    else:
        api_key = st.text_input("输入 Gemini API Key", type="password")
    
    model_name = st.selectbox(
        "选择模型", 
        ["gemini-1.5-pro", "gemini-3-pro-preview"],
        index=0,
        help="必须用 Pro 模型，否则知识库调用可能不全。"
    )

# ==========================================
# 3. 输入区域
# ==========================================
col1, col2 = st.columns(2)
with col1:
    user_school = st.text_input("🏫 学校名称 (必填)", placeholder="例如: 港大 / HKU")
with col2:
    user_program = st.text_input("🎓 专业名称 (必填)", placeholder="例如: CS / 计算机科学")

uploaded_files = st.file_uploader("📤 上传资料", type=['png', 'jpg', 'jpeg', 'txt'], accept_multiple_files=True)

# ==========================================
# 4. 核心逻辑
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

if st.button("🚀 开始生成 (强制合并模式)", type="primary"):
    if not uploaded_files or not api_key:
        st.error("❌ 请检查文件或 API Key")
        st.stop()
    if not user_school or not user_program:
        st.warning("⚠️ 警告：未填写学校/专业，AI 生成的内容可能不准确！")

    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- 核心 Prompt (加强版) ---
    prompt = f"""
    你是一个专业的大学教务长。
    
    【任务目标】
    分析图片，提取课程，并利用你的知识库补充课程大纲。

    【关键输入】
    学校: "{user_school}"
    专业: "{user_program}" (Master Level)

    【执行步骤】
    1. **提取**：识别图片中的课程名称。
    2. **撰写 (必须执行)**：
       - 即使图片里只有课程名，你也**必须**检索你的内部知识库。
       - 为每门课撰写一段 **100字左右的中文介绍**。
       - 内容必须包含：核心理论、使用工具、教学目标。
       - **严禁**返回 "未提供"、"图片无信息" 等字眼。直接根据课程名生成！

    【输出格式】
    JSON 列表，字段如下：
    [
        {{
            "School_CN": "标准化中文校名",
            "School_EN": "标准化英文校名",
            "Program_CN": "标准化中文专业名",
            "Program_EN": "标准化英文专业名",
            "Course_Name_EN": "Deep Learning",
            "Course_Content_CN": "本课程深入讲解深度神经网络...(必须由你生成)",
            "Course_Content_EN": "This course covers...(Translation)"
        }}
    ]
    """

    for i, file in enumerate(uploaded_files):
        status_text.text(f"🧠 AI 正在检索知识库并撰写: {file.name} ...")
        try:
            mime = file.type or ("image/png" if file.name.endswith(('.png','.jpg')) else "text/plain")
            res = get_gemini_response(file, mime, prompt, api_key, model_name)
            data = json.loads(clean_json_text(res))
            all_data.extend(data)
        except Exception as e:
            st.error(f"处理出错: {e}")
        progress_bar.progress((i + 1) / len(uploaded_files))

    status_text.success("✅ 完成！")

    if all_data:
        df = pd.DataFrame(all_data)

        # --- 🔧 强制数据一致性 (解决不合并的问题) ---
        # 我们取第一行的学校/专业信息，强制覆盖所有行
        # 这样能保证 100% 所有的行都是一模一样的字符，Excel 才会合并
        if not df.empty:
            first_row = df.iloc[0]
            df['School_CN'] = first_row.get('School_CN', user_school)
            df['School_EN'] = first_row.get('School_EN', user_school)
            df['Program_CN'] = first_row.get('Program_CN', user_program)
            df['Program_EN'] = first_row.get('Program_EN', user_program)

        # 确保列存在
        cols = ['School_CN', 'School_EN', 'Program_CN', 'Program_EN', 'Course_Name_EN', 'Course_Content_CN', 'Course_Content_EN']
        for c in cols: 
            if c not in df.columns: df[c] = ""
        
        df = df[cols]
        
        # --- 设置索引以触发合并 ---
        df_indexed = df.set_index(['School_CN', 'School_EN', 'Program_CN', 'Program_EN'])

        st.dataframe(df_indexed, use_container_width=True)

        # --- 导出 Excel ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_indexed.to_excel(writer, sheet_name='List', merge_cells=True)
            
            # 格式美化
            wb = writer.book
            ws = writer.sheets['List']
            fmt_center = wb.add_format({'valign': 'vcenter', 'text_wrap': True, 'align': 'center'})
            fmt_text = wb.add_format({'valign': 'top', 'text_wrap': True})
            
            ws.set_column('A:D', 20, fmt_center) # 索引列居中
            ws.set_column('E:E', 25, fmt_text)   # 课程名
            ws.set_column('F:G', 50, fmt_text)   # 内容

        st.download_button(
            "📥 下载 Excel (v3.0 合并版)", 
            output.getvalue(), 
            f"{user_school}_Courses.xlsx", 
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )