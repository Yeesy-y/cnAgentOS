import tornado.web
from app.controllers.user_base import UserBaseHandler
from app.models.user_service import UserRepository

class UserLoginHandler(UserBaseHandler):
	def get(self):
		saved_username = self.get_cookie("remember_username", "")
		self.render("user_login.html", title="用户登录", error=None, saved_username=saved_username)

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		remember = self.get_body_argument("remember", "")

		if not username or not password:
			return self.render("user_login.html", title="用户登录", error="用户名或密码不能为空", saved_username=username)

		user = UserRepository.get_user_by_username(username)
		if not user:
			return self.render("user_login.html", title="用户登录", error="用户不存在", saved_username=username)

		try:
			user_status = user["status"]
			if user_status != 1:
				return self.render("user_login.html", title="用户登录", error="该账号已被禁用，请联系管理员", saved_username=username)
		except (IndexError, KeyError):
			pass

		if not UserRepository.verify_user(username, password):
			return self.render("user_login.html", title="用户登录", error="用户名或密码错误", saved_username=username)

		user_id = int(user["id"])
		if UserRepository.has_role_code(user_id, "super_admin"):
			return self.render("user_login.html", title="用户登录", error="该账号为管理员账号，请使用管理后台登录", saved_username=username)

		if remember:
			self.set_cookie("remember_username", username, expires_days=30)
		else:
			self.clear_cookie("remember_username")

		self.set_secure_cookie("username", username)
		self.redirect("/home")


class UserLogoutHandler(UserBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.clear_cookie("username")
		self.redirect("/login")

	@tornado.web.authenticated
	def post(self):
		self.clear_cookie("username")
		self.redirect("/login")


class UserRegisterHandler(UserBaseHandler):
	def get(self):
		self.render("user_register.html", title="用户注册", error=None, form=None)

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		password2 = self.get_body_argument("password2", "")
		real_name = (self.get_body_argument("real_name", "") or "").strip()

		form = {"username": username, "real_name": real_name}
		if not username or not password:
			return self.render("user_register.html", title="用户注册", error="用户名或密码不能为空", form=form)
		if len(password) < 6:
			return self.render("user_register.html", title="用户注册", error="密码长度至少6位", form=form)
		if password != password2:
			return self.render("user_register.html", title="用户注册", error="两次输入的密码不一致", form=form)

		user_id = UserRepository.create_normal_user(username, password, real_name, "", "")
		if not user_id:
			return self.render("user_register.html", title="用户注册", error="注册失败：用户名可能已存在", form=form)

		self.redirect("/login")
