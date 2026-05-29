import json
import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection


class AdminGroupListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		keyword = (self.get_argument("keyword", "") or "").strip()
		page_size = 20
		
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) as cnt FROM groups WHERE name LIKE ?",
					(f"%{keyword}%",)
				).fetchone()
				total = count_row["cnt"] if count_row else 0
				
				offset = (page - 1) * page_size
				rows = conn.execute("""
					SELECT g.*, u.username as creator_name,
						(SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count,
						(SELECT COUNT(*) FROM group_employees WHERE group_id = g.id) as employee_count
					FROM groups g
					LEFT JOIN users u ON g.creator_id = u.id
					WHERE g.name LIKE ?
					ORDER BY g.created_at DESC
					LIMIT ? OFFSET ?
				""", (f"%{keyword}%", page_size, offset)).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) as cnt FROM groups").fetchone()
				total = count_row["cnt"] if count_row else 0
				
				offset = (page - 1) * page_size
				rows = conn.execute("""
					SELECT g.*, u.username as creator_name,
						(SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count,
						(SELECT COUNT(*) FROM group_employees WHERE group_id = g.id) as employee_count
					FROM groups g
					LEFT JOIN users u ON g.creator_id = u.id
					ORDER BY g.created_at DESC
					LIMIT ? OFFSET ?
				""", (page_size, offset)).fetchall()
		
		groups = []
		for row in rows:
			groups.append({
				"id": row["id"],
				"name": row["name"],
				"creator_name": row["creator_name"] or "未知",
				"member_count": row["member_count"],
				"employee_count": row["employee_count"],
				"status": row["status"] if "status" in row else "normal",
				"created_at": row["created_at"][:19] if "created_at" in row and row["created_at"] else ""
			})
		
		self.render(
			"admin_group_list.html",
			title="群聊管理",
			username=self.current_user,
			active_menu="group",
			groups=groups,
			total=total,
			page=page,
			page_size=page_size,
			keyword=keyword
		)
	
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "delete":
			group_id_str = self.get_body_argument("group_id", "")
			if group_id_str and group_id_str.isdigit():
				self._delete_group(int(group_id_str))
		elif action == "ban":
			group_id_str = self.get_body_argument("group_id", "")
			if group_id_str and group_id_str.isdigit():
				self._update_status(int(group_id_str), "banned")
		elif action == "unban":
			group_id_str = self.get_body_argument("group_id", "")
			if group_id_str and group_id_str.isdigit():
				self._update_status(int(group_id_str), "normal")
		elif action == "notice":
			group_id_str = self.get_body_argument("group_id", "")
			notice = self.get_body_argument("notice", "").strip()
			if group_id_str and group_id_str.isdigit():
				self._send_notice(int(group_id_str), notice)
		
		return self.redirect("/admin/group/list")
	
	def _delete_group(self, group_id):
		with get_connection() as conn:
			conn.execute("DELETE FROM group_employees WHERE group_id = ?", (group_id,))
			conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
			conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
			conn.commit()
	
	def _update_status(self, group_id, status):
		with get_connection() as conn:
			conn.execute("UPDATE groups SET status = ? WHERE id = ?", (status, group_id))
			conn.commit()
	
	def _send_notice(self, group_id, notice):
		with get_connection() as conn:
			conn.execute("UPDATE groups SET notice = ?, notice_at = datetime('now') WHERE id = ?", (notice, group_id))
			conn.commit()


class AdminGroupDetailHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		group_id = int(self.get_argument("group_id", "0"))
		
		if not group_id:
			return self.redirect("/admin/group/list")
		
		with get_connection() as conn:
			group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
			
			user_rows = conn.execute("""
				SELECT u.id, u.username, gm.joined_at
				FROM group_members gm
				JOIN users u ON gm.user_id = u.id
				WHERE gm.group_id = ?
			""", (group_id,)).fetchall()
			
			employee_rows = conn.execute("""
				SELECT de.id, de.employee_name, de.at_alias, ge.added_at
				FROM group_employees ge
				JOIN digital_employees de ON ge.employee_id = de.id
				WHERE ge.group_id = ?
			""", (group_id,)).fetchall()
		
		if not group:
			return self.redirect("/admin/group/list")
		
		members = []
		for row in user_rows:
			members.append({
				"id": row["id"],
				"name": row["username"],
				"type": "user",
				"joined_at": row["joined_at"][:19] if row.get("joined_at") else ""
			})
		
		employees = []
		for row in employee_rows:
			employees.append({
				"id": row["id"],
				"name": row["employee_name"],
				"at_alias": row["at_alias"],
				"type": "employee",
				"added_at": row["added_at"][:19] if row.get("added_at") else ""
			})
		
		self.render(
			"admin_group_detail.html",
			title="群聊详情",
			username=self.current_user,
			active_menu="group",
			group={
				"id": group["id"],
				"name": group["name"],
				"status": group.get("status", "normal"),
				"notice": group.get("notice", ""),
				"created_at": group["created_at"][:19] if group.get("created_at") else ""
			},
			members=members,
			employees=employees
		)


class AdminGroupMembersHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		group_id = int(self.get_argument("group_id", "0"))
		
		if not group_id:
			return self.write(json.dumps({"success": False, "message": "缺少群ID"}))
		
		with get_connection() as conn:
			user_rows = conn.execute("""
				SELECT u.id, u.username, gm.joined_at, gm.status
				FROM group_members gm
				JOIN users u ON gm.user_id = u.id
				WHERE gm.group_id = ?
			""", (group_id,)).fetchall()
			
			employee_rows = conn.execute("""
				SELECT de.id, de.employee_name, de.at_alias, ge.added_at
				FROM group_employees ge
				JOIN digital_employees de ON ge.employee_id = de.id
				WHERE ge.group_id = ?
			""", (group_id,)).fetchall()
		
		members = []
		for row in user_rows:
			members.append({
				"id": row["id"],
				"name": row["username"],
				"type": "user",
				"status": row.get("status", "normal"),
				"joined_at": row["joined_at"][:19] if row.get("joined_at") else ""
			})
		
		for row in employee_rows:
			members.append({
				"id": row["id"],
				"name": row["employee_name"],
				"at_alias": row["at_alias"],
				"type": "employee",
				"added_at": row["added_at"][:19] if row.get("added_at") else ""
			})
		
		return self.write(json.dumps({"success": True, "members": members}))
	
	def post(self):
		action = self.get_body_argument("action", "")
		group_id = int(self.get_body_argument("group_id", "0"))
		member_id = int(self.get_body_argument("member_id", "0"))
		member_type = self.get_body_argument("member_type", "user")
		
		if not group_id or not member_id:
			return self.write(json.dumps({"success": False, "message": "参数错误"}))
		
		with get_connection() as conn:
			if action == "remove":
				if member_type == "user":
					conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, member_id))
				else:
					conn.execute("DELETE FROM group_employees WHERE group_id = ? AND employee_id = ?", (group_id, member_id))
				conn.commit()
				return self.write(json.dumps({"success": True, "message": "移除成功"}))
			elif action == "ban_member":
				if member_type == "user":
					conn.execute("UPDATE group_members SET status = 'banned' WHERE group_id = ? AND user_id = ?", (group_id, member_id))
					conn.commit()
					return self.write(json.dumps({"success": True, "message": "封禁成功"}))
			elif action == "unban_member":
				if member_type == "user":
					conn.execute("UPDATE group_members SET status = 'normal' WHERE group_id = ? AND user_id = ?", (group_id, member_id))
					conn.commit()
					return self.write(json.dumps({"success": True, "message": "解封成功"}))
		
		return self.write(json.dumps({"success": False, "message": "未知操作"}))


class AdminGroupMessagesHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		group_id = int(self.get_argument("group_id", "0"))
		page = int(self.get_argument("page", "1"))
		page_size = 20
		
		if not group_id:
			return self.write(json.dumps({"success": False, "message": "缺少群ID"}))
		
		with get_connection() as conn:
			count_row = conn.execute(
				"SELECT COUNT(*) as cnt FROM group_messages WHERE group_id = ?",
				(group_id,)
			).fetchone()
			total = count_row["cnt"] if count_row else 0
			
			offset = (page - 1) * page_size
			rows = conn.execute("""
				SELECT gm.*, u.username as sender_name
				FROM group_messages gm
				LEFT JOIN users u ON gm.sender_id = u.id
				WHERE gm.group_id = ?
				ORDER BY gm.created_at DESC
				LIMIT ? OFFSET ?
			""", (group_id, page_size, offset)).fetchall()
		
		messages = []
		for row in rows:
			content = row["content"]
			try:
				parsed = json.loads(content)
				if isinstance(parsed, dict):
					content = f"[消息对象: {parsed.get('type', 'unknown')}]"
			except:
				pass
			
			messages.append({
				"id": row["id"],
				"sender_name": row["sender_name"] or "系统",
				"content": content[:100] + "..." if len(content) > 100 else content,
				"content_type": row.get("message_type", "text"),
				"created_at": row["created_at"][:19] if row.get("created_at") else ""
			})
		
		return self.write(json.dumps({
			"success": True,
			"messages": messages,
			"total": total,
			"page": page,
			"page_size": page_size
		}))
	
	def post(self):
		action = self.get_body_argument("action", "")
		group_id = int(self.get_body_argument("group_id", "0"))
		message_id = int(self.get_body_argument("message_id", "0"))
		
		if not group_id:
			return self.write(json.dumps({"success": False, "message": "缺少群ID"}))
		
		with get_connection() as conn:
			if action == "clear":
				conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
				conn.commit()
				return self.write(json.dumps({"success": True, "message": "清空成功"}))
			elif action == "delete":
				if message_id:
					conn.execute("DELETE FROM group_messages WHERE id = ? AND group_id = ?", (message_id, group_id))
					conn.commit()
					return self.write(json.dumps({"success": True, "message": "删除成功"}))
		
		return self.write(json.dumps({"success": False, "message": "未知操作"}))