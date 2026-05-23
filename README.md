# AI智能瞭望与智能问数系统

> 基于 Tornado MVC 架构的 B/S 架构 Web 应用系统

---

## 一、项目概览

### 1.1 项目定位
本系统是一个 **AI智能瞭望与智能问数系统**，采用 B/S（Browser/Server）架构，用户通过浏览器访问，服务端提供HTTP服务与业务逻辑处理。

### 1.2 技术栈
| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 运行时 | Python | 3.11 | 虚拟环境位于 `venv/` |
| Web框架 | Tornado | 6.5.5 | 异步非阻塞HTTP框架 |
| 数据库 | SQLite3 | 内置 | 轻量级文件型数据库 |
| 前端 | HTML5 + CSS + JavaScript | - | 模板渲染 + 静态资源 |
| UI组件库 | Layui | 2.13.6 | 本地化部署，用于快速构建后台界面 |
| 响应式框架 | Bootstrap | 5.3.8 | 本地化部署，用于响应式布局与组件 |
| 图标库 | FontAwesome | 5.15.4 | 本地化部署，提供丰富图标 |

### 1.3 架构模式
采用 **MVC（Model-View-Controller）** 分层架构：
- **Model（模型层）**：`app/models/` - 数据库访问与业务逻辑
- **View（视图层）**：`app/templates/` + `app/static/` - 模板渲染与静态资源
- **Controller（控制层）**：`app/controllers/` - HTTP请求处理与路由分发

---

## 二、项目目录结构

```
cnAgentOS/
├── app.md                          # 项目目录结构说明文档
├── README.md                       # 项目开发指导文档（本文件）
├── app.py                          # 程序主入口（服务器容器 + 应用本体）
├── test.py                         # 单元测试/临时测试脚本
│
├── app/                            # MVC业务代码根包
│   ├── __init__.py                 # 包标识文件（便于IDE识别与导入）
│   │
│   ├── controllers/                # 【控制层】tornado RequestHandler
│   │   ├── __init__.py             # 包标识
│   │   ├── base.py                 # 公共基础Handler类（BaseHandler）
│   │   ├── auth.py                 # 认证相关Handler（登录/退出）
│   │   └── home.py                 # 后台首页Handler
│   │
│   ├── models/                     # 【模型层】数据访问 + 业务方法
│   │   ├── __init__.py             # 包标识
│   │   ├── db.py                   # 数据库连接与建表（DDL）
│   │   └── user.py                 # 用户数据访问对象（UserRepository）
│   │
│   ├── templates/                  # 【视图层】HTML模板（Tornado模板引擎）
│   │   ├── base.html               # 基础布局模板（继承模板）
│   │   ├── login.html              # 登录页模板
│   │   ├── index.html              # 后台首页模板
│   │   └── register.html           # 注册页模板（已创建，内容为空，待开发）
│   │
│   └── static/                     # 【视图层】静态资源
│       ├── css/
│       │   └── base.css            # 基础样式重置文件
│       ├── js/
│       │   └── base.js             # 基础JS脚本
│       └── dist/                   # 【第三方前端组件库】（本地化部署）
│           ├── layui-v2.13.6/      # Layui UI组件库
│           │   ├── layui/
│           │   │   ├── css/layui.css
│           │   │   ├── layui.js
│           │   │   └── font/       # Layui图标字体
│           │   └── test.html       # Layui测试页
│           ├── bootstrap-5.3.8-dist/  # Bootstrap响应式框架
│           │   ├── css/
│           │   │   └── bootstrap.min.css  # 推荐使用min版本
│           │   └── js/
│           │       └── bootstrap.bundle.min.js  # 含Popper的完整包
│           └── fontawesome-free-5.15.4-web/  # FontAwesome图标库
│               ├── css/
│               │   ├── all.min.css   # 全部图标
│               │   ├── fontawesome.min.css  # 核心
│               │   └── solid.min.css  # 实心图标
│               ├── webfonts/        # 图标字体文件
│               └── js/              # JS版本图标
│
├── database/                       # SQLite数据库目录
│   └── app.db                      # SQLite数据库文件（运行时自动创建）
│
└── venv/                           # Python 3.11 虚拟环境
    └── ...                         # 依赖包（tornado 6.5.5 等）
```

