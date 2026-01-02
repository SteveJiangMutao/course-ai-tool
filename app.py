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
st.set_page_config(
    page_title="AI 课程整理助手 (双语版)", 
    page_icon="🎓", 
    layout="wide"
)

st.title("🎓 留学课程信息提取工具 (自动中英双语)")
st.markdown("""
**功能说明：**
1. 上传课程截图或大纲文本。
2. 输入学校/专业简称（如 "港大 CS"）。
3. AI 自动**提取课程**、**翻译为英文**，并**补全学校专业的中英文全称**。
""")

# ==========================================
# 2. 侧边栏设置 (API Key & 模型)
# ==========================================
with st.sidebar:
    st.header("⚙️ 系统设置")
    
    # 优先读取系统密钥，如果没有则显示输入框
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已加载系统内置 Key")
    else:
        api_key = st.text_input("请输入 Gemini API Key", type="password", help="在此填入您的 Key 以开始使用")
    
    # 模型选择
    model_name = st.selectbox(
        "选择模型", 
        ["gemini-1.5-pro", "gemini-3-pro-preview", "gemini-2.0-flash-exp"],
        index=0,
        help="推荐使用 1.5-pro，它对文档和表格的理解最稳定。"
    )
    
    st.divider()
    st.info("💡 **小贴士**：支持一次性上传多张图片，系统会自动合并到同一个 Excel 表格中。")

# ==========================================
# 3. 用户输入区域
# ==========================================
col1, col2 = st.columns(2)
with col1:
    user_school = st.text_input("🏫 学校名称 (输入中文/英文/简称均可)", placeholder="例如: 港大 / HKU")
with col2:
    user_program = st.text_input("🎓 专业名称 (输入中文/英文/简称均可)", placeholder="例如: CS / 计算机科学")

uploaded_files = st.file_uploader(
    "📤 请上传课程资料 (支持 PNG, JPG, TXT, MD)", 
    type=['png', 'jpg', 'jpeg', 'txt', 'md'], 
    accept_multiple_files=True
)

# ==========================================
# 4. 核心逻辑函数
# ==========================================

def clean_json_text(text):
    """清理 Markdown 标记，确保 JSON 解析成功"""
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

def get_gemini_response(file_obj, mime_type, prompt, api_key, model_name):
    """调用 Gemini API"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    try:
        content_part = None
        if mime_type.startswith("image"):
            image = Image.open(file_obj)
            content_part = image
        else:
            text_content = file_obj.getvalue().decode("utf-8")
            content_part = text_content
            
        response = model.generate_content([prompt, content_part])
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# 5. 主处理流程
# ==========================================

if st.button("🚀 开始智能提取", type="primary"):
    # --- 基础校验 ---
    if not uploaded_files:
        st.warning("⚠️ 请先上传文件！")
        st.stop()
    if not api_key:
        st.error("❌ 请先配置 API Key！")
        st.stop()

    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- 构建 Prompt (核心指令) ---
    prompt = f"""
    你是一个专业的留学申请数据专员。请分析提供的图片或文本，提取课程列表。

    【输入线索】
    用户提供的学校: "{user_school if user_school else '未提供，请根据图片内容推断'}"
    用户提供的专业: "{user_program if user_program else '未提供，请根据图片内容推断'}"

    【任务要求】
    1. **学校/专业标准化**：
       - 无论用户输入的是简称还是中文，请务必补全为**正式的中文全称**和**正式的英文全称**。
       - 例如：输入"港大"，输出 School_CN="香港大学", School_EN="The University of Hong Kong"。
    
    2. **课程提取与翻译**：
       - 提取所有课程名称。
       - 将“课程名称”和“课程内容”**全部翻译为英文**。
       - 如果原文已是英文，请保持并优化语法。

    【输出格式】
    必须严格返回一个 JSON 列表 (List of Objects)，不要包含 Markdown 标记。
    字段名必须如下：
    [
        {{
            "School_CN": "香港大学",
            "School_EN": "The University of Hong Kong",
            "Program_CN": "计算机科学理学硕士",
            "Program_EN": "MSc in Computer Science",
            "Course_Name_EN": "Advanced Algorithms",
            "Course_Content_EN": "Topics include graph theory, dynamic programming..."
        }}
    ]
    """

    # --- 循环处理文件 ---
    for i, file in enumerate(uploaded_files):
        status_text.text(f"🔄 ({i+1}/{len(uploaded_files)}) 正在分析: {file.name} ...")
        
        try:
            # 识别文件类型
            mime_type = file.type
            if not mime_type: 
                mime_type = "image/png" if file.name.endswith(('.png', '.jpg')) else "text/plain"

            # 调用 AI
            raw_response = get_gemini_response(file, mime_type, prompt, api_key, model_name)
            
            # 解析 JSON
            json_str = clean_json_text(raw_response)
            data = json.loads(json_str)
            
            # 标记来源文件
            for item in data:
                item['Source_File'] = file.name
            
            all_data.extend(data)
            
        except Exception as e:
            st.error(f"❌ 文件 {file.name} 处理失败: {e}")
        
        # 更新进度
        progress_bar.progress((i + 1) / len(uploaded_files))
        time.sleep(1) # 避免触发 API 速率限制

    status_text.success("✅ 处理完成！")
    
    # --- 展示与导出 ---
    if all_data:
        df = pd.DataFrame(all_data)
        
        # 定义列顺序
        desired_columns = [
            'School_CN', 'School_EN', 
            'Program_CN', 'Program_EN', 
            'Course_Name_EN', 'Course_Content_EN', 
            'Source_File'
        ]
        
        # 补全缺失列
        for col in desired_columns:
            if col not in df.columns:
                df[col] = ""
        
        df = df[desired_columns]

        st.subheader("📊 结果预览")
        st.dataframe(df, use_container_width=True)
        
        # 生成 Excel 文件流
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Course List')
            
            # 美化列宽
            worksheet = writer.sheets['Course List']
            worksheet.set_column('A:B', 20) # 学校
            worksheet.set_column('C:D', 20) # 专业
            worksheet.set_column('E:E', 30) # 课程名
            worksheet.set_column('F:F', 50) # 内容
            
        processed_data = output.getvalue()
        
        # 智能文件名
        file_label = "Courses_Translated.xlsx"
        if not df.empty and df.iloc[0]['School_EN']:
            file_label = f"{df.iloc[0]['School_EN']}_Courses.xlsx"

        st.download_button(
            label="📥 下载 Excel (含中英双语信息)",
            data=processed_data,
            file_name=file_label,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("⚠️ 未能提取到数据，请检查图片是否清晰。")