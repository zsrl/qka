"""
QKA 股票池管理模块 (Stock Pool Management)
存储引擎：SQLite 关系型数据库 (stock_pools.db)
核心理念：选赛道、做减法、精选股
三级股票池：基础股票池 -> 精选股票池 -> 交易股票池
行业分类：大金融、消费、周期、科技 及细分赛道
"""

import os
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

DB_FILE = "stock_pools.db"
JSON_LEGACY_FILE = "stock_pools.json"
ROOT_DIR = Path(__file__).resolve().parent.parent

DB_PATH = ROOT_DIR / DB_FILE
LEGACY_JSON_PATH = ROOT_DIR / JSON_LEGACY_FILE

# 默认四大顶层赛道与初始化科技分类
DEFAULT_CATEGORIES = [
    {
        "id": "tech",
        "name": "科技",
        "description": "聚焦人工智能算力、算法、数据、通信、计算机、先进制造与设备",
        "children": [
            {"id": "optical_comm", "name": "光通信", "description": "800G/1.6T高速光模块、光器件、CPO"},
            {"id": "storage", "name": "存储", "description": "DRAM/NAND、HBM高带宽存储、存储主控芯片"},
            {"id": "domestic_compute", "name": "国产算力", "description": "AI服务器、GPU/NPU芯片、算力中心调度"},
            {"id": "power_ai", "name": "电力（AI基建/燃机/发电机/储能）", "description": "AI基建电力支撑、燃气轮机、发电机、电网设备、新型储能"},
            {"id": "new_materials", "name": "新材料", "description": "半导体高阶材料、电子化学品、关键合金材料"},
            {"id": "semiconductor_equip", "name": "半导体设备", "description": "算力细分方向设备、光刻/刻蚀/薄膜沉积设备、光模块精密设备"}
        ]
    },
    {
        "id": "consumption",
        "name": "消费",
        "description": "做减法：必选消费只选创新药，可选消费只选新消费",
        "children": [
            {"id": "innovative_drugs", "name": "创新药", "description": "创新药靶点研发、出海CXO、ADC与生物技术"},
            {"id": "new_consumption", "name": "新消费", "description": "高景气潮流新消费、国货美妆、潮玩出海"}
        ]
    },
    {
        "id": "cyclical",
        "name": "周期",
        "description": "做减法：只选能源金属与战略金属、锂电与储能周期复苏",
        "children": [
            {"id": "energy_metals", "name": "能源金属", "description": "锂、钴、镍等电池关键能源金属"},
            {"id": "strategic_metals", "name": "战略金属", "description": "铜、钼、钨、稀土等稀缺战略储备金属"},
            {"id": "battery_recovery", "name": "锂电储能复苏", "description": "锂电池龙头、固态电池、储能逆变器与集成系统"}
        ]
    },
    {
        "id": "finance",
        "name": "大金融",
        "description": "高股息稳健底仓与资本市场核心枢纽",
        "children": [
            {"id": "bank_high_dividend", "name": "核心银行", "description": "头部商业银行、高股息红利标的"},
            {"id": "insurance_broker", "name": "保险证券", "description": "大型综合保险资产、头部券商"}
        ]
    }
]

