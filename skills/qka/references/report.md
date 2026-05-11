# Report 模块

回测报告生成。由 `bt.report()` 调用，生成 Plotly HTML 报告。

## 用法

```python
# Backtest 运行后调用
bt.run(benchmark='000300.SH')

# 生成报告
path = bt.report()                             # 默认 ./reports/
path = bt.report(output_path='results.html')   # 指定路径
```

- 返回生成的 HTML 文件路径（str）
- 报告是自包含的 HTML，不需要服务器即可在浏览器打开
- 可在手机端查看

## 报告内容

报告包含以下图表和指标：

1. **累计收益率曲线** — 策略 vs benchmark 累计收益对比
2. **每日收益率柱状图** — 每日盈亏分布
3. **最大回撤曲线** — 回撤深度和持续时间
4. **月度收益率热力图** — 按月份的收益率矩阵
5. **交易记录表** — 逐笔交易明细
6. **换手率**
7. **综合指标面板** — 集成所有关键指标

## 注意事项

- `bt.report()` 必须是在 `bt.run()` 之后调用
- 报告的输出目录由 `output_path` 参数决定
- 默认目录 `./reports/` 不会被 git 跟踪（已在 .gitignore 中）
- 报告的 HTML 文件可分享给其他人查看，无需安装 QKA
