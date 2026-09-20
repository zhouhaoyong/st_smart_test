# 智测（ST Smart Test）

智测是一套面向研发团队的测试协作平台，覆盖测试工作台、API 测试、工具箱、导航管理和管理中心，帮助团队统一管理需求、测试用例、接口资产、执行结果、缺陷和测试报告。

## 1. 核心能力

| 模块 | 主要能力 |
| --- | --- |
| 测试工作台 | 管理系统、版本、需求、测试用例、执行结果和 Bug |
| API 测试 | 管理项目、环境、接口、参数、用例、执行集和测试报告 |
| 工具箱 | 提供 JSON、时间戳、编码、正则、随机数据、高德地址与坐标互转等常用工具 |
| 导航管理 | 集中维护团队常用的系统、应用和入口链接 |
| 管理中心 | 管理用户、AI 模型、消息通知、执行策略、审计和平台数据 |

## 2. 快速开始

### 2.1 启动前准备

请先安装 Git 和 Docker Desktop（包含 Docker Compose）。默认使用以下端口，请确认没有被其他程序占用：前端 `3000`、后端 `8000`、MySQL `3306`。

### 2.2 克隆、配置并启动

在终端执行：

```bash
git clone <仓库地址> st_smart_test
cd st_smart_test
cp .env.example .env
```

打开根目录 `.env`，启动前重点确认：

| 配置 | 说明 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | MySQL 密码，同时用于后端连接数据库。已有数据库时不要随意修改。 |
| `SECRET_KEY` | JWT 密钥。共享或正式环境必须替换为随机长字符串。 |
| `AMAP_WEB_SERVICE_KEY` | 使用高德地址/坐标转换工具时填写；不使用可留空。 |
| `OSS_*` | 使用 OSS 文件存储时填写，并将 `OSS_ENABLED=true`；本地体验可保持关闭。 |

本地体验可以先使用 `.env.example` 中的其他示例值。然后在项目根目录启动：

```bash
docker-compose up -d --build
```

首次启动会初始化数据库，请等待片刻后执行下面的命令，确认 `st_smart_test_backend` 状态为 `Up (healthy)`：

```bash
docker-compose ps
```

启动完成后访问：

- 前端：<http://localhost:3000>
- 后端健康检查：<http://localhost:8000/health>
- 后端接口文档：<http://localhost:8000/docs>

### 2.3 创建超级管理员

首次启动后，在项目根目录执行：

```bash
docker-compose exec backend python create_superadmin.py --phone 13800000000 --password YourPwd123 --real-name 超级管理员
```

参数要求：手机号为 11 位；密码至少 6 位，并同时包含大写字母和小写字母；真实姓名不能与已有用户重复。

该命令创建的账号仅拥有“超级管理员”角色，不会同时附带“管理员”角色。

## 3. 第一次使用

1. 使用超级管理员账号登录平台。
2. 其他用户可以在登录页注册，注册后默认是普通用户；超级管理员也可以在管理中心新增用户并明确分配角色。
3. 在管理中心配置 AI 模型或消息通知。
4. 使用测试工作台时，按“系统与版本 → 需求 → 测试用例 → 执行 → Bug”的顺序操作。
5. 使用 API 测试时，按“项目 → 环境 → 接口 → 测试用例 → 执行集 → 测试报告”的顺序操作。
6. 需要临时处理数据时，使用工具箱；需要维护常用入口时，使用导航管理。

## 4. 配置说明

### 4.1 配置文件位置

普通用户使用 Docker 启动时，只需要维护根目录 `.env`：

| 使用方式 | 配置文件 | 说明 |
| --- | --- | --- |
| Docker Compose | 根目录 `.env` | 从根目录 `.env.example` 复制，是 Docker 启动的唯一配置入口。 |
| 前端单独构建 | `frontend/.env.production` 或 `frontend/.env.staging` | 仅用于 Vite 构建期的前端地址和 API 地址。 |

### 4.2 常用配置

以下配置用于 Docker 启动，全部填写在根目录 `.env` 中：

