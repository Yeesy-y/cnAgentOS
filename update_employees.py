#!/usr/bin/env python3
"""更新数据库中的数字员工数据"""

import sqlite3
import os
import json
from pathlib import Path

# 数据库路径
_db_path = Path(__file__).parent / "database" / "app.db"

def update_employees():
    """更新数字员工数据"""
    if not _db_path.exists():
        print(f"数据库文件不存在: {_db_path}")
        return False
    
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # 删除旧的数字员工
        conn.execute("DELETE FROM digital_employees WHERE employee_name IN (?, ?, ?)", 
                    ("川小农", "天气", "音乐"))
        
        # 插入新的数字员工
        default_employees = [
            ("川农小助手", "chuan_nong_xiao_zhu_shou", "川农小助手", 1, "LLM", 
             "默认模型 + Prompt 的对话型数字员工", "", 
             "你是数字员工\"川农小助手\"，以中文简洁、专业地回答用户问题。优先给出结论与可执行建议。", 
             "", json.dumps({"use_default_model": True}, ensure_ascii=False), 1),
            ("天气", "weather", "天气", 0, "API", 
             "通过接口管理中的天气API返回天气数据；用户输入为城市名称", "", 
             "", "query_tian", json.dumps({"city_param": "city"}, ensure_ascii=False), 1),
            ("毒鸡汤", "poison_chicken_soup", "毒鸡汤", 0, "API", 
             "发送毒鸡汤内容", "", "", "", json.dumps({}, ensure_ascii=False), 1),
        ]
        
        for employee_name, employee_code, at_alias, category, service_type, description, model_code, prompt, api_code, config_json, status in default_employees:
            conn.execute(
                """
                INSERT OR IGNORE INTO digital_employees(employee_name, employee_code, at_alias, category, service_type, description, model_code, prompt, api_code, config_json, status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (employee_name, employee_code, at_alias, int(category), service_type, description, model_code, prompt, api_code, config_json, int(status))
            )
        
        conn.commit()
        print("数字员工数据更新成功！")
        print("已更新的数字员工：")
        print("- 川农小助手")
        print("- 天气")
        print("- 毒鸡汤")
        return True
        
    except Exception as e:
        print(f"更新失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    update_employees()