---

## 三、核心文件详解

### 3.1 主入口 `app.py`

**路径**: `d:\ysy\4\cnAgentOS\app.py`

**职责**:
- 服务器容器：提供 HTTP 服务
- 应用配置：路由表 + Tornado Settings
- 启动入口：初始化数据库、绑定端口、启动事件循环

**关键逻辑**:
```python
# 路由配置
(r"/",             IndexHandler),   # 后台首页（需登录）
(r"/auth/login",   LoginHandler),   # 登录页
(r"/auth/logout",  LogoutHandler),  # 退出登录

# Tornado Settings
template_path = "app/templates"      # 模板路径
static_path   = "app/static"         # 静态资源路径
cookie_secret = "demo-cookie-secret-change-me"  # 安全Cookie密钥
login_url     = "/auth/login"        # 未登录跳转地址
xsrf_cookies  = True                 # 开启XSRF防护
debug         = True                 # 调试模式
autoreload    = True                 # 代码自动重载

# 服务端口: 10086
# 启动方式: server.bind(10086) + server.start()（自动CPU核心数）
```

**启动流程**:
1. 调用 `init_db()` 检查并初始化数据库表
2. 调用 `make_app()` 创建 Tornado Application
3. 创建 `HTTPServer` 并绑定端口 10086
4. 启动 `IOLoop` 事件循环

---

### 3.2 控制层（Controllers）

#### 3.2.1 基础Handler `base.py`

**路径**: `d:\ysy\4\cnAgentOS\app\controllers\base.py`

**职责**: 提供统一的认证机制，供其他 Handler 继承使用

**核心类**: `BaseHandler(tornado.web.RequestHandler)`

```python
class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        # 读取 secure cookie 中的 username
        # 返回 username 字符串 或 None
        # 若返回 None，则 @tornado.web.authenticated 装饰器
        # 会触发跳转到 login_url（/auth/login）
```

**认证机制说明**:
- Tornado 框架通过 `get_current_user()` 的返回值判断用户是否已登录
- 返回 `None` 表示未登录，触发 `@tornado.web.authenticated` 跳转到 `login_url`
- 返回有效值表示已登录，`self.current_user` 即为返回值

#### 3.2.2 认证Handler `auth.py`

**路径**: `d:\ysy\4\cnAgentOS\app\controllers\auth.py`

**已实现的Handler**:

| Handler | 路由 | 方法 | 说明 |
|---------|------|------|------|
| `LoginHandler` | `/auth/login` | GET | 渲染登录页面 |
| `LoginHandler` | `/auth/login` | POST | 校验用户名密码，写入secure cookie，跳转到首页 |
| `LogoutHandler` | `/auth/logout` | POST | 清除username cookie，跳转回登录页 |

**LoginHandler 逻辑流程 (POST)**:
1. 获取表单参数 `username` 和 `password`
2. 校验是否为空 → 空则返回 400 + 错误信息
3. 调用 `UserRepository.verify_user(username, password)` 验证
4. 验证失败 → 返回 401 + 错误信息
5. 验证成功 → `set_secure_cookie("username", username)` → `redirect("/")`

**注意**: 注册功能（RegisterHandler）尚未实现，`register.html` 模板已创建但内容为空。

#### 3.2.3 首页Handler `home.py`

**路径**: `d:\ysy\4\cnAgentOS\app\controllers\home.py`

**已实现的Handler**:

| Handler | 路由 | 方法 | 说明 |
|---------|------|------|------|
| `IndexHandler` | `/` | GET | 渲染后台首页（需登录） |

**认证要求**: `@tornado.web.authenticated` 装饰器 → 未登录自动跳转到 `/auth/login`

**渲染模板**: `index.html`，传入参数 `title="后台"` 和 `username=self.current_user`

---

### 3.3 模型层（Models）

#### 3.3.1 数据库模块 `db.py`

**路径**: `d:\ysy\4\cnAgentOS\app\models\db.py`

**职责**: 数据库连接管理与表初始化

**核心函数**:

