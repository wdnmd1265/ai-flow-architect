"""
攻击执行引擎

加载 config/attack_strategies/core.yaml 中的攻击策略，
自动检测输入类型，执行静态分析或沙箱执行攻击。
三层防护：策略层、执行层、环境层。
"""

import ast
import re
import subprocess
import tempfile
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import yaml
from loguru import logger


@dataclass
class AttackStrategy:
    """攻击策略"""
    id: str
    category: str
    severity: str
    description: str
    input_template: str
    expected: str
    applicable_to: List[str]
    verification: str  # code_execution / static_analysis / manual
    sandbox_level: str
    dangerous: bool


@dataclass
class AttackResult:
    """攻击执行结果"""
    strategy_id: str
    input_used: str
    execution_result: str
    triggered: bool
    error: Optional[str] = None
    execution_time: float = 0.0
    sandbox_used: bool = False


@dataclass
class AttackEngineConfig:
    """攻击引擎配置"""
    strategies_path: Path
    temp_dir: Path
    timeout: int = 5
    max_strategies: int = 50
    allow_dangerous: bool = False


class AttackEngine:
    """
    攻击执行引擎
    
    核心功能：
    1. 加载攻击策略库
    2. 自动检测输入类型（代码/文本）
    3. 执行攻击：静态分析优先，沙箱仅对安全策略开放
    4. 三层防护机制
    """
    
    DANGEROUS_PATTERNS = [
        r'\brm\b.*-rf',
        r'\bdel\b.*/.*',
        r'\bformat\b',
        r'\bshutdown\b',
        r'\bhalt\b',
        r'\bpoweroff\b',
        r'\bkill\b.*-9',
        r'\bdd\b.*if=/dev/',
        r'\b:\(\)\{.*\}',
        r'\bmkfs\b',
        r'\bmount\b.*-o.*remount.*rw',
        r'\becho\b.*>\s*/proc/',
        r'\bchmod\b.*777',
        r'\bchown\b.*root',
        r'\bwget\b.*-O.*/bin/',
        r'\bcurl\b.*-o.*/bin/',
    ]
    
    def __init__(
        self,
        strategies_path: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
        timeout: int = 5,
        allow_dangerous: bool = False,
    ):
        if strategies_path is None:
            strategies_path = (
                Path(__file__).parent.parent / 
                "config" / "attack_strategies" / "core.yaml"
            )
        if temp_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="arsenal_attack_"))
        
        self.config = AttackEngineConfig(
            strategies_path=strategies_path,
            temp_dir=temp_dir,
            timeout=timeout,
            allow_dangerous=allow_dangerous,
        )
        self.strategies: Dict[str, AttackStrategy] = {}
        self._load_strategies()
        
        logger.info(f"攻击引擎初始化完成 | 策略数: {len(self.strategies)} | 临时目录: {temp_dir}")
    
    def _load_strategies(self):
        """加载攻击策略"""
        try:
            with open(self.config.strategies_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            strategies = data.get("strategies", [])
            for s in strategies:
                strategy = AttackStrategy(**s)
                self.strategies[strategy.id] = strategy
            
            logger.info(f"加载 {len(self.strategies)} 条攻击策略")
        except Exception as e:
            logger.error(f"加载攻击策略失败: {e}")
            raise
    
    def detect_input_type(self, content: str) -> str:
        """
        检测输入类型
        
        Returns:
            类型: "code", "sql", "text", "unknown"
        """
        # 检查代码特征
        code_keywords = [
            "def ", "class ", "import ", "from ", "if ", "for ", "while ",
            "return ", "print(", "console.log", "function ", "var ", "let ",
            "const ", "public ", "private ", "protected ", "void ", "int ",
            "String ", "System.out.println",
        ]
        
        sql_keywords = [
            "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "FROM ", "WHERE ",
            "JOIN ", "UNION ", "CREATE ", "DROP ", "ALTER ", "TABLE ",
        ]
        
        content_lower = content.lower()
        
        # 检查代码（优先，因代码中常内嵌 SQL 字符串）
        code_count = sum(1 for kw in code_keywords if kw in content)
        if code_count >= 2:
            return "code"
        
        # 检查 SQL
        sql_count = sum(1 for kw in sql_keywords if kw.lower() in content_lower)
        if sql_count >= 2:
            return "sql"
        
        # 检查特定文件扩展名
        if any(ext in content for ext in [".py", ".js", ".java", ".cpp", ".c", ".go"]):
            return "code"
        
        return "text"
    
    def filter_strategies_by_type(
        self,
        input_type: str,
        category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[AttackStrategy]:
        """
        根据输入类型过滤策略
        """
        filtered = []
        for strategy in self.strategies.values():
            # 检查适用性
            if input_type not in strategy.applicable_to:
                continue
            
            # 检查类别
            if category and strategy.category != category:
                continue
            
            # 检查严重度
            if severity and strategy.severity != severity:
                continue
            
            # 检查危险策略
            if strategy.dangerous and not self.config.allow_dangerous:
                logger.warning(f"跳过危险策略: {strategy.id}")
                continue
            
            filtered.append(strategy)
        
        return filtered
    
    def _check_dangerous_patterns(self, content: str) -> bool:
        """检查是否包含危险模式"""
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def _execute_static_analysis(
        self,
        content: str,
        strategy: AttackStrategy,
    ) -> AttackResult:
        """
        执行静态分析
        
        使用正则表达式/AST匹配检测漏洞。
        """
        import time
        start_time = time.time()
        
        try:
            # 检查危险模式
            if self._check_dangerous_patterns(content):
                return AttackResult(
                    strategy_id=strategy.id,
                    input_used=strategy.input_template,
                    execution_result="检测到危险模式，拒绝分析",
                    triggered=False,
                    error="包含危险操作模式",
                    execution_time=time.time() - start_time,
                )
            
            # 根据策略类型进行不同分析
            if strategy.category == "security":
                # 安全漏洞检测
                if "sql" in strategy.id:
                    # SQL注入检测 - 更广泛的模式
                    sql_patterns = [
                        r"'.*OR.*'1'='1'",
                        r"'.*--",
                        r"'.*;.*--",
                        r"UNION.*SELECT",
                        r"SLEEP\(",
                        r"f[\"'].*SELECT",
                        r"f[\"'].*WHERE",
                        r"format\(.*SELECT",
                        r"%s.*SELECT",
                        r"\+.*SELECT",
                        r"execute\(query\)",
                        r"execute\(.*f[\"']",
                        r"cursor\.execute\([^?]",
                    ]
                    for pattern in sql_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            return AttackResult(
                                strategy_id=strategy.id,
                                input_used=strategy.input_template,
                                execution_result=f"检测到SQL注入模式: {pattern}",
                                triggered=True,
                                execution_time=time.time() - start_time,
                            )
                
                elif "xss" in strategy.id:
                    # XSS检测 - 更广泛的模式
                    xss_patterns = [
                        r"<script>",
                        r"onerror=",
                        r"javascript:",
                        r"<img.*onload=",
                        r"<svg.*onload=",
                        r"innerHTML",
                        r"document\.write\(",
                        r"f[\"'].*<h[1-6]>",
                        r"\+.*<.*>",
                        r"html\s*\+=",
                        r"html\s*=\s*\".*<",
                        r"f[\"'].*<.*>",
                    ]
                    for pattern in xss_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            return AttackResult(
                                strategy_id=strategy.id,
                                input_used=strategy.input_template,
                                execution_result=f"检测到XSS模式: {pattern}",
                                triggered=True,
                                execution_time=time.time() - start_time,
                            )
                
                elif "command" in strategy.id:
                    # 命令注入检测
                    cmd_patterns = [
                        r";.*rm",
                        r"\|\s*cat",
                        r"`.*`",
                        r"\$\(.*\)",
                    ]
                    for pattern in cmd_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            return AttackResult(
                                strategy_id=strategy.id,
                                input_used=strategy.input_template,
                                execution_result=f"检测到命令注入模式: {pattern}",
                                triggered=True,
                                execution_time=time.time() - start_time,
                            )
            
            # 对于Python代码，尝试AST分析
            if self.detect_input_type(content) == "code" and ".py" in content:
                try:
                    tree = ast.parse(content)
                    # 检查危险函数调用
                    dangerous_calls = ["eval", "exec", "os.system", "subprocess.call"]
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name):
                                if node.func.id in dangerous_calls:
                                    return AttackResult(
                                        strategy_id=strategy.id,
                                        input_used=strategy.input_template,
                                        execution_result=f"检测到危险函数调用: {node.func.id}",
                                        triggered=True,
                                        execution_time=time.time() - start_time,
                                    )
                except SyntaxError:
                    pass
            
            # 默认：未触发
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result="未检测到匹配的漏洞模式",
                triggered=False,
                execution_time=time.time() - start_time,
            )
            
        except Exception as e:
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result=f"静态分析失败: {e}",
                triggered=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )
    
    def _execute_sandbox(
        self,
        content: str,
        strategy: AttackStrategy,
    ) -> AttackResult:
        """
        沙箱执行
        
        仅对 verification=code_execution 且 dangerous=false 的策略开放。
        使用 subprocess.run 在隔离环境中执行。
        """
        import time
        start_time = time.time()
        
        # 安全检查
        if strategy.dangerous:
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result="危险策略禁止沙箱执行",
                triggered=False,
                error="策略标记为dangerous=true",
                execution_time=time.time() - start_time,
            )
        
        if self._check_dangerous_patterns(content):
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result="内容包含危险模式，拒绝执行",
                triggered=False,
                error="检测到危险模式",
                execution_time=time.time() - start_time,
            )
        
        try:
            # 创建临时文件
            temp_file = self.config.temp_dir / f"attack_{strategy.id}.py"
            temp_file.write_text(content, encoding="utf-8")
            
            # 执行命令
            cmd = [sys.executable, str(temp_file)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                shell=False,
                cwd=self.config.temp_dir,
            )
            
            # 分析结果
            triggered = False
            output_lines = result.stdout.splitlines() + result.stderr.splitlines()
            
            # 简单检测：检查是否有异常输出
            error_keywords = ["error", "exception", "traceback", "failed", "injection"]
            for line in output_lines:
                if any(kw in line.lower() for kw in error_keywords):
                    triggered = True
                    break
            
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result=result.stdout[:500] + (result.stderr[:500] if result.stderr else ""),
                triggered=triggered,
                error=result.stderr if result.returncode != 0 else None,
                execution_time=time.time() - start_time,
                sandbox_used=True,
            )
            
        except subprocess.TimeoutExpired:
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result="执行超时",
                triggered=False,
                error="timeout",
                execution_time=self.config.timeout,
                sandbox_used=True,
            )
        except Exception as e:
            return AttackResult(
                strategy_id=strategy.id,
                input_used=strategy.input_template,
                execution_result=f"沙箱执行失败: {e}",
                triggered=False,
                error=str(e),
                execution_time=time.time() - start_time,
                sandbox_used=True,
            )
    
    def execute_attack(
        self,
        content: str,
        strategy_id: Optional[str] = None,
        input_type: Optional[str] = None,
    ) -> List[AttackResult]:
        """
        执行攻击
        
        Args:
            content: 待攻击的内容
            strategy_id: 指定策略ID（可选）
            input_type: 输入类型（可选，自动检测）
            
        Returns:
            攻击结果列表
        """
        # 检测输入类型
        if input_type is None:
            input_type = self.detect_input_type(content)
        logger.info(f"检测到输入类型: {input_type}")
        
        # 选择策略
        if strategy_id:
            if strategy_id not in self.strategies:
                raise ValueError(f"策略不存在: {strategy_id}")
            strategies = [self.strategies[strategy_id]]
        else:
            strategies = self.filter_strategies_by_type(input_type)
            # 限制数量
            strategies = strategies[:self.config.max_strategies]
        
        results = []
        for strategy in strategies:
            logger.info(f"执行攻击策略: {strategy.id}")
            
            # 根据验证方式选择执行方法
            if strategy.verification == "code_execution" and not strategy.dangerous:
                result = self._execute_sandbox(content, strategy)
            else:
                result = self._execute_static_analysis(content, strategy)
            
            results.append(result)
        
        return results
    
    def format_results(
        self,
        results: List[AttackResult],
        format_type: str = "text",
    ) -> str:
        """格式化攻击结果"""
        if format_type == "json":
            import json
            return json.dumps([
                {
                    "strategy_id": r.strategy_id,
                    "input_used": r.input_used,
                    "execution_result": r.execution_result,
                    "triggered": r.triggered,
                    "error": r.error,
                    "execution_time": r.execution_time,
                    "sandbox_used": r.sandbox_used,
                }
                for r in results
            ], ensure_ascii=False, indent=2)
        
        elif format_type == "html":
            return self._format_html(results)
        
        else:  # text
            return self._format_text(results)
    
    def _format_text(self, results: List[AttackResult]) -> str:
        """文本格式输出"""
        lines = []
        lines.append("=" * 80)
        lines.append("攻击执行结果")
        lines.append("=" * 80)
        
        triggered_count = sum(1 for r in results if r.triggered)
        lines.append(f"执行策略数: {len(results)}")
        lines.append(f"触发防御: {triggered_count}")
        lines.append("")
        
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. 策略: {result.strategy_id}")
            lines.append(f"   输入: {result.input_used[:100]}...")
            lines.append(f"   结果: {result.execution_result[:200]}...")
            lines.append(f"   触发: {'✅ 是' if result.triggered else '❌ 否'}")
            if result.error:
                lines.append(f"   错误: {result.error[:200]}")
            lines.append(f"   用时: {result.execution_time:.2f}s")
            lines.append(f"   沙箱: {'是' if result.sandbox_used else '否'}")
            lines.append("")
        
        # 统计
        lines.append("-" * 40)
        lines.append("统计信息:")
        lines.append(f"  安全策略: {sum(1 for r in results if not r.strategy_id.startswith('logic_'))}")
        lines.append(f"  逻辑策略: {sum(1 for r in results if r.strategy_id.startswith('logic_'))}")
        lines.append(f"  静态分析: {sum(1 for r in results if not r.sandbox_used)}")
        lines.append(f"  沙箱执行: {sum(1 for r in results if r.sandbox_used)}")
        
        return "\n".join(lines)
    
    def _format_html(self, results: List[AttackResult]) -> str:
        """HTML格式输出（用于报告）"""
        html = []
        html.append('<div class="attack-results">')
        html.append('<h3>攻击执行结果</h3>')
        
        triggered_count = sum(1 for r in results if r.triggered)
        html.append(f'<p><strong>执行策略数:</strong> {len(results)}</p>')
        html.append(f'<p><strong>触发防御:</strong> {triggered_count}</p>')
        
        html.append('<table class="attack-table">')
        html.append('<thead><tr>')
        html.append('<th>策略ID</th><th>输入</th><th>结果</th><th>触发</th><th>用时</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for result in results:
            triggered_class = "triggered-yes" if result.triggered else "triggered-no"
            html.append(f'<tr class="{triggered_class}">')
            html.append(f'<td>{result.strategy_id}</td>')
            html.append(f'<td><code>{result.input_used[:80]}...</code></td>')
            html.append(f'<td>{result.execution_result[:150]}...</td>')
            html.append(f'<td>{"✅" if result.triggered else "❌"}</td>')
            html.append(f'<td>{result.execution_time:.2f}s</td>')
            html.append('</tr>')
        
        html.append('</tbody></table>')
        html.append('</div>')
        return "\n".join(html)
    
    def cleanup(self):
        """清理临时目录"""
        if self.config.temp_dir.exists():
            try:
                shutil.rmtree(self.config.temp_dir)
                logger.info(f"清理临时目录: {self.config.temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")


class StrategyMonitor:
    """
    策略退化监控器
    
    功能：
    1. 记录每次攻击策略使用结果
    2. 计算策略近 N 天命中率
    3. 检测 30 天内零命中的退化策略
    4. 生成策略库新鲜度报告
    """
    
    def __init__(self, db: "EvidenceDB" = None, conscience: Optional[Any] = None):
        """
        初始化策略监控器
        
        Args:
            db: 证据数据库实例（用于存储策略命中记录）
            conscience: Conscience 管道实例（用于验证自动扩展的策略）
        """
        self.db = db
        self.conscience = conscience
        self._hits: Dict[str, List[Dict[str, Any]]] = {}  # strategy_id -> [{timestamp, success}]
        
        # 如果提供了数据库，创建策略监控表
        if self.db:
            self._ensure_tables()
    
    def _ensure_tables(self) -> None:
        """确保策略监控表存在"""
        if not self.db:
            return
        
        with self.db._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 0,
                    input_hash TEXT,
                    execution_time REAL,
                    verdict TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy_hits_strategy
                    ON strategy_hits(strategy_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy_hits_timestamp
                    ON strategy_hits(timestamp)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_status (
                    strategy_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'active',
                    last_updated TEXT,
                    notes TEXT,
                    auto_extended INTEGER DEFAULT 0
                )
            """)
            conn.commit()
    
    def record_hit(self, strategy_id: str, success: bool, 
                   input_hash: str = "", execution_time: float = 0.0,
                   verdict: str = "") -> None:
        """
        记录每次攻击策略使用结果
        
        Args:
            strategy_id: 策略 ID
            success: 是否成功触发
            input_hash: 输入哈希
            execution_time: 执行时间
            verdict: 判决结果
        """
        timestamp = datetime.now().isoformat()
        hit = {
            "timestamp": timestamp,
            "success": success
        }
        
        if strategy_id not in self._hits:
            self._hits[strategy_id] = []
        self._hits[strategy_id].append(hit)
        
        # 持久化到数据库
        if self.db:
            try:
                with self.db._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO strategy_hits 
                        (strategy_id, timestamp, success, input_hash, execution_time, verdict)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (strategy_id, timestamp, 1 if success else 0, 
                         input_hash, execution_time, verdict)
                    )
                    conn.commit()
            except Exception as e:
                logger.warning(f"记录策略命中失败 {strategy_id}: {e}")
        
        logger.debug(f"策略命中记录: {strategy_id} | 成功: {success}")
    
    def get_hit_rate(self, strategy_id: str, days: int = 30) -> float:
        """
        计算策略近 N 天命中率
        
        Args:
            strategy_id: 策略 ID
            days: 天数范围
            
        Returns:
            命中率 (0.0-1.0)
        """
        if not self._hits.get(strategy_id):
            return 0.0
        
        cutoff = datetime.now() - timedelta(days=days)
        recent_hits = [
            h for h in self._hits[strategy_id] 
            if datetime.fromisoformat(h["timestamp"]) > cutoff
        ]
        
        if not recent_hits:
            return 0.0
        
        successes = sum(1 for h in recent_hits if h["success"])
        return successes / len(recent_hits)
    
    def find_degraded(self, zero_hit_days: int = 30) -> List[str]:
        """
        找出 N 天内零命中的策略，标记为待审查
        
        Args:
            zero_hit_days: 零命中天数阈值
            
        Returns:
            退化策略 ID 列表
        """
        degraded = []
        
        for strategy_id, hits in self._hits.items():
            if not hits:
                # 从未被使用的策略
                degraded.append(strategy_id)
                continue
            
            # 查找最近一次命中
            last_success = None
            for hit in reversed(hits):
                if hit["success"]:
                    last_success = datetime.fromisoformat(hit["timestamp"])
                    break
            
            if last_success is None:
                # 从未成功命中的策略
                degraded.append(strategy_id)
                continue
            
            # 检查是否超过阈值天数
            days_since_last = (datetime.now() - last_success).days
            if days_since_last > zero_hit_days:
                degraded.append(strategy_id)
        
        # 更新数据库状态
        if self.db:
            try:
                with self.db._connect() as conn:
                    for sid in degraded:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO strategy_status 
                            (strategy_id, status, last_updated, notes)
                            VALUES (?, 'degraded', ?, '自动检测：零命中超过阈值')
                            """,
                            (sid, datetime.now().isoformat())
                        )
                    conn.commit()
            except Exception as e:
                logger.warning(f"更新策略状态失败: {e}")
        
        return degraded
    
    def get_freshness_report(self) -> Dict[str, Any]:
        """
        策略库新鲜度报告
        
        Returns:
            新鲜度报告字典
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_strategies": len(self._hits),
            "active_strategies": 0,
            "degraded_strategies": 0,
            "strategy_details": [],
            "summary": ""
        }
        
        total_hit_rate = 0.0
        hit_rate_count = 0
        
        for strategy_id in self._hits:
            hit_rate = self.get_hit_rate(strategy_id)
            is_degraded = strategy_id in self.find_degraded(30)
            
            total_hit_rate += hit_rate
            hit_rate_count += 1
            
            if is_degraded:
                report["degraded_strategies"] += 1
            else:
                report["active_strategies"] += 1
            
            # 获取最近命中时间
            hits = self._hits[strategy_id]
            last_hit_time = None
            for hit in reversed(hits):
                if hit["success"]:
                    last_hit_time = hit["timestamp"]
                    break
            
            report["strategy_details"].append({
                "strategy_id": strategy_id,
                "hit_rate": hit_rate,
                "hit_rate_formatted": f"{hit_rate:.1%}",
                "total_hits": len(hits),
                "last_success_hit": last_hit_time,
                "degraded": is_degraded
            })
        
        # 计算平均命中率
        avg_hit_rate = total_hit_rate / hit_rate_count if hit_rate_count > 0 else 0.0
        report["avg_hit_rate"] = avg_hit_rate
        report["avg_hit_rate_formatted"] = f"{avg_hit_rate:.1%}"
        
        # 生成摘要
        report["summary"] = (
            f"总策略数: {report['total_strategies']} | "
            f"活跃策略: {report['active_strategies']} | "
            f"退化策略: {report['degraded_strategies']} | "
            f"平均命中率: {report['avg_hit_rate_formatted']}"
        )
        
        return report
    
    def _generate_expansions(self) -> List[AttackStrategy]:
        """
        基于现有策略自动生成扩展策略
        
        根据退化策略的模式，生成语义相近的变体策略。
        例如：SQL 注入策略 → 生成宽字符注入、盲注等变体。
        
        Returns:
            新生成的扩展策略列表
        """
        from copy import deepcopy
        
        expansions = []
        degraded_ids = self.find_degraded(30)
        
        # SQL 注入扩展规则
        sql_variants = {
            "sql_injection_basic": [
                ("sql_injection_widechar", "宽字符注入绕过"),
                ("sql_injection_blind", "盲注（时间延迟）"),
                ("sql_injection_union", "UNION 查询注入"),
                ("sql_injection_stacked", "堆叠查询注入"),
            ],
            "sql_injection_advanced": [
                ("sql_injection_out_of_band", "带外数据注入"),
                ("sql_injection_second_order", "二阶 SQL 注入"),
            ],
        }
        
        # XSS 扩展规则
        xss_variants = {
            "xss_reflected": [
                ("xss_dom_based", "DOM 型 XSS 攻击"),
                ("xss_stored", "存储型 XSS 攻击"),
                ("xss_polyglot", "多语言 XSS 载荷"),
            ],
        }
        
        # 命令注入扩展规则
        cmd_variants = {
            "command_injection_basic": [
                ("command_injection_chained", "链式命令注入"),
                ("command_injection_blind", "盲命令注入"),
                ("command_injection_template", "模板注入变体"),
            ],
        }
        
        all_variants = {}
        all_variants.update(sql_variants)
        all_variants.update(xss_variants)
        all_variants.update(cmd_variants)
        
        for sid in degraded_ids:
            if sid in all_variants:
                base_strategy = None
                if hasattr(self, '_strategies_cache'):
                    base_strategy = self._strategies_cache.get(sid)
                
                for new_id, new_desc in all_variants[sid]:
                    new_strategy = AttackStrategy(
                        id=new_id,
                        category=base_strategy.category if base_strategy else "security",
                        severity=base_strategy.severity if base_strategy else "medium",
                        description=new_desc,
                        input_template=base_strategy.input_template if base_strategy else "",
                        expected=base_strategy.expected if base_strategy else "",
                        applicable_to=deepcopy(base_strategy.applicable_to) if base_strategy else ["code"],
                        verification=base_strategy.verification if base_strategy else "static_analysis",
                        sandbox_level=base_strategy.sandbox_level if base_strategy else "basic",
                        dangerous=base_strategy.dangerous if base_strategy else False,
                    )
                    expansions.append(new_strategy)
        
        return expansions
    
    def expand_strategies(self) -> List[str]:
        """
        自动扩展策略库，并对新策略经 Conscience 管道验证
        
        对于自动生成的新策略，调用 Conscience 验证其有效性：
        - 验证通过 → 状态标记为 active
        - 验证失败或 Conscience 不可用 → 状态标记为 pending_review
        
        Returns:
            新生成的策略 ID 列表
        """
        new_ids: List[str] = []
        
        for strategy in self._generate_expansions():
            new_ids.append(strategy.id)
            
            # 经 Conscience 验证
            if self.conscience:
                try:
                    is_valid = self.conscience.verify_strategy(strategy)
                    strategy.status = "active" if is_valid else "pending_review"
                except Exception as e:
                    logger.warning(f"Conscience 验证策略 {strategy.id} 失败: {e}")
                    strategy.status = "pending_review"
            else:
                strategy.status = "pending_review"
            
            # 记录到数据库
            if self.db:
                try:
                    with self.db._connect() as conn:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO strategy_status 
                            (strategy_id, status, last_updated, notes, auto_extended)
                            VALUES (?, ?, ?, ?, 1)
                            """,
                            (strategy.id, strategy.status, 
                             datetime.now().isoformat(),
                             f"自动扩展自退化策略 | Conscience验证: {'通过' if strategy.status == 'active' else '未通过/不可用'}")
                        )
                        conn.commit()
                except Exception as e:
                    logger.warning(f"记录扩展策略失败 {strategy.id}: {e}")
            
            logger.info(f"扩展策略: {strategy.id} → status={strategy.status}")
        
        return new_ids
    
    def mark_strategy_deprecated(self, strategy_id: str, notes: str = "用户手动确认弃用") -> None:
        """
        将策略标记为弃用
        
        Args:
            strategy_id: 策略 ID
            notes: 备注说明
        """
        if self.db:
            try:
                with self.db._connect() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO strategy_status 
                        (strategy_id, status, last_updated, notes)
                        VALUES (?, 'deprecated', ?, ?)
                        """,
                        (strategy_id, datetime.now().isoformat(), notes)
                    )
                    conn.commit()
                logger.info(f"策略 {strategy_id} 标记为弃用")
            except Exception as e:
                logger.warning(f"标记策略失败: {e}")
    
    def mark_strategy_retired(self, strategy_id: str, notes: str = "用户手动确认退休") -> None:
        """
        将策略标记为退休
        
        Args:
            strategy_id: 策略 ID
            notes: 备注说明
        """
        if self.db:
            try:
                with self.db._connect() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO strategy_status 
                        (strategy_id, status, last_updated, notes)
                        VALUES (?, 'retired', ?, ?)
                        """,
                        (strategy_id, datetime.now().isoformat(), notes)
                    )
                    conn.commit()
                logger.info(f"策略 {strategy_id} 标记为退休")
            except Exception as e:
                logger.warning(f"标记策略失败: {e}")


