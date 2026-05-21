"""
TrustEngine API — FastAPI 包装

启动：
    uvicorn ai_flow_architect.api:app --host 0.0.0.0 --port 8000

调用：
    POST /audit
    {
        "requirement": "审计这段代码的安全性",
        "ai_output": "def login(user, pwd): ..."
    }
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .engine import TrustEngine, AuditContext


app = FastAPI(
    title="AI Trust Engine",
    description="克服 AI 幻觉的信任审查服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    """审查请求"""
    requirement: str = Field(..., description="用户需求描述", min_length=1)
    ai_output: str = Field(..., description="AI 生成的产出", min_length=1)
    project_path: Optional[str] = Field(None, description="项目路径（可选，传入后审查深度升级）")
    files: Optional[dict] = Field(None, description="文件内容（可选）")
    dependencies: Optional[list] = Field(None, description="依赖声明（可选）")
    brain1: str = Field("gpt-4o", description="主审查模型")
    brain2: Optional[str] = Field(None, description="副审查模型（默认自动选择）")


@app.post("/audit")
async def audit(request: AuditRequest):
    """
    审查 AI 产出，返回 TrustReport。
    
    最简调用：只传 requirement + ai_output。
    进阶调用：加上 project_path / files / dependencies，审查深度自动升级。
    """
    try:
        engine = TrustEngine(brain1=request.brain1, brain2=request.brain2)
        
        context = None
        if request.project_path or request.files or request.dependencies:
            context = AuditContext(
                project_path=request.project_path,
                files=request.files,
                dependencies=request.dependencies,
            )
        
        report = await engine.audit(
            requirement=request.requirement,
            ai_output=request.ai_output,
            context=context,
        )
        
        return report.model_dump()
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/models")
async def models():
    """查看支持的模型列表"""
    return {
        "providers": {
            "openai": {"tested": True, "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
            "anthropic": {"tested": True, "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]},
            "dashscope": {"tested": False, "models": ["qwen-max", "qwen-plus", "qwen-turbo"]},
            "deepseek": {"tested": False, "models": ["deepseek-chat", "deepseek-coder"]},
            "zhipu": {"tested": False, "models": ["glm-4", "glm-4-flash"]},
            "moonshot": {"tested": False, "models": ["moonshot-v1-8k", "moonshot-v1-32k"]},
            "ollama": {"tested": False, "models": ["llama3.1", "qwen2.5", "deepseek-r1"]},
        }
    }