# 初始种子股票池（根据用户投资理念构建精选初始标的）
INITIAL_STOCKS = [
    # 科技 - 光通信
    {
        "symbol": "300308.SZ",
        "name": "中际旭创",
        "pool_level": "trading",
        "categories": ["科技", "光通信"],
        "reason": "全球高速光模块领头羊，800G/1.6T需求确定性强，海外顶级算力云客户核心供应商。",
        "reports": ["中信建投-光通信行业深度：全球AI算力集群驱动1.6T放量", "2024Q3业绩预增突破历史新高"],
        "risk_notes": "单日涨幅偏离过大时注意分步止盈，控制回撤。",
        "price": 162.80,
        "change_pct": 3.82,
        "change_3d": 8.45,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "300502.SZ",
        "name": "新易盛",
        "pool_level": "trading",
        "categories": ["科技", "光通信"],
        "reason": "LPO与硅光技术领先，800G交付份额提升，海外云厂商订单饱满。",
        "reports": ["广发证券-新易盛：高速率产品放量加速，海外突破显著"],
        "risk_notes": "警惕短期连续3日冲高后的技术性缩量震荡。",
        "price": 128.50,
        "change_pct": 4.15,
        "change_3d": 7.80,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "300394.SZ",
        "name": "天孚通信",
        "pool_level": "selected",
        "categories": ["科技", "光通信"],
        "reason": "光器件平台型龙头，光引擎技术壁垒极高，配套北美AI算力芯片出货。",
        "reports": ["招商证券-天孚通信：光器件引擎龙头，无源+有源协同释放业绩"],
        "risk_notes": "估值中枢处于历史高位，需紧密跟踪季度业绩兑现度。",
        "price": 96.20,
        "change_pct": 1.85,
        "change_3d": 4.20,
        "updated_at": "2026-10-27"
    },
    # 科技 - 国产算力
    {
        "symbol": "688256.SH",
        "name": "寒武纪",
        "pool_level": "trading",
        "categories": ["科技", "国产算力"],
        "reason": "国产AI训练芯片与大模型推理核心旗舰，自主可控稀缺性极强。",
        "reports": ["中金公司-算力芯片自主可控产业链梳理", "大客户采购意向公告"],
        "risk_notes": "研发投入大、商业化闭环仍在爬坡期，波动率较高，严控单笔仓位。",
        "price": 420.00,
        "change_pct": 5.60,
        "change_3d": 12.30,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "601138.SH",
        "name": "工业富联",
        "pool_level": "basic",
        "categories": ["科技", "国产算力"],
        "reason": "全球AI服务器制造巨头，深度绑定海外头部云厂商，高端算力机柜与液冷协同交付。",
        "reports": ["天风证券-工业富联：AI服务器份额爆发，业绩弹性强"],
        "risk_notes": "",
        "price": 24.50,
        "change_pct": 1.20,
        "change_3d": 2.80,
        "updated_at": "2026-10-27"
    },
    # 科技 - 存储
    {
        "symbol": "688123.SH",
        "name": "聚辰股份",
        "pool_level": "selected",
        "categories": ["科技", "存储"],
        "reason": "内存模组SPD芯片国内龙头，与澜起科技紧密合作，深度受益DDR5渗透率与AI服务器放量。",
        "reports": ["方正证券-聚辰股份：SPD业务迎DDR5黄金期，车载EEPROM放量"],
        "risk_notes": "半导体周期下行时价格承压风险。",
        "price": 64.30,
        "change_pct": 2.10,
        "change_3d": 3.40,
        "updated_at": "2026-10-27"
    },
    # 科技 - 电力 / AI基建
    {
        "symbol": "601728.SH",
        "name": "中国电信",
        "pool_level": "selected",
        "categories": ["科技", "国产算力"],
        "reason": "全国产天翼云底座与息壤智能调度算力平台，AI基建国家队枢纽。",
        "reports": ["申万宏源-三大运营商算力基建深度跟踪"],
        "risk_notes": "公用事业属性高，股息稳健但短期爆发力适中。",
        "price": 6.85,
        "change_pct": 0.44,
        "change_3d": 1.15,
        "updated_at": "2026-10-27"
    },
    # 消费 - 创新药
    {
        "symbol": "600276.SH",
        "name": "恒瑞医药",
        "pool_level": "selected",
        "categories": ["消费", "创新药"],
        "reason": "传统药企创新转型标杆，ADC出海授权不断落地，必选消费景气修复核心龙头。",
        "reports": ["国金证券-恒瑞医药：创新药收入占比过半，海外授权厚积薄发"],
        "risk_notes": "海外临床试验审批不确定性风险。",
        "price": 48.60,
        "change_pct": 1.25,
        "change_3d": 2.10,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "2269.HK",
        "name": "药明生物",
        "pool_level": "basic",
        "categories": ["消费", "创新药"],
        "reason": "全球大分子生物药CRDMO龙头，海外在手订单充足，行业去库存尾声。",
        "reports": ["摩根士丹利-药明生物：海外投产加速，跟随分子商业化"],
        "risk_notes": "地缘政治法案扰动，建议紧密跟踪海外立法进程。",
        "price": 16.40,
        "change_pct": -1.20,
        "change_3d": -2.50,
        "updated_at": "2026-10-27"
    },
    # 周期 - 锂电与储能复苏
    {
        "symbol": "300750.SZ",
        "name": "宁德时代",
        "pool_level": "trading",
        "categories": ["周期", "锂电储能复苏"],
        "reason": "全球动力与储能电池绝对王者，海外市占率创新高，神行超充与麒麟电池排产饱满。",
        "reports": ["东吴证券-宁德时代：海外建厂稳步推进，储能盈利逆势领跑", "三季报毛利率环比提升"],
        "risk_notes": "产能利用率周期波动，关注锂盐原料价格波动。",
        "price": 258.60,
        "change_pct": 2.95,
        "change_3d": 6.10,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "300274.SZ",
        "name": "阳光电源",
        "pool_level": "selected",
        "categories": ["周期", "锂电储能复苏"],
        "reason": "全球光储逆变器出海先锋，大储集成系统海外高毛利订单支撑业绩中枢。",
        "reports": ["长江证券-阳光电源：大储出海全球布局，盈利中枢坚韧"],
        "risk_notes": "海外汇率波动与欧美贸易关税政策风险。",
        "price": 88.90,
        "change_pct": 2.40,
        "change_3d": 5.30,
        "updated_at": "2026-10-27"
    },
    # 周期 - 战略金属
    {
        "symbol": "603993.SH",
        "name": "洛阳钼业",
        "pool_level": "trading",
        "categories": ["周期", "战略金属"],
        "reason": "全球铜钴战略资源巨头，TFM/KFM两大矿区放量，受益全球电网改造与AI数据中心铜需求爆发。",
        "reports": ["中信证券-洛阳钼业：铜钴双轮驱动，降本增效成果显著"],
        "risk_notes": "大宗商品国际价格波动，大涨分步止盈，大跌分步低吸。",
        "price": 8.75,
        "change_pct": 3.10,
        "change_3d": 4.80,
        "updated_at": "2026-10-27"
    },
    {
        "symbol": "601899.SH",
        "name": "紫金矿业",
        "pool_level": "selected",
        "categories": ["周期", "战略金属"],
        "reason": "矿业跨国龙头，金铜双轮驱动，资源储备丰富，逆周期并购整合能力突出。",
        "reports": ["天风证券-紫金矿业：全球化战略步入收获期，金铜产量持续爬坡"],
        "risk_notes": "海外矿山运营地缘政策风险。",
        "price": 17.60,
        "change_pct": 1.30,
        "change_3d": 3.20,
        "updated_at": "2026-10-27"
    },
    # 大金融 - 核心银行
    {
        "symbol": "600036.SH",
        "name": "招商银行",
        "pool_level": "basic",
        "categories": ["大金融", "核心银行"],
        "reason": "零售之王，高股息资产，资产质量与拨备覆盖率扎实，震荡市防御压舱石。",
        "reports": ["平安证券-招商银行：零售资产重塑韧性，股息率具备坚挺吸引力"],
        "risk_notes": "",
        "price": 38.20,
        "change_pct": 0.52,
        "change_3d": 0.90,
        "updated_at": "2026-10-27"
    }
]


