import tornado.web
from app.models.user_service import UserRepository

class UserBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("username")
		if not username:
			return None
		return username.decode("utf-8")

	def get_login_url(self):
		return "/login"

	def get_current_user_row(self):
		if not self.current_user:
			return None
		return UserRepository.get_user_by_username(self.current_user)
