import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.admin_user import AdminUserRepository

class AdminUserListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		result = AdminUserRepository.list_users(1, 20)
		for u in result["data"]:
			if "create_at" in u and u["create_at"]:
				ca = u["create_at"]
				if len(ca) > 10:
					u["create_at"] = ca[:10] + " " + ca[11:19]
		self.render("admin_user_list.html",
			title="用户管理",
			username=self.current_user,
			active_menu="user",
			users=result["data"])

	def post(self):
		action = self.get_body_argument("action", "")
		uids_str = self.get_body_argument("uids", "")
		if action == "delete" and uids_str:
			uids = [int(x.strip()) for x in uids_str.split(",") if x.strip().isdigit()]
			for uid in uids:
				AdminUserRepository.delete_user(uid)
		return self.redirect("/admin/user/list")


class AdminUserAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin_user_form.html",
			title="新增用户",
			username=self.current_user,
			active_menu="user",
			user=None,
			mode="add")

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		real_name = (self.get_body_argument("real_name", "") or "").strip()

		if not username or not password or len(password) < 6:
			return self.redirect("/admin/user/add")

		AdminUserRepository.create_user(username, password, real_name, "", "")
		return self.redirect("/admin/user/list")


class AdminUserEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		user_id = int(self.get_argument("id", "0"))
		if not user_id:
			return self.redirect("/admin/user/list")
		user = AdminUserRepository.get_user_by_id(user_id)
		if not user:
			return self.redirect("/admin/user/list")
		self.render("admin_user_form.html",
			title="编辑用户",
			username=self.current_user,
			active_menu="user",
			user=dict(user),
			mode="edit")

	def post(self):
		user_id = int(self.get_body_argument("id", "0"))
		real_name = (self.get_body_argument("real_name", "") or "").strip()
		password = self.get_body_argument("password", "")
		status = int(self.get_body_argument("status", "1"))

		if not user_id:
			return self.redirect("/admin/user/list")

		AdminUserRepository.update_user(
			user_id,
			real_name=real_name,
			email="",
			phone="",
			password=password if password else None,
			status=status
		)
		return self.redirect("/admin/user/list")