@contextmanager
def get_db_connection():
    """获取 SQLite 数据库连接上下文管理器，自动管理提交与关闭"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化 SQLite 数据库表结构，并在初次运行时自动从 JSON 或种子数据迁移"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. 股票标的表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pool_level TEXT NOT NULL DEFAULT 'basic',
                categories_json TEXT NOT NULL DEFAULT '[]',
                reason TEXT,
                reports_json TEXT NOT NULL DEFAULT '[]',
                risk_notes TEXT,
                price REAL DEFAULT 0.0,
                change_pct REAL DEFAULT 0.0,
                change_3d REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_level ON stocks(pool_level);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_updated ON stocks(updated_at);")

        # 2. 赛道与板块结构表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                children_json TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER DEFAULT 0
            );
        """)

        # 3. 元信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        conn.commit()

        # 检查是否需要初始化迁移数据
        cursor.execute("SELECT COUNT(*) as cnt FROM stocks")
        count = cursor.fetchone()["cnt"]

        if count == 0:
            print("[INFO] 股票池 SQLite 数据库初次初始化，正在导入初始数据...")
            categories_to_seed = DEFAULT_CATEGORIES
            stocks_to_seed = INITIAL_STOCKS
            last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 优先从现有的 stock_pools.json 继承历史数据
            if LEGACY_JSON_PATH.exists():
                try:
                    with open(LEGACY_JSON_PATH, "r", encoding="utf-8") as f:
                        legacy_data = json.load(f)
                        if legacy_data.get("stocks"):
                            stocks_to_seed = legacy_data["stocks"]
                        if legacy_data.get("categories"):
                            categories_to_seed = legacy_data["categories"]
                        if legacy_data.get("last_updated"):
                            last_updated = legacy_data["last_updated"]
                    print(f"[INFO] 成功从 {JSON_LEGACY_FILE} 迁移 {len(stocks_to_seed)} 只标的至 SQLite 数据库！")
                except Exception as e:
                    print(f"[WARN] 读取遗留 JSON 失败: {e}，使用初始种子数据")

            # 插入 categories
            for idx, cat in enumerate(categories_to_seed):
                cursor.execute("""
                    INSERT OR REPLACE INTO categories (id, name, description, children_json, sort_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    cat.get("id"),
                    cat.get("name"),
                    cat.get("description", ""),
                    json.dumps(cat.get("children", []), ensure_ascii=False),
                    idx
                ))

            # 插入 stocks
            for s in stocks_to_seed:
                cursor.execute("""
                    INSERT OR REPLACE INTO stocks (
                        symbol, name, pool_level, categories_json, reason,
                        reports_json, risk_notes, price, change_pct, change_3d, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.get("symbol"),
                    s.get("name"),
                    s.get("pool_level", "basic"),
                    json.dumps(s.get("categories", []), ensure_ascii=False),
                    s.get("reason", ""),
                    json.dumps(s.get("reports", []), ensure_ascii=False),
                    s.get("risk_notes", ""),
                    float(s.get("price") or 0.0),
                    float(s.get("change_pct") or 0.0),
                    float(s.get("change_3d") or 0.0),
                    s.get("updated_at", datetime.now().strftime("%Y-%m-%d"))
                ))

            # 插入 meta
            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)", (last_updated,))
            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('version', '1.0.0')")

            conn.commit()


