cd E:\Code\qka
git add -A
git commit -m "feat: 新增仓位管理模块 SizingAccessor

- qka/core/sizing.py: 挂载在 Strategy.sizing 下
- 支持 fixed_shares/fixed_amount/percent/kelly/atr_risk
- 自动按手（100股）向下取整
- 17 个单元测试，覆盖边界条件
- 更新文档：概念、API、架构图"
git push origin develop
