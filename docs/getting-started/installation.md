# 安装指南

---

## 前置要求

- Python 3.11 或更高版本

---

## 从 PyPI 安装

```bash
pip install qka
```

---

## 从源码安装

```bash
git clone https://github.com/zsrl/qka.git
cd qka
pip install -e .
```

推荐使用 `uv`（更快的包管理器）：

```bash
git clone https://github.com/zsrl/qka.git
cd qka
uv sync          # 安装主依赖
uv sync --extra dev   # 安装开发依赖（测试、文档）
```

---

## 安装验证

```python
import qka
print(qka.__version__)
```

如果能正常导入且不报错，说明安装成功。

---

## 下一步

- 创建你的 [第一个策略](first-strategy.md)
- 了解 [核心概念](concepts.md)