# 初始化数据库
init_db()


def _row_to_stock_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    将 SQLite row 映射为 Python 字典格式，并计算三级包含关系打标：
    交易股票池 ⊆ 精选股票池 ⊆ 基础股票池
    """
    categories = []
    try:
        categories = json.loads(row["categories_json"]) if row["categories_json"] else []
    except Exception:
        pass

    reports = []
    try:
        reports = json.loads(row["reports_json"]) if row["reports_json"] else []
    except Exception:
        pass

    lvl = row["pool_level"] or "basic"

    # 三级层级严格包含关系：
    # 1. 交易股票池的票一定在基础股票池和精选股票池
    # 2. 精选股票池的票同时一定在基础股票池
    # 3. 基础股票池包含所有的精选股与交易股
    in_trading = (lvl == "trading")
    in_selected = (lvl in ["selected", "trading"])
    in_basic = True

    member_pools = ["basic"]
    if in_selected:
        member_pools.append("selected")
    if in_trading:
        member_pools.append("trading")

    return {
        "symbol": row["symbol"],
        "name": row["name"],
        "pool_level": lvl,
        "in_basic": in_basic,
        "in_selected": in_selected,
        "in_trading": in_trading,
        "member_pools": member_pools,
        "categories": categories,
        "reason": row["reason"] or "",
        "reports": reports,
        "risk_notes": row["risk_notes"] or "",
        "price": row["price"],
        "change_pct": row["change_pct"],
        "change_3d": row["change_3d"],
        "updated_at": row["updated_at"] or ""
    }


def load_pool_data() -> Dict[str, Any]:
    """加载股票池与分类数据（提供向后兼容数据契约）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 加载分类
        cursor.execute("SELECT id, name, description, children_json FROM categories ORDER BY sort_order ASC")
        categories = []
        for r in cursor.fetchall():
            children = []
            try:
                children = json.loads(r["children_json"]) if r["children_json"] else []
            except Exception:
                pass
            categories.append({
                "id": r["id"],
                "name": r["name"],
                "description": r["description"] or "",
                "children": children
            })

        # 加载标的
        cursor.execute("""
            SELECT symbol, name, pool_level, categories_json, reason, reports_json, risk_notes, price, change_pct, change_3d, updated_at
            FROM stocks
            ORDER BY CASE pool_level WHEN 'trading' THEN 1 WHEN 'selected' THEN 2 ELSE 3 END, updated_at DESC
        """)
        stocks = [_row_to_stock_dict(r) for r in cursor.fetchall()]

        # 获取最后更新时间
        cursor.execute("SELECT value FROM meta WHERE key = 'last_updated'")
        meta_row = cursor.fetchone()
        last_updated = meta_row["value"] if meta_row else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "categories": categories,
        "stocks": stocks,
        "last_updated": last_updated
    }