| 函数 | 说明 |
|------|------|
| `_project_root()` | 获取项目根目录的绝对路径 |
| `get_connection()` | 获取 SQLite 连接，设置 `row_factory = sqlite3.Row`（支持列名访问） |
| `init_db()` | 初始化数据库表（CREATE TABLE IF NOT EXISTS） |

**数据库文件路径**: `database/app.db`（相对于项目根目录）

**已定义的表结构 - `users` 表**:
```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    create_at     TEXT    NOT NULL DEFAULT(datetime('now'))
)
```

**扩展说明**: `db.py` 当前为 SQLite 直连实现，代码结构预留了扩展到其他数据库（MySQL/PostgreSQL）的能力。

#### 3.3.2 用户模块 `user.py`

**路径**: `d:\ysy\4\cnAgentOS\app\models\user.py`

**职责**: 用户相关的数据访问对象（UserRepository），包含密码加密、用户创建、查询与验证

**核心类**: `UserRepository`

| 方法 | 类型 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `create_user` | 静态 | `username: str`, `password: str` | `bool` | 创建新用户，若用户名已存在返回 `False` |
| `get_user_by_username` | 静态 | `username: str` | `sqlite3.Row` 或 `None` | 根据用户名查询用户信息 |
| `verify_user` | 静态 | `username: str`, `password: str` | `bool` | 验证用户名和密码是否正确 |

**密码加密机制**:
- 算法：`PBKDF2-HMAC-SHA256`
- 迭代次数：100,000 次
- Salt：16 字节随机数（`secrets.token_bytes(16)`）
- 存储格式：`password_hash` 存储 hex 编码的密钥，`salt` 存储 hex 编码的随机盐值

```python
def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return dk.hex()
```

---

### 3.4 视图层（Views）

#### 3.4.1 模板引擎

使用 **Tornado 内置模板引擎**，支持：
- 模板继承：`{% extends "base.html" %}`
- 块定义：`{% block body %}{% end %}`
- 变量渲染：`{{ variable }}`
- 条件判断：`{% if error %} ... {% end %}`
- XSRF Token：`{% module xsrf_form_html() %}`
- 静态资源引用：`{{ static_url('css/base.css') }}`

#### 3.4.2 `base.html` - 基础布局模板

**路径**: `d:\ysy\4\cnAgentOS\app\templates\base.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="{{ static_url('css/base.css') }}">
</head>
<body>
    <div class="container">
        {% block body %}{% end %}
    </div>
</body>
</html>
```

**特点**: 定义全局 HTML 骨架，子模板通过 `{% block body %}` 注入内容。

#### 3.4.3 `login.html` - 登录页模板

**路径**: `d:\ysy\4\cnAgentOS\app\templates\login.html`

```html
{% extends "base.html" %}
{% block body %}
<h3>登录</h3>
{% if error %}
<div class="error">{{ error }}</div>
{% end %}
<form method="post" action="/auth/login">
    <input name="username">
    <input name="password">
    <button type="submit">登录admin</button>
    {% module xsrf_form_html() %}
</form>
{% end %}
```

**传入参数**:
- `title`: 页面标题（"登录"）
- `error`: 错误信息（可选，为 `None` 时不显示）

#### 3.4.4 `index.html` - 后台首页模板

**路径**: `d:\ysy\4\cnAgentOS\app\templates\index.html`

```html
{% extends "base.html" %}
{% block body %}
<h3>后台页面</h3>
<form action="/auth/logout" method="post">
    {% module xsrsf_form_html() %}
    <button type="submit">退出</button>
</form>
<div>{{ username }}</div>
{% end %}
```

**传入参数**:
- `title`: 页面标题（"后台"）
- `username`: 当前登录用户名

#### 3.4.5 `register.html` - 注册页模板（待开发）

**路径**: `d:\ysy\4\cnAgentOS\app\templates\register.html`

**状态**: 文件已创建，内容为空。后续开发需补充注册表单内容。

#### 3.4.6 静态资源

| 文件 | 路径 | 说明 |
|------|------|------|
| `base.css` | `app/static/css/base.css` | CSS重置样式，基础错误提示样式 |
| `base.js` | `app/static/js/base.js` | 基础JS脚本（当前仅有一行测试代码） |

