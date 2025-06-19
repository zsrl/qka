# 开发指南

QKA量化回测系统的开发文档和贡献指南。

## 目录

### [架构设计](architecture.md)
- 系统架构概述
- 模块设计原则
- 接口规范
- 扩展机制

### [开发环境](development-setup.md)
- 环境搭建
- 依赖管理
- 开发工具配置
- 调试技巧

### [编码规范](coding-standards.md)
- Python代码规范
- 文档编写规范
- 测试规范
- 版本控制规范

### [API设计](api-design.md)
- API设计原则
- 接口约定
- 错误处理
- 版本管理

### [测试指南](testing.md)
- 单元测试
- 集成测试
- 性能测试
- 测试覆盖率

### [部署指南](deployment.md)
- 本地部署
- 生产环境部署
- Docker容器化
- CI/CD流水线

### [贡献指南](contributing.md)
- 如何贡献代码
- 提交规范
- Code Review流程
- 社区规则

## 快速开始

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/your-repo/qka.git
cd qka

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 启动开发服务器
python -m qka.dev server
```

### 项目结构

```
qka/
├── qka/                    # 主要源代码
│   ├── core/              # 核心模块
│   ├── utils/             # 工具模块
│   ├── brokers/           # 交易接口
│   └── mcp/               # MCP协议
├── tests/                 # 测试代码
├── docs/                  # 文档
├── examples/              # 示例代码
├── scripts/               # 脚本工具
└── requirements/          # 依赖文件
```

## 开发工作流

### 1. 功能开发

```bash
# 创建功能分支
git checkout -b feature/new-feature

# 开发代码
# ... 编写代码 ...

# 运行测试
pytest tests/

# 提交代码
git add .
git commit -m "feat: 添加新功能"

# 推送分支
git push origin feature/new-feature
```

### 2. 代码审查

- 创建 Pull Request
- 等待 Code Review
- 根据反馈修改代码
- 合并到主分支

### 3. 发布流程

```bash
# 更新版本号
bump2version minor  # 或 major, patch

# 创建发布标签
git tag v1.1.0

# 推送标签
git push origin v1.1.0

# 构建和发布
python setup.py sdist bdist_wheel
twine upload dist/*
```

## 核心概念

### 模块化设计

QKA采用模块化设计，每个模块都有明确的职责：

- **Core** - 核心功能（配置、事件、回测）
- **Utils** - 通用工具（日志、缓存、格式化）
- **Brokers** - 交易接口（客户端、服务器、执行）
- **MCP** - AI模型接口（协议、服务器）

### 事件驱动架构

系统采用事件驱动架构，通过事件总线连接各个组件：

```python
# 事件发布
bus.publish(MarketDataEvent(symbol='AAPL', price=150.0))

# 事件订阅
@bus.subscribe('market_data')
def handle_market_data(event):
    # 处理市场数据
    pass
```

### 插件系统

支持通过插件扩展系统功能：

```python
from qka.core import PluginManager

# 注册插件
@PluginManager.register('data_source')
class MyDataSource:
    def get_data(self, symbol):
        return data
```

## 性能考虑

### 性能优化原则

1. **缓存优先** - 缓存计算结果和数据
2. **异步处理** - 使用异步处理I/O密集型任务
3. **批量操作** - 批量处理数据减少开销
4. **内存管理** - 及时释放不需要的对象

### 性能监控

```python
from qka.utils.tools import timeit, monitor_memory

@timeit
@monitor_memory
def expensive_function():
    # 耗时函数
    pass
```

## 安全考虑

### 数据安全

- 敏感配置使用环境变量
- API密钥加密存储
- 数据传输使用HTTPS

### 代码安全

- 输入验证和清洗
- SQL注入防护
- 权限控制

```python
from qka.utils.tools import ValidationHelper

validator = ValidationHelper()

# 验证输入
if not validator.validate_symbol(symbol):
    raise ValueError("无效的股票代码")
```

## 文档贡献

### 文档编写

- 使用Markdown格式
- 包含代码示例
- 提供清晰的说明

### API文档

API文档使用mkdocstrings自动生成：

```python
def my_function(param1: str, param2: int = 10) -> str:
    """
    函数描述
    
    Args:
        param1: 参数1描述
        param2: 参数2描述，默认值为10
        
    Returns:
        返回值描述
        
    Examples:
        >>> result = my_function("test", 20)
        >>> print(result)
        "test result"
    """
    return f"{param1} result"
```

### 文档构建

```bash
# 本地构建文档
mkdocs serve

# 部署文档
mkdocs gh-deploy
```

## 质量保证

### 代码质量工具

```bash
# 代码格式化
black qka/
isort qka/

# 代码检查
flake8 qka/
pylint qka/

# 类型检查
mypy qka/

# 安全检查
bandit -r qka/
```

### 测试覆盖率

```bash
# 运行测试并生成覆盖率报告
pytest --cov=qka tests/

# 生成HTML报告
pytest --cov=qka --cov-report=html tests/
```

## 社区参与

### 报告问题

- 使用GitHub Issues报告bug
- 提供详细的复现步骤
- 包含环境信息

### 提出建议

- 在GitHub Discussions讨论新功能
- 提供详细的用例说明
- 考虑实现的复杂度

### 参与讨论

- 加入开发者群组
- 参与技术讨论
- 分享使用经验

更多详细信息请参考各个子页面的具体说明。