def save_pool_data(data: Dict[str, Any]) -> bool:
    """持久化保存股票池数据至 SQLite"""
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)", (now_str,))

            # 批量写入 stocks（如果提供）
            if "stocks" in data:
                for s in data["stocks"]:
                    cursor.execute("""
                        INSERT OR REPLACE INTO stocks (
                            symbol, name, pool_level, categories_json, reason,
                            reports_json, risk_notes, price, change_pct, change_3d, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        s.get("symbol"),
                        s.get("name"),
                        s.get("pool_level", "basic"),
                        json.dumps(s.get("categories", []), ensure_ascii=False),
                        s.get("reason", ""),
                        json.dumps(s.get("reports", []), ensure_ascii=False),
                        s.get("risk_notes", ""),
                        float(s.get("price") or 0.0),
                        float(s.get("change_pct") or 0.0),
                        float(s.get("change_3d") or 0.0),
                        s.get("updated_at", datetime.now().strftime("%Y-%m-%d"))
                    ))

            conn.commit()
        return True
    except Exception as e:
        print(f"[ERROR] 保存股票池至 SQLite 失败: {e}")
        return False


def get_all_stocks(pool_level: Optional[str] = None, category: Optional[str] = None, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    高效查询股票列表
    层级包含关系逻辑：
    - trading: 仅查询交易股票池标的 (pool_level = 'trading')
    - selected: 查询精选股票池标的（包含所有交易股：pool_level IN ('selected', 'trading')）
    - basic: 查询基础股票池标的（包含所有标的：所有交易股与精选股均在基础池）
    - basic_only: 仅处于基础池尚未进入精选池的标的
    """
    sql = """
        SELECT symbol, name, pool_level, categories_json, reason, reports_json, risk_notes, price, change_pct, change_3d, updated_at
        FROM stocks
        WHERE 1=1
    """
    params: List[Any] = []

    if pool_level and pool_level != "all":
        if pool_level == "trading":
            sql += " AND pool_level = 'trading'"
        elif pool_level == "selected":
            sql += " AND pool_level IN ('selected', 'trading')"
        elif pool_level == "basic_only":
            sql += " AND pool_level = 'basic'"
        elif pool_level == "basic":
            # 基础股票池包含所有的精选股与交易股 (全量标的)
            pass
        else:
            sql += " AND pool_level = ?"
            params.append(pool_level)

    if keyword:
        kw = f"%{keyword.strip()}%"
        sql += " AND (symbol LIKE ? OR name LIKE ? OR reason LIKE ?)"
        params.extend([kw, kw, kw])

    sql += " ORDER BY CASE pool_level WHEN 'trading' THEN 1 WHEN 'selected' THEN 2 ELSE 3 END, updated_at DESC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        raw_rows = cursor.fetchall()

    results = []
    for r in raw_rows:
        stock = _row_to_stock_dict(r)
        if category and category != "all":
            cats = stock.get("categories", [])
            if category not in cats and not any(category in c for c in cats):
                continue
        results.append(stock)

    return results


def add_or_update_stock(stock_dict: Dict[str, Any]) -> bool:
    """新增或修改股票池中的股票"""
    symbol = stock_dict.get("symbol", "").strip().upper()
    if not symbol:
        return False

    name = stock_dict.get("name", "").strip() or symbol
    pool_level = stock_dict.get("pool_level", "basic")
    categories = stock_dict.get("categories", ["科技"])
    reason = stock_dict.get("reason", "")
    reports = stock_dict.get("reports", [])
    risk_notes = stock_dict.get("risk_notes", "")
    price = float(stock_dict.get("price") or 0.0)
    change_pct = float(stock_dict.get("change_pct") or 0.0)
    change_3d = float(stock_dict.get("change_3d") or 0.0)
    now_date = datetime.now().strftime("%Y-%m-%d")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stocks (
                    symbol, name, pool_level, categories_json, reason,
                    reports_json, risk_notes, price, change_pct, change_3d, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    pool_level = excluded.pool_level,
                    categories_json = excluded.categories_json,
                    reason = excluded.reason,
                    reports_json = excluded.reports_json,
                    risk_notes = excluded.risk_notes,
                    price = excluded.price,
                    change_pct = excluded.change_pct,
                    change_3d = excluded.change_3d,
                    updated_at = excluded.updated_at
            """, (
                symbol,
                name,
                pool_level,
                json.dumps(categories, ensure_ascii=False),
                reason,
                json.dumps(reports, ensure_ascii=False),
                risk_notes,
                price,
                change_pct,
                change_3d,
                now_date
            ))

            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)", (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"[ERROR] 写入 SQLite 标的失败: {e}")
        return False


def move_stock_level(symbol: str, target_level: str) -> bool:
    """调整股票所在池层级 (basic -> selected -> trading)"""
    if target_level not in ["basic", "selected", "trading"]:
        return False

    now_date = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE stocks
            SET pool_level = ?, updated_at = ?
            WHERE symbol = ?
        """, (target_level, now_date, symbol))

        if cursor.rowcount > 0:
            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)", (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()
            return True
    return False


