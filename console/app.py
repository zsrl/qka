"""
QKA Web 控制台后端服务 (Flask Web Console)
"""

import os
import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

from console.engine import (
    get_system_info,
    PRESET_STRATEGIES,
    fetch_market_data,
    generate_simulation_data,
    execute_backtest
)
from console.config import (
    load_config,
    save_config,
    DEFAULT_CONFIG,
    get_config_path
)
from console.stock_pool import (
    load_pool_data,
    get_all_stocks,
    add_or_update_stock,
    move_stock_level,
    delete_stock,
    parse_and_import_text,
    get_pool_statistics
)

# 确保项目根目录在 sys.path 中
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static")
)
CORS(app)


@app.route("/")
@app.route("/overview")
@app.route("/pool")
@app.route("/stock-pool")
@app.route("/strategy")
@app.route("/market")
@app.route("/simulate")
@app.route("/ai")
@app.route("/settings")
def index():
    """控制台独立路由页面入口"""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """获取系统与环境监控状态"""
    info = get_system_info()
    return jsonify({"success": True, "data": info})


@app.route("/api/presets", methods=["GET"])
def api_presets():
    """获取预置量化策略列表"""
    return jsonify({"success": True, "data": list(PRESET_STRATEGIES.values())})


@app.route("/api/market", methods=["GET"])
def api_market():
    """获取标的行情与指标数据 (K线 + Volume + 指标)"""
    symbol = request.args.get("symbol", "000001.SZ")
    source = request.args.get("source", "tickflow")
    adjust = request.args.get("adjust", "qfq")
    start_date = request.args.get("start_date", "2023-01-01")
    end_date = request.args.get("end_date", "2024-12-31")

    data = fetch_market_data(
        symbol=symbol,
        source=source,
        adjust=adjust,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify({"success": True, "data": data})


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """现场合成特定几何特性的模拟行情"""
    body = request.get_json() or {}
    symbol = body.get("symbol", "SIM.A")
    drift = float(body.get("drift", 0.0005))
    reversion = float(body.get("reversion", 0.05))
    vol = float(body.get("vol", 0.015))
    start_price = float(body.get("start_price", 100.0))
    days = int(body.get("days", 250))
    start_date = body.get("start_date", "2024-01-01")

    data = generate_simulation_data(
        symbol=symbol,
        drift=drift,
        reversion=reversion,
        vol=vol,
        start_price=start_price,
        days=days,
        start_date=start_date
    )
    return jsonify({"success": True, "data": data})


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """运行策略回测并返回图表数据与指标"""
    body = request.get_json() or {}
    strategy_code = body.get("code", "")
    symbols = body.get("symbols", ["000001.SZ"])
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",") if s.strip()]

    cash = float(body.get("cash", 200000.0))
    start_date = body.get("start_date", "2023-01-01")
    end_date = body.get("end_date", "2024-12-31")
    benchmark = body.get("benchmark", "000300.SH")
    warmup = int(body.get("warmup", 20))
    factors = body.get("factors", None)

    if not strategy_code.strip():
        return jsonify({"success": False, "error": "策略代码不能为空！"}), 400

    result = execute_backtest(
        strategy_code=strategy_code,
        symbols=symbols,
        cash=cash,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        warmup=warmup,
        factors_dict=factors
    )
    return jsonify(result)


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取系统当前完整配置"""
    conf = load_config()
    return jsonify({
        "success": True,
        "data": conf,
        "config_path": str(get_config_path())
    })


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """保存并应用全局配置"""
    body = request.get_json() or {}
    success = save_config(body)
    if success:
        return jsonify({"success": True, "msg": "配置已成功保存并即时生效！"})
    return jsonify({"success": False, "error": "配置保存失败"}), 500


@app.route("/api/config/reset", methods=["POST"])
def api_reset_config():
    """重置为出厂默认配置"""
    success = save_config(DEFAULT_CONFIG)
    if success:
        return jsonify({"success": True, "data": DEFAULT_CONFIG, "msg": "已成功重置为默认配置！"})
    return jsonify({"success": False, "error": "重置失败"}), 500


@app.route("/api/config/detect_tdx", methods=["GET"])
def api_detect_tdx():
    """自动探测本机通达信客户端安装目录"""
    try:
        from qka.core.tdx import get_tdx_root_info
        info = get_tdx_root_info()
        return jsonify({"success": True, "data": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": {"root": None, "source": None}})


@app.route("/api/config/test_tickflow", methods=["POST"])
def api_test_tickflow():
    """测试 TickFlow API 服务连通性"""
    import urllib.request
    body = request.get_json() or {}
    key = body.get("api_key", "").strip()
    url = "https://api.tickflow.org/v1/health" if key else "https://free-api.tickflow.org/v1/health"

    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            return jsonify({
                "success": True,
                "msg": f"TickFlow 服务连接成功！状态码: {response.status}",
                "mode": "完整专有通道 (api.tickflow.org)" if key else "公共免费通道 (free-api.tickflow.org)"
            })
    except Exception as e:
        return jsonify({"success": False, "error": f"连通失败: {e}"})


# ==========================================
# REST API: Stock Pool Management (股票池管理)
# ==========================================
@app.route("/api/pool/stocks", methods=["GET"])
def api_pool_stocks():
    """获取股票池列表（支持按池层级、赛道板块、关键字筛选）"""
    pool_level = request.args.get("level")
    category = request.args.get("category")
    keyword = request.args.get("keyword")

    stocks = get_all_stocks(pool_level=pool_level, category=category, keyword=keyword)
    return jsonify({"success": True, "data": stocks, "count": len(stocks)})


@app.route("/api/pool/stocks", methods=["POST"])
def api_pool_add_stock():
    """新增或修改股票池中的股票"""
    body = request.get_json() or {}
    success = add_or_update_stock(body)
    if success:
        return jsonify({"success": True, "msg": "股票池标的保存成功！"})
    return jsonify({"success": False, "error": "保存失败，请检查标的代码等必填项"}), 400


@app.route("/api/pool/stocks/<symbol>", methods=["DELETE"])
def api_pool_delete_stock(symbol):
    """从股票池中彻底移除标的"""
    success = delete_stock(symbol)
    if success:
        return jsonify({"success": True, "msg": f"已将 {symbol} 从股票池中移除"})
    return jsonify({"success": False, "error": "删除失败，未找到对应标的"}), 404


@app.route("/api/pool/stocks/move", methods=["POST"])
def api_pool_move_stock():
    """在三级股票池之间流转移动标的 (basic / selected / trading)"""
    body = request.get_json() or {}
    symbol = body.get("symbol")
    target_level = body.get("target_level")

    if not symbol or not target_level:
        return jsonify({"success": False, "error": "缺少 symbol 或 target_level 参数"}), 400

    success = move_stock_level(symbol, target_level)
    level_names = {"basic": "基础股票池", "selected": "精选股票池", "trading": "交易股票池"}
    if success:
        return jsonify({
            "success": True,
            "msg": f"标的 {symbol} 已成功移入 {level_names.get(target_level, target_level)}"
        })
    return jsonify({"success": False, "error": "移动失败，标的不存在或目标层级非法"}), 400


@app.route("/api/pool/import", methods=["POST"])
def api_pool_import():
    """通过研报摘要/微博短文等文本批量解析导入股票池"""
    body = request.get_json() or {}
    text = body.get("text", "").strip()
    level = body.get("level", "basic")
    category = body.get("category", "科技")

    if not text:
        return jsonify({"success": False, "error": "导入文本内容不能为空"}), 400

    result = parse_and_import_text(text, default_level=level, default_category=category)
    return jsonify(result)


@app.route("/api/pool/stats", methods=["GET"])
def api_pool_stats():
    """获取股票池全景统计与盯盘提醒"""
    stats = get_pool_statistics()
    return jsonify({"success": True, "data": stats})


@app.route("/api/pool/categories", methods=["GET"])
def api_pool_categories():
    """获取赛道与板块层级结构"""
    data = load_pool_data()
    return jsonify({"success": True, "data": data.get("categories", [])})


@app.route("/reports/<path:filename>")
def serve_report(filename):
    """访问回测生成的独立 HTML 报告"""
    reports_dir = ROOT_DIR / "reports"
    return send_from_directory(str(reports_dir), filename)


@app.route("/api/cache/clear", methods=["POST"])
def api_clear_cache():
    """清理本地历史缓存"""
    info = get_system_info()
    cache_dir = Path(info["cache_dir"])
    cleared_files = 0
    if cache_dir.exists():
        for f in cache_dir.rglob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    cleared_files += 1
                except Exception:
                    pass
    return jsonify({"success": True, "cleared_files": cleared_files})


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=15002, debug=True)
