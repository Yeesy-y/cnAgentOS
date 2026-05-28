#!/usr/bin/env python3
"""
更新数据库中的数字员工数据
"""
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

from app.models.db import get_connection


def update_employees():
    """更新数字员工数据"""
    print("开始更新数字员工数据...")
    
    # 定义新的数字员工数据
    new_employees = [
        ("川农小助手", "chuan_nong_xiao_zhu_shou", "川农小助手", 1, "LLM", 
         "负责关于川农的限定范围问题聊天，支持多轮对话", "", 
         "你是四川农业大学的专属数字员工助手——川农小助手。你的任务是回答与四川农业大学（川农）相关的问题，包括但不限于：\n1. 学校历史、校区分布、院系设置\n2. 招生信息、专业介绍、录取分数线\n3. 校园生活、住宿条件、食堂美食\n4. 师资力量、科研成果、学术交流\n5. 校园活动、社团组织、体育赛事\n6. 校园设施、图书馆、实验室等\n\n回答要求：\n- 仅回答与川农相关的问题\n- 如用户问题超出范围，礼貌说明你主要专注于川农相关问题\n- 保持专业、友好、耐心的态度\n- 支持多轮对话，记住之前的上下文\n- 提供准确、实用的信息", 
         "", json.dumps({"use_default_model": True}, ensure_ascii=False), 1),
        ("天气小助手", "weather", "天气小助手", 0, "API", 
         "输入城市名，返回指定城市天气卡片+动态联动的天气特效", "", 
         "", "query_tian", json.dumps({"city_param": "city"}, ensure_ascii=False), 1),
        ("毒鸡汤助手", "poison_chicken_soup", "毒鸡汤助手", 0, "API", 
         "随机回复毒鸡汤语句", "", "", "", json.dumps({}, ensure_ascii=False), 1),
    ]
    
    # 需要删除的旧员工
    old_employee_names = ["川小农", "天气", "毒鸡汤"]
    
    try:
        with get_connection() as conn:
            # 删除旧的数字员工
            for name in old_employee_names:
                conn.execute("DELETE FROM digital_employees WHERE employee_name = ?", (name,))
                print(f"已删除旧数字员工: {name}")
            
            # 插入或更新新的数字员工
            for employee in new_employees:
                (employee_name, employee_code, at_alias, category, service_type, 
                 description, model_code, prompt, api_code, config_json, status) = employee
                
                # 检查是否已存在
                cursor = conn.execute(
                    "SELECT id FROM digital_employees WHERE employee_name = ?",
                    (employee_name,)
                )
                exists = cursor.fetchone()
                
                if exists:
                    # 更新现有记录
                    conn.execute("""
                        UPDATE digital_employees 
                        SET employee_code = ?, at_alias = ?, category = ?, service_type = ?,
                            description = ?, model_code = ?, prompt = ?, api_code = ?,
                            config_json = ?, status = ?
                        WHERE employee_name = ?
                    """, (employee_code, at_alias, category, service_type, description, 
                          model_code, prompt, api_code, config_json, status, employee_name))
                    print(f"已更新数字员工: {employee_name}")
                else:
                    # 插入新记录
                    conn.execute("""
                        INSERT INTO digital_employees 
                        (employee_name, employee_code, at_alias, category, service_type,
                         description, model_code, prompt, api_code, config_json, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, employee)
                    print(f"已插入新数字员工: {employee_name}")
            
            print("\n数字员工数据更新完成！")
            print("\n当前数字员工列表:")
            cursor = conn.execute("SELECT employee_name, service_type, status FROM digital_employees")
            for row in cursor:
                status_str = "启用" if row["status"] == 1 else "禁用"
                print(f"  - {row['employee_name']} ({row['service_type']}) - {status_str}")
                
    except Exception as e:
        print(f"更新失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    update_employees()