def delete_stock(symbol: str) -> bool:
    """从股票池中彻底删除标的"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stocks WHERE symbol = ?", (symbol,))
        if cursor.rowcount > 0:
            cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_updated', ?)", (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()
            return True
    return False


def parse_and_import_text(text: str, default_level: str = "basic", default_category: str = "科技") -> Dict[str, Any]:
    """
    通过研报文本、微博短文或列表智能解析并批量导入基础股票池
    识别股票代码 (如 000001.SZ, 600519.SH, 300750) 与标的中文简称
    """
    pattern = re.compile(r'([036][0-9]{5}(?:\.[Ss][ZzHh])?|[036][0-9]{5})')

    imported_stocks = []
    updated_stocks = []
    now_date = datetime.now().strftime("%Y-%m-%d")

    # 获取已有的所有股票映射
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, name, categories_json, reports_json, pool_level FROM stocks")
        existing_symbols = {r["symbol"]: dict(r) for r in cursor.fetchall()}

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for line in lines:
        line_matches = pattern.findall(line)
        for raw_code in line_matches:
            # 补全 .SZ / .SH
            code = raw_code.upper()
            if "." not in code:
                if code.startswith(("60", "68")):
                    code += ".SH"
                elif code.startswith(("00", "30")):
                    code += ".SZ"
                else:
                    code += ".SZ"

            # 提取中文名称：优先寻找括号前或紧邻代码的2~6个中文字符
            name_match = re.search(r'([\u4e00-\u9fa5]{2,6})[\(（]' + re.escape(raw_code), line)
            if not name_match:
                name_match = re.search(r'([\u4e00-\u9fa5]{2,6})\s*' + re.escape(raw_code), line)
            if not name_match:
                name_match = re.search(re.escape(raw_code) + r'[\)）\s]*([\u4e00-\u9fa5]{2,6})', line)

            name = name_match.group(1) if name_match else ""

            # 清理整行作为研报或核心逻辑
            clean_reason = re.sub(r'[\(（]' + re.escape(raw_code) + r'[\)）]', '', line)
            clean_reason = clean_reason.replace(raw_code, '').strip('【】[](),.，。；; ')

            if code in existing_symbols:
                s = existing_symbols[code]
                stock_name = s.get("name")
                if name and (not stock_name or stock_name == "自选标的" or stock_name.startswith("【")):
                    stock_name = name

                reports = []
                try:
                    reports = json.loads(s.get("reports_json") or "[]")
                except Exception:
                    pass

                if clean_reason and line not in reports:
                    reports.insert(0, line)
                reports = reports[:5]

                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE stocks
                        SET name = ?, reports_json = ?, updated_at = ?
                        WHERE symbol = ?
                    """, (stock_name, json.dumps(reports, ensure_ascii=False), now_date, code))
                    conn.commit()

                updated_stocks.append({
                    "symbol": code,
                    "name": stock_name,
                    "pool_level": s.get("pool_level", default_level),
                    "categories": json.loads(s.get("categories_json") or "[]")
                })
            else:
                stock_name = name or "自选标的"
                new_item = {
                    "symbol": code,
                    "name": stock_name,
                    "pool_level": default_level,
                    "categories": [default_category],
                    "reason": clean_reason or "研报推荐/每日功课笔记导入",
                    "reports": [line] if line != code else [],
                    "risk_notes": "",
                    "price": 0.0,
                    "change_pct": 0.0,
                    "change_3d": 0.0,
                    "updated_at": now_date
                }
                add_or_update_stock(new_item)
                existing_symbols[code] = new_item
                imported_stocks.append(new_item)

    all_processed = imported_stocks + updated_stocks
    return {
        "success": True,
        "imported_count": len(imported_stocks),
        "updated_count": len(updated_stocks),
        "total": len(all_processed),
        "stocks": all_processed
    }


