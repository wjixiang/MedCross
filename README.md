# MedCross

医学交叉研究工具集，提供 GWAS 遗传分析、医学影像获取、放射组学和机器学习等方向的 CLI 工具和 SDK 库。

## 项目结构

```
MedCross/
├── libs/                          # 可复用库
│   ├── gwas-client/               # IEU OpenGWAS API 客户端 SDK
│   └── rediomics/                 # 放射组学库（开发中）
│
├── apps/                          # CLI 应用
│   ├── opengwas-cli/              # GWAS 数据查询与分析 CLI
│   ├── tcia-cli/                  # TCIA 医学影像数据获取 CLI
│   ├── ml/                        # 机器学习应用（开发中）
│   └── radiomics/                 # 放射组学应用（开发中）
│
├── pyproject.toml                 # Workspace 配置
├── uv.lock                        # 依赖锁定文件
└── .python-version                # Python 版本
```

## 环境要求

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/)（包管理器）

## 快速开始

```bash
# 安装所有依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

## CLI 工具

### opengwas — GWAS 数据查询与分析

基于 [IEU OpenGWAS 数据库](https://api.opengwas.io) 的命令行工具，支持数据集查询、变异关联分析、PheWAS、LD 操作等。

```bash
# 查看帮助
uv run --package opengwas-cli opengwas --help

# 检查 API 状态
uv run --package opengwas-cli opengwas status check

# 列出 GWAS 数据集（支持过滤）
uv run --package opengwas-cli opengwas info list --trait cholesterol --limit 10

# 查看数据集详情和下载链接
uv run --package opengwas-cli opengwas info show ieu-a-2
uv run --package opengwas-cli opengwas info files ieu-a-2

# 查询变异关联
uv run --package opengwas-cli opengwas assoc query rs1205 --study ieu-a-2

# 提取显著位点
uv run --package opengwas-cli opengwas tophits extract ieu-a-2 --pval 1e-5

# 全表型关联扫描
uv run --package opengwas-cli opengwas phewas run rs1205 --limit 10

# 变异信息查询
uv run --package opengwas-cli opengwas variants rsid rs1205 rs234
uv run --package opengwas-cli opengwas variants gene 1017 --limit 5

# LD 操作
uv run --package opengwas-cli opengwas ld matrix rs1205 rs234
uv run --package opengwas-cli opengwas ld clump rs1205 rs234 -p 1e-8 1e-5
```

所有命令支持 `--json` 输出和 `--limit/-n` 行数限制。

### tcia — TCIA 医学影像数据获取

从 [The Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net) 查询和下载医学影像数据。

```bash
# 查看帮助
uv run --package tcia-cli tcia --help

# 列出可用数据集
uv run --package tcia-cli tcia collections list

# 搜索数据集
uv run --package tcia-cli tcia search
```

## 库

### gwas-client

IEU OpenGWAS REST API 的 Python SDK，覆盖全部 30 个 API 端点。

```python
from gwas_client import OpenGWAS_API_Client

with OpenGWAS_API_Client(token="your-jwt-token") as client:
    # 查询数据集元数据
    info = client.get_gwas_info(["ieu-a-2", "ieu-a-7"])

    # 查询变异关联
    assoc = client.get_associations(
        variant=["rs1205"],
        id=["ieu-a-2"],
        proxies=1,
        population="EUR",
    )

    # LD clumping
    result = client.ld_clump(
        rsid=["rs1205", "rs234"],
        pval=[1e-8, 1e-5],
        pop="EUR",
    )
```

Token 可在 https://api.opengwas.io 注册获取。

## 开发

```bash
# 同步依赖（修改 pyproject.toml 后）
uv sync

# 运行测试
uv run pytest
```

## 许可证

MIT