---

## 四、已实现功能清单

### 4.1 用户认证功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 用户登录 | 已完成 | 用户名密码验证，secure cookie 会话管理 |
| 用户退出 | 已完成 | 清除会话cookie，跳转回登录页 |
| 登录态保护 | 已完成 | `@tornado.web.authenticated` 装饰器保护需要登录的页面 |
| XSRF防护 | 已完成 | 全局开启 XSRF Cookie 防护 |
| 用户注册 | 未完成 | `register.html` 已创建但为空，RegisterHandler 未实现 |

### 4.2 数据库功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 数据库初始化 | 已完成 | 启动时自动创建 `users` 表 |
| 用户创建 | 已完成 | `UserRepository.create_user()` |
| 密码加密存储 | 已完成 | PBKDF2 + Salt 安全存储 |
| 用户查询 | 已完成 | `UserRepository.get_user_by_username()` |
| 用户验证 | 已完成 | `UserRepository.verify_user()` |

### 4.3 测试验证

通过 `test.py` 脚本已验证以下场景：
```
✅ 创建用户 admin/123456 → 成功
✅ 创建重复用户 admin → 失败（唯一约束）
✅ 查询用户 admin → 成功
✅ 验证 admin/123456 → 成功
✅ 验证 admin1/123456 → 成功
✅ 验证 admin/1234567 → 失败（密码错误）
```

---

## 五、开发规范与约定

### 5.1 MVC分层职责

| 层级 | 目录 | 职责 | 原则 |
|------|------|------|------|
| Controller | `app/controllers/` | 接收HTTP请求、校验参数、调用Model、渲染View或跳转 | 一个业务模块一个文件 |
| Model | `app/models/` | 数据库访问、业务逻辑、数据校验 | 不直接处理HTTP请求 |
| View | `app/templates/` + `app/static/` | HTML模板渲染、静态资源 | 不包含业务逻辑 |

### 5.2 路由命名规范

| 模块 | 路由前缀 | 示例 |
|------|----------|------|
| 认证 | `/auth/` | `/auth/login`, `/auth/logout`, `/auth/register`（待添加） |
| 首页 | `/` | `/` |
| 未来扩展 | 按模块名 | 如 `/api/`, `/data/` 等 |

### 5.3 Handler命名规范

- 以业务功能命名 + `Handler` 后缀
- 如：`LoginHandler`, `LogoutHandler`, `IndexHandler`
- 公共逻辑抽取到 `BaseHandler`

### 5.4 Model命名规范

- 数据访问类以 `Repository` 结尾
- 如：`UserRepository`
- 方法使用静态方法（`@staticmethod`）

### 5.5 模板命名规范

- 小写字母 + `.html` 后缀
- 基础模板：`base.html`
- 功能页面：`login.html`, `index.html`, `register.html`

### 5.6 安全规范

- 密码使用 `PBKDF2-HMAC-SHA256` + 随机Salt加密
- 会话使用 `secure_cookie` 加密存储
- 全局开启 XSRF Cookie 防护
- 表单提交使用 `{% module xsrf_form_html() %}` 生成隐藏字段

---

## 六、开发指南

### 6.1 环境准备

```powershell
# 激活虚拟环境
venv\Scripts\activate

# 安装依赖（当前仅 tornado）
pip install tornado==6.5.5
```

### 6.2 启动服务

```powershell
# 在项目根目录执行
python app.py
```

服务启动后访问: `http://localhost:10086`

**默认测试账号**: `admin / 123456`（通过 `test.py` 创建）

### 6.3 新增功能模块步骤

以新增"数据查询"模块为例：

**步骤1：Model层** - 在 `app/models/` 下创建数据访问文件
```python
# app/models/data_query.py
from app.models.db import get_connection

class DataRepository:
    @staticmethod
    def get_data_list():
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM xxx").fetchall()
        return rows
```

**步骤2：Controller层** - 在 `app/controllers/` 下创建Handler
```python
# app/controllers/data.py
from app.controllers.base import BaseHandler
from app.models.data_query import DataRepository

class DataListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        data = DataRepository.get_data_list()
        self.render("data_list.html", title="数据列表", data=data)
```

