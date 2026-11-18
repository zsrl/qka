"""
Unit tests for QKA Web Console and Stock Pool Management
"""
import unittest
import json
from console.app import app
from console.stock_pool import load_pool_data, save_pool_data, parse_and_import_text

class ConsoleStockPoolTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_routes_exist(self):
        for route in ["/", "/overview", "/pool", "/stock-pool", "/strategy", "/market", "/simulate", "/ai", "/settings"]:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed")
            self.assertIn("QKA", resp.get_data(as_text=True))

    def test_pool_categories(self):
        resp = self.client.get("/api/pool/categories")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        cats = [c["name"] for c in data.get("data", [])]
        self.assertIn("科技", cats)
        self.assertIn("消费", cats)
        self.assertIn("周期", cats)
        self.assertIn("大金融", cats)

    def test_pool_stats(self):
        resp = self.client.get("/api/pool/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        stats = data.get("data", {})
        self.assertIn("level_counts", stats)
        self.assertIn("trading", stats["level_counts"])
        self.assertIn("selected", stats["level_counts"])
        self.assertIn("basic", stats["level_counts"])

    def test_stock_crud(self):
        # 1. Add
        test_stock = {
            "symbol": "688012.SH",
            "name": "中微公司",
            "pool_level": "selected",
            "categories": ["科技", "半导体设备"],
            "reason": "刻蚀与薄膜沉积设备领头羊",
            "reports": ["国泰君安-半导体设备深度追踪"],
            "risk_notes": "排查估值偏离与海外供应波动",
            "price": 178.0,
            "change_pct": 3.2,
            "change_3d": 7.5
        }
        resp = self.client.post("/api/pool/stocks", json=test_stock)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get("success"))

        # 2. Query
        resp = self.client.get("/api/pool/stocks?keyword=中微公司")
        self.assertEqual(resp.status_code, 200)
        stocks = resp.get_json().get("data", [])
        self.assertTrue(any(s["symbol"] == "688012.SH" for s in stocks))

        # 3. Move level
        resp = self.client.post("/api/pool/stocks/move", json={"symbol": "688012.SH", "target_level": "trading"})
        self.assertEqual(resp.status_code, 200)

        # 4. Delete
        resp = self.client.delete("/api/pool/stocks/688012.SH")
        self.assertEqual(resp.status_code, 200)

    def test_import_text(self):
        text = "【中金公司算力研报】推荐寒武纪(688256)与中际旭创(300308)。"
        resp = self.client.post("/api/pool/import", json={"text": text, "level": "basic", "category": "科技"})
        self.assertEqual(resp.status_code, 200)
        res = resp.get_json()
        self.assertTrue(res.get("success"))
        self.assertGreaterEqual(res.get("total", 0), 2)

    def test_funnel_hierarchy(self):
        """验证三级包含关系：交易股票池 ⊆ 精选股票池 ⊆ 基础股票池"""
        # 1. 统计接口验证
        resp_stats = self.client.get("/api/pool/stats")
        stats = resp_stats.get_json()["data"]
        counts = stats["level_counts"]

        # 基础股票池数量包含全部标的
        self.assertEqual(counts["basic"], stats["total_stocks"])
        # 精选股票池包含所有交易股: trading <= selected <= basic
        self.assertLessEqual(counts["trading"], counts["selected"])
        self.assertLessEqual(counts["selected"], counts["basic"])

        # 2. 列表查询接口验证包含关系
        resp_trading = self.client.get("/api/pool/stocks?level=trading")
        trading_stocks = resp_trading.get_json()["data"]
        trading_symbols = {s["symbol"] for s in trading_stocks}

        resp_selected = self.client.get("/api/pool/stocks?level=selected")
        selected_stocks = resp_selected.get_json()["data"]
        selected_symbols = {s["symbol"] for s in selected_stocks}

        resp_basic = self.client.get("/api/pool/stocks?level=basic")
        basic_stocks = resp_basic.get_json()["data"]
        basic_symbols = {s["symbol"] for s in basic_stocks}

        # 交易股票池的标的必须全部包含在精选股票池与基础股票池中
        self.assertTrue(trading_symbols.issubset(selected_symbols))
        self.assertTrue(trading_symbols.issubset(basic_symbols))
        # 精选股票池的标的必须全部包含在基础股票池中
        self.assertTrue(selected_symbols.issubset(basic_symbols))

        # 3. 关联打标属性验证
        for s in trading_stocks:
            self.assertTrue(s["in_trading"])
            self.assertTrue(s["in_selected"])
            self.assertTrue(s["in_basic"])
            self.assertIn("trading", s["member_pools"])
            self.assertIn("selected", s["member_pools"])
            self.assertIn("basic", s["member_pools"])

if __name__ == "__main__":
    unittest.main()
