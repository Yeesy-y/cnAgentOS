│  app.md (本文件，说明整个项目的目录结构及文件归属，是指导AI完成开发的重要框架性帮助文件)
│  app.py (整个程序的主入口，采用tornado框架构建实现，MVC三层经典架构)
│  test.py (程序单元测试用脚本文件，主要用于模块/包/方法的测试，可以写入一些临时性的测试用例)
│  
├─app（整个项目的主包）
│  │  **init**.py
│  │  
│  ├─controllers (MVC中的控制层模块)
│  │  │  auth.py (鉴权有关的控制层方法，涉及登录、注册、退出)
│  │  │  base.py（控制层 公共基类，提供纺一的登录态获取逻辑，供其他Handler继承使用）
│  │  │  home.py（后台首页控制类）
│  │  │  **init**.py
│  │  │  
│  │  └─\_\_pycache\_\_
│  │          auth.cpython-311.pyc
│  │          base.cpython-311.pyc
│  │          home.cpython-311.pyc
│  │          **init**.cpython-311.pyc
│  │  
│  ├─models（业务与数据模型层）
│  │  │  db.py（sqlite数据库访问层【model】后续可在此拓展兼容MySQL、pgsql等数据库访问逻辑）
│  │  │  user.py（对应相关用户的model）
│  │  │  **init**.py
│  │  │  
│  │  └─\_\_pycache\_\_
│  │          db.cpython-311.pyc
│  │          user.cpython-311.pyc
│  │          **init**.cpython-311.pyc
│  │  
│  ├─static（view中的静态资源）
│  │  ├─css（样式）
│  │  │      base.css（基础公共样式）
│  │  │  
│  │  └─js（JS脚本）
│  │          base.js（基础公共脚本）
│  │  
│  ├─templates（view-视图）
│  │      base.html（基础摸板）
│  │      index.html（后台首页模版）
│  │      login.html（登录页模版）
│  │      register.html（注册页模版）
│  │  
│  └─\_\_pycache\_\_
│          **init**.cpython-311.pyc
│  
├─database (sqlite数据库目录,用于存放sqlite文件或sql脚本文件)
│      app.db (当前自动创建的sqLite数据库，通过init\_db()在启动时检查创建)
│  
└─venv (python3.11下创建venv空间，语法：python-m venv venv，后续开发、运行启动需要在此空间中完成）