**步骤3：View层** - 在 `app/templates/` 下创建模板
```html
<!-- app/templates/data_list.html -->
{% extends "base.html" %}
{% block body %}
<h3>数据列表</h3>
<!-- 渲染数据 -->
{% end %}
```

**步骤4：注册路由** - 在 `app.py` 的 `make_app()` 中添加路由
```python
(r"/data/list", DataListHandler),
```

**步骤5：导入Handler** - 在 `app.py` 顶部导入新Handler
```python
from app.controllers.data import DataListHandler
```

### 6.4 数据库扩展

如需新增数据表，在 `app/models/db.py` 的 `init_db()` 中添加：
```python
def init_db():
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (...)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS new_table (...)""")  # 新增
```

### 6.5 静态资源引用

在模板中引用静态资源：
```html
<!-- CSS -->
<link rel="stylesheet" href="{{ static_url('css/base.css') }}">
<!-- JS -->
<script src="{{ static_url('js/base.js') }}"></script>
<!-- 图片 -->
<img src="{{ static_url('images/logo.png') }}">
```

---

## 七、待开发功能规划

### 7.1 近期待完成

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 用户注册 | 完善注册功能 | `auth.py`, `register.html`, 路由配置 |
| 密码修改 | 用户修改密码 | 新Controller + 新模板 |
| 用户管理 | 用户列表、编辑、删除 | 新Model + 新Controller + 新模板 |

### 7.2 系统核心功能（AI智能瞭望与智能问数）

| 功能模块 | 说明 | 备注 |
|----------|------|------|
| 智能瞭望 | AI数据监控与预警 | 待需求明确 |
| 智能问数 | 自然语言数据查询 | 待需求明确 |
| 数据可视化 | 图表展示 | 待需求明确 |
| API接口 | 数据交互接口 | 待需求明确 |

---

## 八、关键技术点备忘

### 8.1 Tornado 认证机制

```python
# 1. BaseHandler 中定义 get_current_user()
def get_current_user(self):
    return self.get_secure_cookie("username")

# 2. Settings 中配置 login_url
settings = {"login_url": "/auth/login"}

# 3. Handler 中使用 @tornado.web.authenticated
class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.write(f"Hello {self.current_user}")
```

### 8.2 XSRF 防护

```python
# Settings 中开启
settings = {"xsrf_cookies": True}

# 模板表单中添加
{% module xsrf_form_html() %}

# AJAX 请求需要设置 X-XSRFToken header
```

### 8.3 Secure Cookie

```python
# 写入
self.set_secure_cookie("username", username)

# 读取
username = self.get_secure_cookie("username")

# 清除
self.clear_cookie("username")
```

### 8.4 模板继承

```html
<!-- 父模板 base.html -->
{% block body %}{% end %}

<!-- 子模板 -->
{% extends "base.html" %}
{% block body %}
    <!-- 子模板内容 -->
{% end %}
```

---

## 九、前端组件使用指南

### 9.1 Layui v2.13.6

**官方文档**: https://layui.dev/docs/2

**目录位置**: `app/static/dist/layui-v2.13.6/`

**核心文件**:
- CSS: `{{ static_url('dist/layui-v2.13.6/layui/css/layui.css') }}`
- JS: `{{ static_url('dist/layui-v2.13.6/layui/layui.js') }}`
- 图标字体: `app/static/dist/layui-v2.13.6/layui/font/`

**模板中引入示例**:
```html
{% extends "base.html" %}
{% block body %}
<link rel="stylesheet" href="{{ static_url('dist/layui-v2.13.6/layui/css/layui.css') }}">
<script src="{{ static_url('dist/layui-v2.13.6/layui/layui.js') }}"></script>

<button class="layui-btn">默认按钮</button>
<button class="layui-btn layui-btn-primary">原始按钮</button>
<button class="layui-btn layui-btn-normal">百搭按钮</button>

<script>
layui.use(['layer', 'form'], function(){
    var layer = layui.layer;
    var form = layui.form;
    layer.msg('Hello Layui');
});
</script>
{% end %}
```

