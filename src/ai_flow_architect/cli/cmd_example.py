"""CLI 命令：example — 生成带漏洞的示例代码。"""

from pathlib import Path


def do_example(args):
    """生成带已知漏洞的示例代码。"""
    example_code = '''"""
示例 Python 代码 — 包含已知安全漏洞
用于验证武器库的 attack 子命令
"""
import sqlite3
import os

# 硬编码密钥（漏洞1）
SECRET_API_KEY = "sk_live_1234567890abcdef"
DATABASE_URL = "postgresql://admin:secret123@localhost:5432/mydb"


def get_user(username):
    """通过用户名查询用户信息。"""
    # SQL 注入漏洞（漏洞2）
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # ⚠️ 危险：直接拼接用户输入到 SQL 语句
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return result

def render_profile(user_data):
    """将用户数据渲染为 HTML 配置文件。"""
    html = "<html><body>"
    # XSS 漏洞（漏洞3）
    html += f"<h1>Welcome, {user_data['name']}!</h1>"
    html += f"<p>Email: {user_data['email']}</p>"
    html += "</body></html>"
    return html

def export_users(filename, users):
    """导出用户列表到文件。"""
    # 路径遍历漏洞（漏洞4）
    with open(filename, "w") as f:
        for user in users:
            f.write(f"{user['name']},{user['email']}\\n")

def run_command(cmd_param):
    """执行系统命令。"""
    # 命令注入漏洞（漏洞5）
    os.system(f"ping {cmd_param}")

if __name__ == "__main__":
    # 使用弱哈希的密码存储（漏洞6）
    import hashlib
    password = "admin123"
    hash_val = hashlib.md5(password.encode()).hexdigest()
    print(f"Password hash: {hash_val}")
    print(get_user("admin"))
'''

    example_requirement = '''需求：编写一个用户管理系统

功能要求：
1. 用户可以通过用户名查询个人信息
2. 系统应显示用户名和邮箱
3. 支持导出用户列表到文件
4. 支持执行网络诊断命令
5. 用户密码应加密存储

请生成对应的 Python 代码实现。'''

    # 写入当前目录
    output_dir = Path(args.output_dir) if hasattr(args, 'output_dir') and args.output_dir else Path.cwd()
    code_path = output_dir / "example_output.txt"
    req_path = output_dir / "example_requirement.txt"

    code_path.write_text(example_code, encoding="utf-8")
    req_path.write_text(example_requirement, encoding="utf-8")

    print(f"已生成示例代码: {code_path}")
    print(f"已生成示例需求: {req_path}")
    print("")
    print("测试攻击引擎:")
    print(f"  ai-flow attack {code_path}")
    print("")
    print("测试跨审查:")
    print(f"  ai-flow cross-examine {code_path} --requirement {req_path}")
    print("")
    print("测试溯源追踪:")
    print(f"  ai-flow trace {code_path}")
    print("")
    print("Want to audit your own code?")
    print("  → Open Playground: https://wdnmd1265.github.io/ai-flow-architect/playground.html")
    print("  → Install CLI:     pip install --user ai-flow-architect && ai-flow init")
