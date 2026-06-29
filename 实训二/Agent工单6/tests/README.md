# 测试目录

包含项目的单元测试和集成测试。

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_api.py

# 显示详细输出
pytest -v

# 显示测试覆盖率
pytest --cov=backend --cov=models
```

## 测试文件

- `test_api.py`: API端点测试
- `test_services.py`: 业务逻辑测试
- `test_models.py`: 数据模型测试
