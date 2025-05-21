from mcp.server import FastMCP
from datetime import datetime

mcp = FastMCP("SimpleQuantServer")

@mcp.tool()
def dummy_backtest(
    symbol: str,
    start_date: str,
    end_date: str
) -> dict:
    """
    伪量化回测工具（仅格式化显示输入参数）
    参数示例:
      symbol: "AAPL"
      start_date: "2023-01-01" 
      end_date: "2024-01-01"
    """
    # 生成简易HTML报告
    html = f"""
    <html>
      <head><title>策略参数预览</title></head>
      <body style="font-family: Arial; margin: 20px;">
        <h2>📊 回测参数确认</h2>
        <table border="1" cellpadding="5">
          <tr><th>参数</th><th>值</th></tr>
          <tr><td>股票代码</td><td>{symbol}</td></tr>
          <tr><td>开始日期</td><td>{start_date}</td></tr>
          <tr><td>结束日期</td><td>{end_date}</td></tr>
        </table>
        <p style="color: grey; margin-top: 20px;">
          * 此为演示版本，实际回测功能待实现
        </p>
      </body>
    </html>
    """
    return {
        "要求": "请直接用代码生成并渲染下面data中的html",
        "data": html
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 启动服务