| 配置 | 作用 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD`、`MYSQL_DATABASE` | MySQL 密码和数据库名称。 |
| `MYSQL_PORT`、`BACKEND_PORT`、`FRONTEND_PORT` | 宿主机端口映射，默认是 `3306`、`8000`、`3000`。 |
| `SECRET_KEY` | JWT 签名和敏感配置加密密钥。 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 普通登录 Token 有效期，单位为分钟。 |
| `ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER` | “记住我”登录 Token 有效期，单位为分钟。 |
| `FRONTEND_BASE_URL` | 前端访问地址，用于通知消息中的跳转链接。 |
| `BACKEND_CORS_ORIGINS` | 允许访问后端的前端地址，多个地址用英文逗号分隔。 |
| `AMAP_WEB_SERVICE_KEY` | 高德 Web 服务 API Key，用于地址转经纬度和经纬度转地址；可在高德开放平台“控制台 → 应用管理”中创建应用获取。 |
| `OSS_ENABLED` 及其他 `OSS_*` | 是否启用 OSS，以及 OSS 地址、Bucket、访问凭证和文件访问前缀。 |
| `DEBUG`、`ENABLE_API_DOCS`、`SCHEDULER_ENABLED` | 调试模式、接口文档和定时执行策略开关。 |
| `ALLOW_DESTRUCTIVE_MIGRATIONS` | 破坏性数据库迁移开关，默认 `false`；只有确认备份和删除范围后，才临时设为 `true`。 |

修改根目录 `.env` 后，重新执行：

```bash
docker-compose up -d --build
```

### 4.3 前端单独构建

只有直接使用 Vite 构建前端时，才需要维护 `frontend/.env.production` 或 `frontend/.env.staging`，主要配置 `VITE_API_BASE_URL`、`VITE_BASE_PATH` 和 `VITE_REQUEST_TIMEOUT`。

### 4.4 本地与远程部署安全要求

根目录 `.env` 仅用于本机或部署环境，不要提交到 Git，也不要把其中的真实凭证复制到群聊、文档或镜像构建日志中。仓库中的 `.env.example` 只提供格式示例，不能直接作为正式环境配置。

本地体验可以使用示例配置；远程部署前必须至少替换以下配置：

| 配置 | 远程部署要求 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | 使用随机强密码；已有数据库时不要随意修改，避免无法连接原数据库。 |
| `SECRET_KEY` | 使用随机长字符串；该密钥同时用于 JWT 和已保存凭证的加密。已有数据更换后，已保存的 AI 模型密钥等加密凭证需要重新录入。 |
| `BACKEND_CORS_ORIGINS` | 填写实际前端地址，多个地址用英文逗号分隔，不建议使用 `*`。 |
| `DEBUG` | 远程环境设置为 `false`。 |
| `ENABLE_API_DOCS` | 远程环境通常设置为 `false`，确需调试时再临时开启。 |
| `FRONTEND_BASE_URL` | 填写用户实际访问的前端地址，用于通知消息中的跳转链接。 |

Docker Compose 未填写环境变量时会使用开发默认值，包括默认数据库密码、默认密钥、宽松跨域和开启调试。正式环境不要依赖这些默认值，必须显式维护部署环境的 `.env`。

### 4.5 数据库初始化与迁移

后端启动前会自动执行 `backend/init_db.py`。它只创建缺失表，并只自动补齐允许为空的安全字段；新增非空字段、字段修改、数据回填和删除操作必须集中写在该文件的迁移配置区。迁移失败时容器不会继续启动 Web 服务。

每条显式迁移成功后会记录到数据库的 `schema_migrations` 表，重复重启不会重复执行。一次性迁移在所有环境完成后，可以从配置区移除活动 SQL，但不要把一次性 SQL 分散到业务代码中。删除表或字段前，必须先从模型移除对应定义，并临时设置 `ALLOW_DESTRUCTIVE_MIGRATIONS=true`；执行完成后立即恢复为 `false`。

## 5. 权限与管理

平台权限由登录身份、项目范围和操作类型共同决定。项目支持公开或私有范围，普通用户、管理员和超级管理员拥有不同的管理权限。

管理中心主要提供以下能力：

- 用户与角色管理
- AI 模型配置和用量统计
- 消息渠道与模板配置
- 定时执行策略
- 问题反馈
- 审计日志和平台数据管理

详细规则请参阅 [权限说明](docs/权限说明.md)。

## 6. 技术栈

- 前端：Vue 3、Element Plus、Pinia、Vite
- 后端：Python、FastAPI、SQLAlchemy 2.0
- 数据库：MySQL
- 本地启动：Docker Compose

## 7. 相关文档

- [权限说明](docs/权限说明.md)
- [管理中心产品说明](docs/管理中心_产品说明.md)
- [管理中心设计说明](docs/管理中心_设计说明.md)
- [API 测试产品说明](docs/API测试_产品说明.md)
- [API 测试设计说明](docs/API测试_设计说明.md)
- [测试工作台产品说明](docs/测试工作台_产品说明.md)
- [测试工作台设计说明](docs/测试工作台_设计说明.md)
- [API 测试 AI 能力说明](docs/API测试_AI能力说明.md)
- [AI 提示词说明](docs/AI提示词说明.md)
