import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.admin_user import AdminUserRepository
from app.models.rbac import RoleRepository

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
				user = AdminUserRepository.get_user_by_id(uid)
				if user and user["username"] != "admin":
					AdminUserRepository.delete_user(uid)
		return self.redirect("/admin/user/list")


class AdminUserAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		roles = RoleRepository.list_all()
		self.render("admin_user_form.html",
			title="新增用户",
			username=self.current_user,
			active_menu="user",
			user=None,
			mode="add",
			roles=roles,
			user_role_ids=[])

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		real_name = (self.get_body_argument("real_name", "") or "").strip()
		role_ids_str = self.get_body_arguments("role_ids")

		if not username or not password or len(password) < 6:
			return self.redirect("/admin/user/add")

		user_id = AdminUserRepository.create_user(username, password, real_name, "", "")
		if user_id:
			role_ids = [int(x) for x in role_ids_str if x.strip().isdigit()]
			AdminUserRepository.assign_roles(user_id, role_ids)
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
		
		roles = RoleRepository.list_all()
		user_roles = AdminUserRepository.get_user_roles(user_id)
		user_role_ids = [r["id"] for r in user_roles]
		
		self.render("admin_user_form.html",
			title="编辑用户",
			username=self.current_user,
			active_menu="user",
			user=dict(user),
			mode="edit",
			roles=roles,
			user_role_ids=user_role_ids)

	def post(self):
		user_id = int(self.get_body_argument("id", "0"))
		if not user_id:
			return self.redirect("/admin/user/list")
		
		user = AdminUserRepository.get_user_by_id(user_id)
		if not user:
			return self.redirect("/admin/user/list")
		
		if user["username"] == "admin":
			password = self.get_body_argument("password", "")
			if password and len(password) >= 6:
				AdminUserRepository.update_user(user_id, password=password)
		else:
			real_name = (self.get_body_argument("real_name", "") or "").strip()
			password = self.get_body_argument("password", "")
			status = int(self.get_body_argument("status", "1"))
			role_ids_str = self.get_body_arguments("role_ids")
			
			AdminUserRepository.update_user(
				user_id,
				real_name=real_name,
				email="",
				phone="",
				password=password if password else None,
				status=status
			)
			
			role_ids = [int(x) for x in role_ids_str if x.strip().isdigit()]
			AdminUserRepository.assign_roles(user_id, role_ids)
		
		return self.redirect("/admin/user/list")


class AdminProfileHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		user = AdminUserRepository.get_user_by_username(self.current_user)
		if not user:
			return self.redirect("/admin/login")
		self.render(
			"admin_profile.html",
			title="基本资料",
			username=self.current_user,
			active_menu="",
			user=dict(user)
		)

	@tornado.web.authenticated
	def post(self):
		user = AdminUserRepository.get_user_by_username(self.current_user)
		if not user:
			return self.redirect("/admin/login")
		real_name = (self.get_body_argument("real_name", "") or "").strip()
		email = (self.get_body_argument("email", "") or "").strip()
		phone = (self.get_body_argument("phone", "") or "").strip()
		AdminUserRepository.update_user(user["id"], real_name=real_name, email=email, phone=phone)
		return self.redirect("/admin/user/profile")


class AdminSecurityHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render(
			"admin_security.html",
			title="安全设置",
			username=self.current_user,
			active_menu=""
		)

	@tornado.web.authenticated
	def post(self):
		current_password = self.get_body_argument("current_password", "")
		new_password = self.get_body_argument("new_password", "")
		confirm_password = self.get_body_argument("confirm_password", "")

		if not AdminUserRepository.verify_user(self.current_user, current_password):
			return self.redirect("/admin/user/security?error=1")
		if len(new_password) < 6:
			return self.redirect("/admin/user/security?error=2")
		if new_password != confirm_password:
			return self.redirect("/admin/user/security?error=3")

		user = AdminUserRepository.get_user_by_username(self.current_user)
		if not user:
			return self.redirect("/admin/login")
		AdminUserRepository.update_user(user["id"], password=new_password)
		return self.redirect("/admin/user/security?success=1")
