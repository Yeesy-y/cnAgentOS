import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.admin_user import AdminUserRepository

class AdminLoginHandler(AdminBaseHandler):
	def get(self):
		saved_username = self.get_cookie("remember_admin_username", "")
		self.render("admin_login.html", title="管理后台登录", error=None, saved_username=saved_username)

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		remember = self.get_body_argument("remember", "")

		if not username or not password:
			return self.render("admin_login.html", title="管理后台登录", error="用户名或密码不能为空", saved_username="")

		user = AdminUserRepository.get_user_by_username(username)
		if not user:
			return self.render("admin_login.html", title="管理后台登录", error="用户不存在", saved_username=username)

		try:
			user_status = user["status"]
			if user_status != 1:
				return self.render("admin_login.html", title="管理后台登录", error="该账号已被禁用，请联系管理员", saved_username=username)
		except (IndexError, KeyError):
			pass

		if not AdminUserRepository.verify_user(username, password):
			return self.render("admin_login.html", title="管理后台登录", error="用户名或密码错误", saved_username=username)

		if remember:
			self.set_cookie("remember_admin_username", username, expires_days=30)
		else:
			self.clear_cookie("remember_admin_username")

		self.set_secure_cookie("admin_username", username)
		self.redirect("/admin/index")


class AdminLogoutHandler(AdminBaseHandler):
	def post(self):
		self.clear_cookie("admin_username")
		self.redirect("/admin/login")
