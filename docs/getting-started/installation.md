# 安装指南

## 系统要求

!!! info "环境要求"
    - Python 3.8 或更高版本
    - Windows 10/11 (推荐用于QMT集成)
    - macOS / Linux (支持基础功能)

## 安装方式

### 使用 pip 安装

```bash
pip install qka
```

### 使用 uv 安装 (推荐)

```bash
# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建新项目
uv init my-quant-project
cd my-quant-project

# 添加 qka 依赖
uv add qka
```

### 从源码安装

```bash
git clone https://github.com/your-username/qka.git
cd qka
uv sync
uv pip install -e .
```

## 验证安装

创建一个测试文件 `test_install.py`：

```python
import qka
from qka.core.config import config

print(f"QKA 版本: {qka.__version__}")
print(f"配置加载成功: {config.backtest.initial_cash:,}")
print("✅ QKA 安装成功!")
```

运行测试：

```bash
python test_install.py
```

预期输出：
```
QKA 版本: 0.2.0
配置加载成功: 1,000,000
✅ QKA 安装成功!
```

## 可选依赖

### QMT 集成

如果需要使用QMT进行实盘交易，需要安装：

1. **迅投QMT客户端** - [官方下载](https://www.xtquant.com/)
2. **xtquant 库**:
   ```bash
   pip install xtquant
   ```

### 数据源

根据使用的数据源安装对应依赖：

=== "Akshare"
    ```bash
    pip install akshare
    ```

=== "Tushare"
    ```bash
    pip install tushare
    ```

=== "Wind"
    ```bash
    pip install WindPy
    ```

### 可视化增强

```bash
# 交互式图表
pip install plotly

# Jupyter支持
pip install jupyter notebook

# 额外图表库
pip install matplotlib seaborn
```

## 开发环境设置

如果您计划贡献代码或深度定制，建议设置开发环境：

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/qka.git
cd qka
```

### 2. 安装开发依赖

```bash
uv sync --all-extras
```

### 3. 安装预提交钩子

```bash
pre-commit install
```

### 4. 运行测试

```bash
# 运行全部测试
pytest

# 运行特定测试
pytest tests/test_config.py

# 生成覆盖率报告
pytest --cov=qka --cov-report=html
```

### 5. 构建文档

```bash
# 启动文档服务器
mkdocs serve

# 构建静态文档
mkdocs build
```

## 故障排除

### 常见问题

!!! warning "ImportError: No module named 'qka'"
    
    **原因**: QKA 未正确安装
    
    **解决**: 
    ```bash
    pip install --upgrade qka
    # 或
    uv add qka
    ```

!!! warning "xtquant 相关错误"
    
    **原因**: QMT客户端未安装或路径配置错误
    
    **解决**: 
    1. 确保已安装QMT客户端
    2. 检查QMT路径配置
    3. 参考 [QMT配置指南](../user-guide/trading.md#qmt-配置)

!!! warning "数据获取失败"
    
    **原因**: 网络问题或数据源配置错误
    
    **解决**: 
    1. 检查网络连接
    2. 确认数据源API密钥配置
    3. 参考 [数据配置指南](../user-guide/data.md#数据源配置)

### 获取帮助

如果遇到问题，可以通过以下方式获取帮助：

1. **查看文档** - 本文档包含了详细的使用说明
2. **搜索Issues** - [GitHub Issues](https://github.com/your-username/qka/issues)
3. **提交问题** - 如果没有找到解决方案，请提交新的Issue
4. **社区讨论** - [GitHub Discussions](https://github.com/your-username/qka/discussions)

### 版本兼容性

| QKA 版本 | Python 版本 | 主要变化 |
|----------|-------------|----------|
| 0.2.x    | 3.8+       | 配置管理、事件系统 |
| 0.1.x    | 3.8+       | 基础功能 |

---

## 下一步

安装完成后，建议阅读：

- [第一个策略](first-strategy.md) - 创建您的第一个量化策略
- [基础概念](concepts.md) - 了解QKA的核心概念
- [用户指南](../user-guide/data.md) - 深入学习各个功能模块