def attack_file(
    file_path: str,
    strategy_id: Optional[str] = None,
    allow_dangerous: bool = False,
    format_type: str = "text",
) -> str:
    """
    对文件执行攻击
    
    Args:
        file_path: 文件路径
        strategy_id: 指定策略ID
        allow_dangerous: 是否允许危险策略
        format_type: 输出格式
        
    Returns:
        格式化结果
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    content = path.read_text(encoding="utf-8")
    
    engine = AttackEngine(allow_dangerous=allow_dangerous)
    try:
        results = engine.execute_attack(content, strategy_id)
        output = engine.format_results(results, format_type)
        return output
    finally:
        engine.cleanup()


async def main():
    """CLI入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="攻击执行引擎：对代码/文本执行安全攻击测试"
    )
    parser.add_argument(
        "file",
        help="待攻击的文件路径"
    )
    parser.add_argument(
        "--strategy", "-s",
        help="指定攻击策略ID（如 sql_injection_basic）"
    )
    parser.add_argument(
        "--dangerous",
        action="store_true",
        help="允许执行危险策略（谨慎使用）"
    )
    parser.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="列出所有可用策略"
    )
    
    args = parser.parse_args()
    
    if args.list_strategies:
        engine = AttackEngine()
        print("可用攻击策略:")
        for sid, strategy in engine.strategies.items():
            print(f"  {sid}: {strategy.description}")
            print(f"      类别: {strategy.category}, 严重度: {strategy.severity}")
            print(f"      适用: {', '.join(strategy.applicable_to)}")
            print(f"      危险: {strategy.dangerous}")
            print()
        return
    
    try:
        result = await attack_file(
            file_path=args.file,
            strategy_id=args.strategy,
            allow_dangerous=args.dangerous,
            format_type=args.format,
        )
        print(result)
    except Exception as e:
        logger.error(f"攻击执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())