def get_pool_statistics() -> Dict[str, Any]:
    """统计股票池各层级分布、赛道行业分布、盯盘异动预警"""
    pool_data = load_pool_data()
    stocks = pool_data.get("stocks", [])

    # 1. 三级池分布（层级严格包含关系：交易股票池 ⊆ 精选股票池 ⊆ 基础股票池）
    # 基础股票池：包含所有的精选股、交易股（全量标的）
    # 精选股票池：包含精选股 + 交易股
    # 交易股票池：包含交易股
    trading_count = sum(1 for s in stocks if s.get("in_trading"))
    selected_count = sum(1 for s in stocks if s.get("in_selected"))
    basic_count = len(stocks)

    level_counts = {
        "basic": basic_count,
        "selected": selected_count,
        "trading": trading_count,
        "exclusive": {
            "trading": trading_count,
            "selected_only": sum(1 for s in stocks if s.get("pool_level") == "selected"),
            "basic_only": sum(1 for s in stocks if s.get("pool_level") == "basic")
        }
    }

    # 2. 赛道分布
    category_counts: Dict[str, int] = {}
    # 3. 交易盯盘提示（如：大涨止盈预警、大跌低吸机会）
    take_profit_alerts = []  # 连涨超额，提示分步止盈
    dip_buying_alerts = []   # 优质标的大跌，提示分步低吸

    for s in stocks:
        lvl = s.get("pool_level", "basic")

        cats = s.get("categories", ["未分类"])
        for c in cats:
            category_counts[c] = category_counts.get(c, 0) + 1

        # 盯盘监控逻辑
        chg = s.get("change_pct", 0.0)
        chg_3d = s.get("change_3d", 0.0)
        sym = s.get("symbol", "")
        name = s.get("name", "")

        # 止盈提醒：单日涨幅 > 5% 或 3日累涨 > 10%
        if chg >= 5.0 or chg_3d >= 10.0:
            take_profit_alerts.append({
                "symbol": sym,
                "name": name,
                "pool_level": lvl,
                "change_pct": chg,
                "change_3d": chg_3d,
                "reason": f"近3日累涨 {chg_3d:+.2f}%，单日涨幅 {chg:+.2f}%，触发高位偏离，建议分步止盈积累收益。"
            })
        # 低吸提醒：3日回调 > 4% 且属于交易池或精选池
        elif chg_3d <= -4.0 and s.get("in_selected"):
            dip_buying_alerts.append({
                "symbol": sym,
                "name": name,
                "pool_level": lvl,
                "change_pct": chg,
                "change_3d": chg_3d,
                "reason": f"核心赛道优质标的近3日回调 {chg_3d:+.2f}%，长线逻辑不变，符合看长做短、大跌分步低吸策略。"
            })

    return {
        "total_stocks": len(stocks),
        "level_counts": level_counts,
        "category_counts": category_counts,
        "take_profit_alerts": take_profit_alerts,
        "dip_buying_alerts": dip_buying_alerts,
        "last_updated": pool_data.get("last_updated", "")
    }
