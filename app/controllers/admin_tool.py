import json
import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection


class AdminToolListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			rows = conn.execute("""
				SELECT * FROM ai_tools ORDER BY id DESC
			""").fetchall()
		
		tools = []
		for row in rows:
			tools.append({
				"id": row["id"],
				"tool_name": row["tool_name"],
				"tool_code": row["tool_code"],
				"description": row["description"] or "",
				"tool_type": row["tool_type"],
				"parameters_json": row["parameters_json"] or "{}",
				"return_schema": row["return_schema"] or "",
				"status": row["status"],
				"create_at": row["create_at"][:19] if row.get("create_at") else ""
			})
		
		self.render(
			"admin_tool_list.html",
			title="工具管理",
			username=self.current_user,
			active_menu="tool",
			tools=tools
		)
	
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "add":
			self._add_tool()
		elif action == "edit":
			self._edit_tool()
		elif action == "delete":
			tool_id_str = self.get_body_argument("tool_id", "")
			if tool_id_str and tool_id_str.isdigit():
				self._delete_tool(int(tool_id_str))
		elif action == "toggle":
			tool_id_str = self.get_body_argument("tool_id", "")
			status = self.get_body_argument("status", "1")
			if tool_id_str and tool_id_str.isdigit():
				self._toggle_tool(int(tool_id_str), status)
		
		return self.redirect("/admin/tool/list")
	
	def _add_tool(self):
		tool_name = (self.get_body_argument("tool_name", "") or "").strip()
		tool_code = (self.get_body_argument("tool_code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		tool_type = self.get_body_argument("tool_type", "function")
		parameters_json = (self.get_body_argument("parameters_json", "{}") or "{}").strip()
		return_schema = (self.get_body_argument("return_schema", "") or "").strip()
		
		if not tool_name or not tool_code:
			return
		
		with get_connection() as conn:
			conn.execute("""
				INSERT INTO ai_tools (tool_name, tool_code, description, tool_type, parameters_json, return_schema)
				VALUES (?, ?, ?, ?, ?, ?)
			""", (tool_name, tool_code, description, tool_type, parameters_json, return_schema))
			conn.commit()
	
	def _edit_tool(self):
		tool_id = int(self.get_body_argument("tool_id", "0"))
		tool_name = (self.get_body_argument("tool_name", "") or "").strip()
		tool_code = (self.get_body_argument("tool_code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		tool_type = self.get_body_argument("tool_type", "function")
		parameters_json = (self.get_body_argument("parameters_json", "{}") or "{}").strip()
		return_schema = (self.get_body_argument("return_schema", "") or "").strip()
		
		if not tool_id or not tool_name or not tool_code:
			return
		
		with get_connection() as conn:
			conn.execute("""
				UPDATE ai_tools
				SET tool_name = ?, tool_code = ?, description = ?, tool_type = ?,
					parameters_json = ?, return_schema = ?
				WHERE id = ?
			""", (tool_name, tool_code, description, tool_type, parameters_json, return_schema, tool_id))
			conn.commit()
	
	def _delete_tool(self, tool_id):
		with get_connection() as conn:
			conn.execute("DELETE FROM employee_tools WHERE tool_id = ?", (tool_id,))
			conn.execute("DELETE FROM ai_tools WHERE id = ?", (tool_id,))
			conn.commit()
	
	def _toggle_tool(self, tool_id, status):
		with get_connection() as conn:
			conn.execute("UPDATE ai_tools SET status = ? WHERE id = ?", (int(status), tool_id))
			conn.commit()


class AdminToolBindHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		employee_id = int(self.get_argument("employee_id", "0"))
		
		if not employee_id:
			return self.write(json.dumps({"success": False, "message": "缺少员工ID"}))
		
		with get_connection() as conn:
			employee = conn.execute("SELECT * FROM digital_employees WHERE id = ?", (employee_id,)).fetchone()
			if not employee:
				return self.write(json.dumps({"success": False, "message": "员工不存在"}))
			
			bound_tools = conn.execute("""
				SELECT t.* FROM ai_tools t
				JOIN employee_tools et ON t.id = et.tool_id
				WHERE et.employee_id = ?
			""", (employee_id,)).fetchall()
			
			all_tools = conn.execute("SELECT * FROM ai_tools WHERE status = 1 ORDER BY id DESC").fetchall()
		
		return self.write(json.dumps({
			"success": True,
			"employee": {
				"id": employee["id"],
				"name": employee["employee_name"]
			},
			"bound_tools": [t["id"] for t in bound_tools],
			"all_tools": [{
				"id": t["id"],
				"tool_name": t["tool_name"],
				"tool_code": t["tool_code"],
				"description": t["description"]
			} for t in all_tools]
		}))
	
	def post(self):
		action = self.get_body_argument("action", "")
		employee_id = int(self.get_body_argument("employee_id", "0"))
		tool_ids = self.get_body_arguments("tool_ids")
		
		if not employee_id:
			return self.write(json.dumps({"success": False, "message": "缺少员工ID"}))
		
		with get_connection() as conn:
			if action == "bind":
				conn.execute("DELETE FROM employee_tools WHERE employee_id = ?", (employee_id,))
				
				for tool_id in tool_ids:
					if tool_id and str(tool_id).isdigit():
						conn.execute("""
							INSERT OR IGNORE INTO employee_tools (employee_id, tool_id)
							VALUES (?, ?)
						""", (employee_id, int(tool_id)))
				
				conn.commit()
				return self.write(json.dumps({"success": True, "message": "绑定成功"}))
		
		return self.write(json.dumps({"success": False, "message": "未知操作"}))