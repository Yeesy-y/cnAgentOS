#程序的主入口
#承担服务器容器+程序作用
#服务器容器:提供http容器服务,程序放置于该容器中运行
#程序:本体-智能瞭望与智能问数系统 B/s架构
import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

#from app.controllers.base import BaseHandler
#引入auth-controller层
from app.controllers.auth import LoginHandler,LogoutHandler
from app.controllers.home import IndexHandler
#引入admin-controller层
from app.controllers.admin_auth import AdminLoginHandler,AdminLogoutHandler
from app.controllers.admin_home import AdminIndexHandler
from app.controllers.admin_user import AdminUserListHandler,AdminUserAddHandler,AdminUserEditHandler
from app.controllers.admin_rbac import AdminPermissionListHandler,AdminPermissionAddHandler,AdminPermissionEditHandler
from app.controllers.admin_rbac import AdminRoleListHandler,AdminRoleAddHandler,AdminRoleEditHandler
from app.controllers.admin_model import AdminModelListHandler,AdminModelAddHandler,AdminModelEditHandler,AdminModelTestHandler
from app.controllers.admin_watch import AdminWatchSourceListHandler,AdminWatchSourceAddHandler,AdminWatchSourceEditHandler
from app.controllers.admin_watch import AdminWatchCollectHandler,AdminWatchDataListHandler
#引入db-model层
from app.models.db import init_db



# class HealthHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write({"status":"ok"})

# class LoginHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write(f"""<h3>模拟登录验证测试BaseHandler</h3>

# 			<form method="post">
# 			{self.xsrf_form_html()}
# 			<button type="submit">登录admin</button>
# 			</form>
# 			""")

# 	def post(self):
# 		next_url=self.get_argument("next","/private")
# 		self.set_secure_cookie("username","admin")
# 		#写完安全的cookie以后,跳转到目标地址
# 		self.redirect(next_url)

# class PrivateHandler(BaseHandler):
# 	@tornado.web. authenticated
# 	def get(self):
# 		self.write(self.current_user)






def make_app():
	# return tornado.web.Application([
	# 	("/abc",HealthHandler),
	# 	("/login.jsp",HealthHandler),
	# 	("/",HealthHandler),
	# 	("/login.php",HealthHandler)
	# ],debug=True)
	# return tornado.web.Application([
	# 	    (r"/",LoginHandler),
	# 	    (r"/abc",HealthHandler),
	# 	    (r"/private",PrivateHandler)
	#     ],
	#     cookie_secret="demo-cookie-secret-change-me",
	#     login_url="/",
	#     xsrf_cookies=True,
	#     debug=True
	# )
	base_url = os.path.dirname(os.path.abspath(__file__))
	settings = dict(
		#预留view层的内容配置
		template_path=os.path.join(base_url,"app","templates"),
		static_path=os.path.join(base_url,"app","static"),
		cookie_secret="demo-cookie-secret-change-me",
		login_url="/auth/login",
		xsrf_cookies=True,
		debug=True,
		autoreload=True
	)
	return tornado.web.Application([
		(r"/",IndexHandler),
		(r"/auth/login",LoginHandler),
		(r"/auth/logout",LogoutHandler),
		# admin后台路由
		(r"/admin/login",AdminLoginHandler),
		(r"/admin/logout",AdminLogoutHandler),
		(r"/admin/index",AdminIndexHandler),
		(r"/admin/user/list",AdminUserListHandler),
		(r"/admin/user/add",AdminUserAddHandler),
		(r"/admin/user/edit",AdminUserEditHandler),
		# 模型引擎路由
		(r"/admin/model/list",AdminModelListHandler),
		(r"/admin/model/add",AdminModelAddHandler),
		(r"/admin/model/edit",AdminModelEditHandler),
		(r"/admin/model/test",AdminModelTestHandler),
		# 瞭望管理路由
		(r"/admin/watch/source/list",AdminWatchSourceListHandler),
		(r"/admin/watch/source/add",AdminWatchSourceAddHandler),
		(r"/admin/watch/source/edit",AdminWatchSourceEditHandler),
		(r"/admin/watch/collect",AdminWatchCollectHandler),
		(r"/admin/watch/data/list",AdminWatchDataListHandler),
		# RBAC路由
		(r"/admin/perm/list",AdminPermissionListHandler),
		(r"/admin/perm/add",AdminPermissionAddHandler),
		(r"/admin/perm/edit",AdminPermissionEditHandler),
		(r"/admin/role/list",AdminRoleListHandler),
		(r"/admin/role/add",AdminRoleAddHandler),
		(r"/admin/role/edit",AdminRoleEditHandler)

		],
		**settings
		)





	
if __name__=="__main__":
	#启动服务前，检查并初始化数据库表
	init_db()
	app=make_app()
	server = HTTPServer(app)
	server.bind(10086)
	#自动CPU核心数
	server.start()

	print("===== Server 启动成功 ======= 端口：10086 ======",flush=True)
	tornado.ioloop.IOLoop.current().start()

