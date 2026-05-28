import tornado.web
from app.models.admin_user import AdminUserRepository
from app.models.db import get_connection

class AdminBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		return username.decode('utf-8')

	def get_login_url(self):
		return "/admin/login"
	
	def prepare(self):
		# 在每个请求前验证用户权限
		current_user = self.get_current_user()
		if current_user:
			user = AdminUserRepository.get_user_by_username(current_user)
			if user:
				# 检查用户是否具有管理员角色
				has_admin_role = False
				with get_connection() as conn:
					roles = conn.execute("""
						SELECT r.role_code FROM roles r
						INNER JOIN user_roles ur ON r.id = ur.role_id
						WHERE ur.user_id = ? AND r.role_code IN ('super_admin', 'admin_user')
					""", (user["id"],)).fetchall()
					has_admin_role = len(roles) > 0
				
				if not has_admin_role:
					# 没有管理员角色，清除登录状态并跳转登录页
					self.clear_cookie("admin_username")
					self.redirect("/admin/login")
					return
