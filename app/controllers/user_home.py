import tornado.web
from app.controllers.user_base import UserBaseHandler


class UserHomeHandler(UserBaseHandler):
    """用户主界面控制器"""

    @tornado.web.authenticated
    def get(self):
        """渲染主界面"""
        self.render(
            "home.html",
            title="主界面",
            username=self.current_user
        )
