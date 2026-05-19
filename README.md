# 基于协同过滤与内容增强混合推荐的电影流媒体推荐系统

本项目实现了完整闭环：
数据处理 → 多算法训练 → 评估 → FastAPI（可选）→ React 前端展示。

## 1. 项目特点
- 推荐算法：Popularity / UserCF / ItemCF / MF / Content / Hybrid
- 前后端分离：FastAPI + React + Vite
- 支持静态部署：GitHub Pages 纯静态展示（不依赖运行中后端）
- TMDB 仅构建期使用，前端不直接访问 TMDB API

## 2. 数据集

### MovieLens Latest Small / Latest
- 下载：<https://files.grouplens.org/datasets/movielens/ml-latest-small.zip>
- 目录：`data/raw/ml-latest/`（或 `data/raw/ml-latest/ml-latest/`）

### The Movies Dataset
- 下载：<https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset>
- 目录：`data/raw/the-movie-dataset/`（兼容 `data/raw/the-movies-dataset/`）

## 3. 环境变量

复制 `.env.example` 为 `.env`：

```bash
TMDB_READ_ACCESS_TOKEN=your_tmdb_v4_read_access_token_here
TMDB_API_BASE=https://api.themoviedb.org/3
TMDB_IMAGE_BASE=https://image.tmdb.org/t/p
TMDB_POSTER_SIZE=w500
TMDB_BACKDROP_SIZE=original
API_HOST=0.0.0.0
API_PORT=8000
```

如果没有 `TMDB_READ_ACCESS_TOKEN`，流程仍可运行，只是跳过 TMDB 补全。

## 4. 安装

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

## 5. 命令行

### 原有流程
```bash
python main.py preprocess
python main.py train
python main.py evaluate
python main.py all
```

### 新增静态化流程
```bash
python main.py fetch-tmdb
python main.py export-static
python main.py build-static
```

`build-static` 顺序：
1. preprocess
2. train
3. evaluate
4. fetch-tmdb
5. export-static

## 6. 静态数据输出

`python main.py export-static` 会生成：

- `frontend/public/data/movies.json`
- `frontend/public/data/home_cache.json`
- `frontend/public/data/recommendations_cache.json`
- `frontend/public/data/evaluation_results.json`
- `frontend/public/data/search_index.json`

前端静态模式只读取这些 JSON，不会请求 TMDB API。

## 7. 前端运行

### 本地后端模式
```bash
cd frontend
npm run dev
```

设置：
- `VITE_API_MODE=backend`
- `VITE_API_BASE=http://localhost:8000/api`（可选）

### 纯静态模式（GitHub Pages）
- 默认 `VITE_API_MODE=static`
- 从 `/data/*.json` 读取内容

图片规则：
- 使用 `poster_url`
- 缺失或加载失败时回退 `/placeholder-poster.png`

## 8. 后端运行（可选）

```bash
uvicorn backend.app:app --reload --port 8000
```

文档：
- <http://localhost:8000/docs>

## 9. GitHub Pages + TMDB API 的正确使用方式

1. 不要在前端直接调用 TMDB API。  
2. 不要把 API key / token 写入 React 环境变量后打包到前端。  
3. 本项目仅在构建期（本地或 GitHub Actions）调用 TMDB API。  
4. `TMDB_READ_ACCESS_TOKEN` 存放在 GitHub Repository Secrets。  
5. 构建后只生成静态 JSON，网页运行时不需要 API key。  
6. 图片 URL 使用 TMDB image CDN（`image.tmdb.org`），前端无需鉴权。  

### GitHub 设置步骤
1. 申请 TMDB Read Access Token。  
2. GitHub 仓库 `Settings -> Secrets and variables -> Actions`。  
3. 添加 `TMDB_READ_ACCESS_TOKEN`。  
4. 运行 `Deploy GitHub Pages` workflow。  
5. 打开 GitHub Pages 链接查看静态网站。  

## 10. GitHub Actions 部署

已提供：
- `.github/workflows/deploy.yml`

流水线会：
1. 安装 Python/Node 依赖
2. 执行 `python main.py build-static`
3. 前端构建
4. 部署 `frontend/dist` 到 GitHub Pages

## 11. 安全说明
- 不要提交 `.env`
- 不要在 JSON、前端代码、构建产物中写入 token
- 前端 Network 面板应仅看到：
  - `/data/*.json`
  - `https://image.tmdb.org/...` 图片请求

