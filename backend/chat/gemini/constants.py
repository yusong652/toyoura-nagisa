"""
Gemini API 常量定义

该模块包含 Gemini API 处理中使用的常量定义，
主要用于过滤 Pydantic 模型的元数据属性以避免弃用警告。
"""

# Pydantic 模型元数据属性集合
# 这些属性在 Pydantic V2.11+ 中被标记为弃用，需要过滤掉以避免警告
PYDANTIC_METADATA_ATTRS = {
    'model_fields',           # 模型字段定义
    'model_computed_fields',  # 计算字段定义
    'model_config',          # 模型配置
    'model_extra',           # 额外字段设置
    'model_fields_set',      # 已设置字段集合
    'model_validator',       # 模型验证器
    'model_construct',       # 模型构造方法
    'model_copy',           # 模型复制方法
    'model_dump',           # 模型导出方法
    'model_dump_json',      # JSON导出方法
    'model_json_schema',    # JSON schema生成
    'model_rebuild',        # 模型重建方法
    'model_validate',       # 模型验证方法
    'model_validate_json',  # JSON验证方法
    'model_validate_strings' # 字符串验证方法
} 