**常用模块**: layer（弹层）、form（表单）、table（数据表格）、laydate（日期）、element（通用元素）

### 9.2 Bootstrap 5.3.8

**目录位置**: `app/static/dist/bootstrap-5.3.8-dist/`

**核心文件**:
- CSS: `{{ static_url('dist/bootstrap-5.3.8-dist/css/bootstrap.min.css') }}`
- JS: `{{ static_url('dist/bootstrap-5.3.8-dist/js/bootstrap.bundle.min.js') }}`

**模板中引入示例**:
```html
<link rel="stylesheet" href="{{ static_url('dist/bootstrap-5.3.8-dist/css/bootstrap.min.css') }}">
<script src="{{ static_url('dist/bootstrap-5.3.8-dist/js/bootstrap.bundle.min.js') }}"></script>

<div class="container">
    <div class="row">
        <div class="col-md-6">左列</div>
        <div class="col-md-6">右列</div>
    </div>
    <button class="btn btn-primary">Primary</button>
</div>
```

**注意**: Bootstrap 5 不再依赖 jQuery，`bootstrap.bundle.min.js` 已内置 Popper.js。

### 9.3 FontAwesome 5.15.4

**目录位置**: `app/static/dist/fontawesome-free-5.15.4-web/`

**核心文件**:
- CSS: `{{ static_url('dist/fontawesome-free-5.15.4-web/css/all.min.css') }}`
- 字体文件: `app/static/dist/fontawesome-free-5.15.4-web/webfonts/`

**模板中引入示例**:
```html
<link rel="stylesheet" href="{{ static_url('dist/fontawesome-free-5.15.4-web/css/all.min.css') }}">

<i class="fas fa-home"></i>           <!-- 实心图标 -->
<i class="far fa-user"></i>           <!-- 空心图标 -->
<i class="fab fa-github"></i>         <!-- 品牌图标 -->
<i class="fas fa-spinner fa-spin"></i> <!-- 旋转动画 -->
```

**图标搜索**: 可参考 `fontawesome-free-5.15.4-web/metadata/icons.json` 查看所有可用图标。

### 9.4 组件混用建议

- **Layui** 适合后台管理界面，提供开箱即用的表格、表单、弹窗等组件
- **Bootstrap** 适合响应式布局和通用UI组件
- **FontAwesome** 提供图标，可与 Layui 或 Bootstrap 搭配使用
- 不建议在同一页面同时引入 Layui 和 Bootstrap 的全部样式，可能产生CSS冲突
- 推荐方案：后台管理页使用 Layui + FontAwesome，用户展示页使用 Bootstrap + FontAwesome

### 9.5 本地化资源规范

- 所有前端组件已本地化部署在 `app/static/dist/` 目录下
- **禁止引用任何互联网CDN或外部资源链接**
- 模板中引用静态资源统一使用 Tornado 的 `{{ static_url('...') }}` 语法
- 新增第三方组件时，解压至 `app/static/dist/` 目录下，保持命名规范：`组件名-版本号`

---

## 十、项目运行环境

| 项目 | 值 |
|------|-----|
| 操作系统 | Windows |
| Python版本 | 3.11 |
| 虚拟环境 | `venv/` |
| 服务端口 | 10086 |
| 数据库文件 | `database/app.db` |
| 默认账号 | admin / 123456 |

---

## 十一、注意事项

1. **`register.html` 文件已存在但内容为空**，开发注册功能时需补充内容
2. **`base.js` 中存在语法错误**：`console.Log` 应为 `console.log`（L小写）
3. **`cookie_secret` 为测试值**，生产环境需更换为随机强密钥
4. **`debug=True` 和 `autoreload=True`** 仅用于开发环境，生产环境应关闭
5. **数据库扩展**：当前使用SQLite，如需切换MySQL/PostgreSQL，需修改 `db.py` 的连接逻辑
6. **不要修改现有代码和文件层级**，新增功能按MVC分层规范进行扩展
7. **前端资源本地化**：所有前端组件必须使用本地 `static/dist/` 下的文件，禁止引用CDN
8. **CSS冲突注意**：Layui和Bootstrap不建议在同一页面混用全部样式，按需引入所需组件
