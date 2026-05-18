"""
MVP测试脚本
测试核心流程：一号脑规划 → 用户审批 → 执行 → 二号脑审核
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai_flow_architect.core.architect import FlowArchitect


async def test_basic_flow():
    """测试基本流程"""
    print("="*60)
    print("AI Flow Architect MVP 测试")
    print("="*60)
    
    # 配置：必须配置两个不同的模型
    config = {
        "brain1": "gpt-4o",
        "brain2": "claude-3-haiku",
    }
    
    try:
        # 初始化框架
        print("\n1. 初始化框架...")
        architect = FlowArchitect(config=config)
        print("✓ 框架初始化成功")
        
        # 测试用户输入
        user_input = "帮我设计一个简单的计算器程序"
        print(f"\n2. 用户输入: {user_input}")
        
        # 执行工作流（这会触发用户审批）
        print("\n3. 开始执行工作流...")
        print("   注意：蓝图生成后会暂停等待用户审批")
        print("   请输入 A 批准蓝图")
        
        result = await architect.run(user_input)
        
        print("\n4. 执行结果:")
        print(f"   状态: {result.get('status')}")
        if 'audit_result' in result:
            print(f"   质量分数: {result['audit_result'].get('score', 'N/A')}")
        
        print("\n✓ 测试完成")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_basic_flow())