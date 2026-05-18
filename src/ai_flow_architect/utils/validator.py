"""
输入验证器 - 验证和清理输入
"""

from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, validator
from loguru import logger


class ValidationResult(BaseModel):
    """验证结果"""
    is_valid: bool = Field(..., description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
    cleaned_input: Any = Field(None, description="清理后的输入")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class InputValidator:
    """
    输入验证器
    
    用于验证和清理用户输入，确保数据质量
    """
    
    def __init__(self):
        """初始化输入验证器"""
        self.validation_rules = {
            "required_fields": [],
            "max_length": 10000,
            "allowed_characters": None,
            "custom_validators": [],
        }
        
        logger.info("输入验证器初始化完成")
    
    def validate_string(
        self, 
        input_str: str, 
        max_length: int = None,
        min_length: int = 0,
        allow_empty: bool = False
    ) -> ValidationResult:
        """
        验证字符串输入
        
        Args:
            input_str: 输入字符串
            max_length: 最大长度
            min_length: 最小长度
            allow_empty: 是否允许空字符串
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 检查是否为空
        if not input_str or input_str.strip() == "":
            if not allow_empty:
                errors.append("输入不能为空")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                )
        
        # 检查长度
        if max_length and len(input_str) > max_length:
            errors.append(f"输入长度超过限制 ({len(input_str)} > {max_length})")
        
        if len(input_str) < min_length:
            errors.append(f"输入长度不足 ({len(input_str)} < {min_length})")
        
        # 检查特殊字符
        if self._contains_harmful_characters(input_str):
            warnings.append("输入包含特殊字符，已进行清理")
            input_str = self._clean_string(input_str)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=input_str if is_valid else None,
        )
    
    def validate_dict(
        self, 
        input_dict: Dict[str, Any], 
        required_fields: List[str] = None,
        optional_fields: List[str] = None
    ) -> ValidationResult:
        """
        验证字典输入
        
        Args:
            input_dict: 输入字典
            required_fields: 必需字段列表
            optional_fields: 可选字段列表
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        if not isinstance(input_dict, dict):
            errors.append("输入必须是字典类型")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # 检查必需字段
        if required_fields:
            for field in required_fields:
                if field not in input_dict:
                    errors.append(f"缺少必需字段: {field}")
                elif input_dict[field] is None:
                    errors.append(f"字段 '{field}' 不能为空")
        
        # 检查未知字段
        if optional_fields:
            all_allowed = set(required_fields or []) | set(optional_fields)
            unknown_fields = set(input_dict.keys()) - all_allowed
            if unknown_fields:
                warnings.append(f"包含未知字段: {', '.join(unknown_fields)}")
        
        # 清理输入
        cleaned_dict = self._clean_dict(input_dict)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=cleaned_dict if is_valid else None,
        )
    
    def validate_list(
        self, 
        input_list: List[Any], 
        min_items: int = 0,
        max_items: int = None,
        item_validator: callable = None
    ) -> ValidationResult:
        """
        验证列表输入
        
        Args:
            input_list: 输入列表
            min_items: 最小项目数
            max_items: 最大项目数
            item_validator: 项目验证函数
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        if not isinstance(input_list, list):
            errors.append("输入必须是列表类型")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # 检查项目数
        if len(input_list) < min_items:
            errors.append(f"列表项目数不足 ({len(input_list)} < {min_items})")
        
        if max_items and len(input_list) > max_items:
            errors.append(f"列表项目数过多 ({len(input_list)} > {max_items})")
        
        # 验证每个项目
        if item_validator:
            for i, item in enumerate(input_list):
                try:
                    item_result = item_validator(item)
                    if not item_result.is_valid:
                        errors.extend([f"项目 {i}: {err}" for err in item_result.errors])
                except Exception as e:
                    errors.append(f"项目 {i} 验证失败: {str(e)}")
        
        # 清理列表
        cleaned_list = self._clean_list(input_list)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=cleaned_list if is_valid else None,
        )
    
    def validate_email(self, email: str) -> ValidationResult:
        """
        验证邮箱地址
        
        Args:
            email: 邮箱地址
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        if not email:
            errors.append("邮箱地址不能为空")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # 基本格式检查
        if '@' not in email:
            errors.append("邮箱地址格式不正确，缺少@符号")
        elif '.' not in email.split('@')[1]:
            errors.append("邮箱地址格式不正确，域名部分缺少点号")
        
        # 清理邮箱地址
        cleaned_email = email.strip().lower()
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=cleaned_email if is_valid else None,
        )
    
    def validate_url(self, url: str) -> ValidationResult:
        """
        验证URL地址
        
        Args:
            url: URL地址
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        if not url:
            errors.append("URL地址不能为空")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # 基本格式检查
        if not url.startswith(('http://', 'https://')):
            warnings.append("URL缺少协议前缀，已自动添加https://")
            url = 'https://' + url
        
        # 检查域名
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                errors.append("URL格式不正确，缺少域名")
        except Exception:
            errors.append("URL格式不正确")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=url if is_valid else None,
        )
    
    def validate_number(
        self, 
        value: Union[int, float, str], 
        min_value: float = None,
        max_value: float = None,
        allow_float: bool = True
    ) -> ValidationResult:
        """
        验证数字输入
        
        Args:
            value: 输入值
            min_value: 最小值
            max_value: 最大值
            allow_float: 是否允许浮点数
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 尝试转换为数字
        try:
            if isinstance(value, str):
                if allow_float:
                    number = float(value)
                else:
                    number = int(value)
            else:
                number = value
        except (ValueError, TypeError):
            errors.append(f"'{value}' 不是有效的数字")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # 检查范围
        if min_value is not None and number < min_value:
            errors.append(f"数值 {number} 小于最小值 {min_value}")
        
        if max_value is not None and number > max_value:
            errors.append(f"数值 {number} 大于最大值 {max_value}")
        
        # 检查是否为整数
        if not allow_float and isinstance(number, float) and not number.is_integer():
            warnings.append("浮点数已自动转换为整数")
            number = int(number)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=number if is_valid else None,
        )
    
    def _contains_harmful_characters(self, text: str) -> bool:
        """
        检查是否包含有害字符
        
        Args:
            text: 文本内容
            
        Returns:
            是否包含有害字符
        """
        harmful_chars = ['<', '>', '&', '"', "'", '\\', '/', ';', '(', ')']
        return any(char in text for char in harmful_chars)
    
    def _clean_string(self, text: str) -> str:
        """
        清理字符串
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        # 移除或转义特殊字符
        import html
        
        # HTML转义
        cleaned = html.escape(text)
        
        # 移除多余的空白字符
        import re
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _clean_dict(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理字典
        
        Args:
            input_dict: 原始字典
            
        Returns:
            清理后的字典
        """
        cleaned = {}
        
        for key, value in input_dict.items():
            # 清理键
            clean_key = str(key).strip().lower()
            
            # 清理值
            if isinstance(value, str):
                clean_value = self._clean_string(value)
            elif isinstance(value, dict):
                clean_value = self._clean_dict(value)
            elif isinstance(value, list):
                clean_value = self._clean_list(value)
            else:
                clean_value = value
            
            cleaned[clean_key] = clean_value
        
        return cleaned
    
    def _clean_list(self, input_list: List[Any]) -> List[Any]:
        """
        清理列表
        
        Args:
            input_list: 原始列表
            
        Returns:
            清理后的列表
        """
        cleaned = []
        
        for item in input_list:
            if isinstance(item, str):
                clean_item = self._clean_string(item)
            elif isinstance(item, dict):
                clean_item = self._clean_dict(item)
            elif isinstance(item, list):
                clean_item = self._clean_list(item)
            else:
                clean_item = item
            
            cleaned.append(clean_item)
        
        return cleaned
    
    def add_custom_validator(self, name: str, validator_func: callable):
        """
        添加自定义验证器
        
        Args:
            name: 验证器名称
            validator_func: 验证函数
        """
        self.validation_rules["custom_validators"].append({
            "name": name,
            "func": validator_func,
        })
        logger.info(f"添加自定义验证器: {name}")
    
    def validate_with_custom_rules(self, input_data: Any) -> ValidationResult:
        """
        使用自定义规则验证
        
        Args:
            input_data: 输入数据
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        for rule in self.validation_rules["custom_validators"]:
            try:
                result = rule["func"](input_data)
                if not result.get("valid", True):
                    errors.extend(result.get("errors", []))
                    warnings.extend(result.get("warnings", []))
            except Exception as e:
                errors.append(f"验证规则 '{rule['name']}' 执行失败: {str(e)}")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            cleaned_input=input_data if is_valid else None,
        )
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """
        获取验证规则
        
        Returns:
            验证规则字典
        """
        return self.validation_rules.copy()
    
    def set_validation_rules(self, rules: Dict[str, Any]):
        """
        设置验证规则
        
        Args:
            rules: 验证规则字典
        """
        self.validation_rules.update(rules)
        logger.info("更新验证规则")
    
    def reset_rules(self):
        """重置验证规则"""
        self.validation_rules = {
            "required_fields": [],
            "max_length": 10000,
            "allowed_characters": None,
            "custom_validators": [],
        }
        logger.info("重置验证规则")