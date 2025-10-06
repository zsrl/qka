# 安装指南

## 系统要求

- Python 3.10 或更高版本
- Windows 系统（推荐 Windows 10/11）
- 支持 QMT 交易（可选，用于实盘交易）

## 安装方法

### 从 PyPI 安装（推荐）

```bash
pip install qka
```

### 从源码安装

如果你想使用最新的开发版本，可以从 GitHub 源码安装：

```bash
git clone https://github.com/zsrl/qka.git
cd qka
pip install -e .
```

### 安装开发依赖

如果你想要构建文档或运行测试，可以安装开发依赖：

```bash
pip install qka[dev]
```

## 依赖说明

QKA 依赖于以下主要包：

- **akshare**: 数据获取
- **fastapi**: Web 服务器框架
- **plotly**: 数据可视化
- **pandas**: 数据处理
- **dask**: 并行计算
- **xtquant**: QMT Python 接口

完整的依赖列表请参考 [pyproject.toml](../pyproject.toml)。

## 验证安装

安装完成后，可以通过以下方式验证安装是否成功：

```python
import qka

print(f"QKA 版本: {qka.__version__}")

# 检查核心模块是否可用
try:
    from qka import Data, Backtest, Strategy
    print("核心模块导入成功")
except ImportError as e:
    print(f"导入失败: {e}")
```

## 常见问题

### Q: 安装过程中出现依赖冲突怎么办？

A: 建议使用虚拟环境来避免依赖冲突：

```bash
# 创建虚拟环境
python -m venv qka_env

# 激活虚拟环境（Windows）
qka_env\Scripts\activate

# 安装 QKA
pip install qka
```

### Q: 如何更新到最新版本？

A: 使用 pip 更新：

```bash
pip install --upgrade qka
```

### Q: 安装 xtquant 失败怎么办？

A: xtquant 是 QMT 的 Python 接口，如果你不需要实盘交易功能，可以跳过这个依赖。如果需要，请确保已安装 QMT 并正确配置环境。

## 下一步

安装完成后，建议继续阅读：

- [第一个策略](first-strategy.md) - 学习如何创建你的第一个量化策略
- [基础概念](concepts.md) - 了解 QKA 的核心概念和架构