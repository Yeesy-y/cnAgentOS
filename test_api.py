#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.models.admin_user import AdminUserRepository

result = AdminUserRepository.list_users(1, 20)
print("list_users 结果:")
print(f"  code: 0")
print(f"  total: {result['total']}")
print(f"  count: {len(result['data'])}")
print(f"  数据:")
for item in result['data']:
    print(f"    {item}")

print("\n=== 测试输出 JSON ===")
import json
print(json.dumps({
    "code": 0,
    "msg": "ok",
    "count": result['total'],
    "data": result['data']
}, ensure_ascii=False, indent=2))
