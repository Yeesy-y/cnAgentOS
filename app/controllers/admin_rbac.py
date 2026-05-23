import tornado.web
from app.controllers.admin_base import AdminBaseHandler
from app.models.rbac import PermissionRepository, RoleRepository

class AdminPermissionListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		perms = PermissionRepository.list_all()
		self.render("admin_perm_list.html",
			title="权限管理",
			username=self.current_user,
			active_menu="perm",
			permissions=perms)

	def post(self):
		action = self.get_body_argument("action", "")
		if action == "delete":
			pid = int(self.get_body_argument("pid", "0"))
			if pid:
				PermissionRepository.delete(pid)
		self.redirect("/admin/perm/list")


class AdminPermissionAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		parent_id = int(self.get_argument("parent_id", "0"))
		perms = PermissionRepository.list_all()
		self.render("admin_perm_form.html",
			title="新增权限",
			username=self.current_user,
			active_menu="perm",
			permission=None,
			parent_id=parent_id,
			permissions=perms,
			mode="add")

	def post(self):
		perm_name = (self.get_body_argument("perm_name", "") or "").strip()
		perm_code = (self.get_body_argument("perm_code", "") or "").strip()
		parent_id = int(self.get_body_argument("parent_id", "0"))
		menu_url = (self.get_body_argument("menu_url", "") or "").strip()
		sort_order = int(self.get_body_argument("sort_order", "0"))
		if perm_name and perm_code:
			PermissionRepository.create(perm_name, perm_code, parent_id, menu_url, sort_order)
		self.redirect("/admin/perm/list")


class AdminPermissionEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		pid = int(self.get_argument("id", "0"))
		perm = PermissionRepository.get_by_id(pid)
		if not perm:
			return self.redirect("/admin/perm/list")
		perms = PermissionRepository.list_all()
		self.render("admin_perm_form.html",
			title="编辑权限",
			username=self.current_user,
			active_menu="perm",
			permission=perm,
			parent_id=perm["parent_id"],
			permissions=perms,
			mode="edit")

	def post(self):
		pid = int(self.get_body_argument("id", "0"))
		if not pid:
			return self.redirect("/admin/perm/list")
		perm_name = (self.get_body_argument("perm_name", "") or "").strip()
		perm_code = (self.get_body_argument("perm_code", "") or "").strip()
		parent_id = int(self.get_body_argument("parent_id", "0"))
		menu_url = (self.get_body_argument("menu_url", "") or "").strip()
		sort_order = int(self.get_body_argument("sort_order", "0"))
		PermissionRepository.update(pid, perm_name, perm_code, parent_id, menu_url, sort_order)
		self.redirect("/admin/perm/list")


class AdminRoleListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		roles = RoleRepository.list_all()
		self.render("admin_role_list.html",
			title="角色管理",
			username=self.current_user,
			active_menu="role",
			roles=roles)

	def post(self):
		action = self.get_body_argument("action", "")
		if action == "delete":
			rid = int(self.get_body_argument("rid", "0"))
			if rid and rid != 1:
				RoleRepository.delete(rid)
		self.redirect("/admin/role/list")


class AdminRoleAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		perms = PermissionRepository.list_tree()
		self.render("admin_role_form.html",
			title="新增角色",
			username=self.current_user,
			active_menu="role",
			role=None,
			permissions=perms,
			selected_perms=[],
			mode="add")

	def post(self):
		role_name = (self.get_body_argument("role_name", "") or "").strip()
		role_code = (self.get_body_argument("role_code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		perm_ids = [int(p) for p in self.get_body_arguments("perm_ids") if p.isdigit()]
		if role_name and role_code:
			rid = RoleRepository.create(role_name, role_code, description)
			RoleRepository.assign_permissions(rid, perm_ids)
		self.redirect("/admin/role/list")


class AdminRoleEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		rid = int(self.get_argument("id", "0"))
		role = RoleRepository.get_by_id(rid)
		if not role:
			return self.redirect("/admin/role/list")
		perms = PermissionRepository.list_tree()
		selected_perms = RoleRepository.get_permission_ids(rid)
		self.render("admin_role_form.html",
			title="编辑角色",
			username=self.current_user,
			active_menu="role",
			role=role,
			permissions=perms,
			selected_perms=selected_perms,
			mode="edit")

	def post(self):
		rid = int(self.get_body_argument("id", "0"))
		if not rid or rid == 1:
			return self.redirect("/admin/role/list")
		role_name = (self.get_body_argument("role_name", "") or "").strip()
		role_code = (self.get_body_argument("role_code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		status = int(self.get_body_argument("status", "1"))
		perm_ids = [int(p) for p in self.get_body_arguments("perm_ids") if p.isdigit()]
		RoleRepository.update(rid, role_name, role_code, description, status)
		RoleRepository.assign_permissions(rid, perm_ids)
		self.redirect("/admin/role/list")
