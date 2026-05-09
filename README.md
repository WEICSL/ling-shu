🧠 灵枢 · LingShu
一个集成本地 Ollama 和云端 DeepSeek 的双核 AI 对话助手。

Python Django License

✨ 功能特点
功能	说明
💬 多会话对话	支持多个对话独立管理，历史记录持久化
🤖 Agent 模式	工具调用：数学计算、网络搜索、天气查询
🎭 AI 人设系统	可自定义角色性格，支持模板快速创建
🎨 Markdown 渲染	代码高亮、表格、列表完美显示
🔑 用户系统	登录/注册、个人中心、头像上传
⚙️ 系统设置	API 配置、模型参数、主题切换
📊 统计看板	对话次数、使用时长可视化图表
📖 提示词库	预设常用提示词，一键使用
🛠️ 技术栈
后端: Django 6.0 + SQLite
AI 引擎: Ollama (本地) + DeepSeek API (云端)
前端: HTML/CSS/JS + Live2D
渲染: Marked.js + Highlight.js
--------以下是安装方法--------

安装与运行

克隆项目
git clone https://gitee.com/WEICSL/Ling-shu.git
cd Ling-shu

2. 创建虚拟环境
bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

3. 安装依赖
bash
pip install -r requirements.txt

4. 配置环境变量
创建 .env 文件
编辑 .env 文件，填入你的配置：

DEEPSEEK_API_KEY：从 DeepSeek 平台 获取

SECRET_KEY：任意随机字符串，可用 openssl rand -hex 32 生成

注意：.env 文件包含敏感信息，已被 .gitignore 排除，不会上传到仓库

env
DEEPSEEK_API_KEY=你的API密钥
SECRET_KEY=你的Django密钥
DEBUG=True

5. 数据库迁移
bash
python manage.py makemigrations
python manage.py migrate

7. 创建超级用户（可选）
bash
python manage.py createsuperuser

9. 运行项目
bash
python manage.py runserver
访问 http://127.0.0.1:8000

🖼️ 界面预览
主界面	看板娘
AI 对话	Live2D 互动
📝 使用说明
Agent 模式：勾选后 AI 可调用计算、搜索、天气工具

人设切换：在看板娘界面选择不同性格的 AI

双击消息：可编辑用户消息重新发送

右键消息：复制内容或删除消息

📄 开源协议
MIT License

👨 作者
WEICSL

致谢
Django

Ollama

DeepSeek

Live2D

text

## 同时创建 `.gitignore` 文件

点击 `新建文件`，文件名填 `.gitignore`，内容：

```gitignore
# Python
__pycache__/
*.py[cod]
*.so
.Python
.env
venv/
env/

# Django
db.sqlite3
*.log
/staticfiles/

# IDE
.vscode/
.idea/

# 系统文件
.DS_Store
Thumbs.db

-----------注意-----------
如果还有疑问，请联系作者，有时间会一一答复
作者邮箱：3561855366@qq.com
