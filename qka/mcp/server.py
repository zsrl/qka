from mcp.server import FastMCP
import pandas as pd
import os
from datetime import datetime

app = FastMCP('qka')

@app.tool()
def query_akshare_data(
        code: str = ''
) -> dict:
    """
    查询akshare数据源数据
    :param code: 查询代码，要求使用akshare库, 要求生成的函数名叫query,返回数据格式为pandas.DataFrame
    :return: 查询结果
    """
    # 创建本地命名空间，预先导入akshare
    local_namespace = {}
    global_namespace = globals().copy()
    
    try:
        # 尝试导入akshare到全局命名空间
        import akshare as ak
        global_namespace['akshare'] = ak
        global_namespace['ak'] = ak
    except ImportError:
        return {"error": "无法导入akshare模块，请确认已正确安装"}
    
    # 执行传入的代码
    try:
        exec(code, global_namespace, local_namespace)
        
        # 检查是否定义了query函数
        if 'query' not in local_namespace or not callable(local_namespace['query']):
            return {"error": "代码中未定义query函数"}
        
        # 执行query函数（不传入参数）
        result = local_namespace['query']()
        
        # 检查返回结果是否为DataFrame
        if not isinstance(result, pd.DataFrame):
            return {"error": "query函数返回的结果不是DataFrame类型"}
        
        # 创建保存目录
        save_dir = r"e:\Code\qka\output"
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data_{timestamp}.csv"
        file_path = os.path.join(save_dir, filename)
        
        # 保存为CSV文件
        result.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        # 将DataFrame转换为字典返回，并包含条数信息和文件路径
        data_dict = result.to_dict(orient="records")
        
        return {
            "message": "数据已成功保存为CSV文件",
            "file_path": file_path,
            "record_count": len(data_dict),
            "data": data_dict[:10] if len(data_dict) > 10 else data_dict  # 只返回前10条预览
        }
    
    except Exception as e:
        return {"error": f"报错后不需要重试，执行代码时发生错误: {str(e)}"}


if __name__ == '__main__':
    app.run(transport='stdio')