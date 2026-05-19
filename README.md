# 基于协同过滤与内容增强混合推荐的电影流媒体推荐系统

一个接近产品形态的电影推荐课程设计项目，覆盖完整闭环：

数据处理 → 多算法训练 → 评估对比 → FastAPI 服务 → React 流媒体前端展示。

## 1. 项目简介

本项目实现了 Netflix-like / 豆瓣-like 风格的电影推荐平台，支持：

- 热门推荐（Popularity）
- 用户协同过滤（UserCF）
- 物品协同过滤（ItemCF）
- 矩阵分解（MF/SVD）
- 内容推荐（Content-based）
- 混合推荐（Hybrid）

并提供：

- 首页推荐流
- 电影详情页
- 相似电影页
- 用户画像页
- 冷启动 Discover 页
- 算法实验页（权重调节）
- 评估可视化页

## 2. 系统截图占位

请将项目运行截图放到 `reports/figures/`，可在此引用：

- 首页：`reports/figures/home.png`
- 详情页：`reports/figures/detail.png`
- 算法实验页：`reports/figures/lab.png`
- 评估页：`reports/figures/evaluation.png`

## 3. 数据集下载链接

### 3.1 MovieLens Latest Small

- 下载链接：<https://files.grouplens.org/datasets/movielens/ml-latest-small.zip>

解压后放置到：

`data/raw/ml-latest/`

需要文件：

- `ratings.csv`
- `movies.csv`
- `tags.csv`
- `links.csv`

### 3.2 The Movies Dataset

- Kaggle 页面：<https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset>
- 下载命令：

```bash
kaggle datasets download -d rounakbanik/the-movies-dataset
```

解压后放置到：

`data/raw/the-movies-dataset/`

需要文件：

- `movies_metadata.csv`
- `keywords.csv`
- `credits.csv`
- `links_small.csv`

## 4. 数据放置方式

```
data/
  raw/
    ml-latest/
      ratings.csv
      movies.csv
      tags.csv
      links.csv
    the-movies-dataset/
      movies_metadata.csv
      keywords.csv
      credits.csv
      links_small.csv
```

## 5. 环境安装

```bash
pip install -r requirements.txt
```

可选配置 TMDB（非必需）：

复制 `.env.example` 为 `.env`，填写：

- `TMDB_API_KEY`
- `TMDB_API_READ_TOKEN`

未填写时系统仍可运行，会使用本地元数据和占位图。

## 6. 后端运行

```bash
python main.py all
uvicorn backend.app:app --reload --port 8000
```

文档地址：

- Swagger: <http://localhost:8000/docs>

## 7. 前端运行

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- <http://localhost:5173>

## 8. 完整训练流程

可单步执行：

```bash
python main.py preprocess
python main.py train
python main.py evaluate
```

或一键执行：

```bash
python main.py all
```

`all` 包含：

1. 预处理与合并
2. 模型训练与保存
3. 指标评估与画图
4. 缓存生成

## 9. 算法说明

- `PopularityRecommender`：
  - `score(i)=0.6*avg_norm+0.4*log_count_norm`
  - 输出 `trending` 与 `highly_rated`
- `UserCFRecommender`：
  - 用户余弦相似度邻域预测
- `ItemCFRecommender`：
  - 物品余弦相似邻域聚合
  - 支持 `similar_movies`
- `MatrixFactorizationRecommender`：
  - 优先 `surprise.SVD`
  - 不可用时回退到自实现 biased MF(SGD)
- `ContentBasedRecommender`：
  - `metadata_text` + TF-IDF
  - 支持 `similar_movies` 与 `discover_by_preferences`
- `HybridRecommender`：
  - 多模型召回 + min-max 归一化加权重排
  - 权重来自 `config.yaml`

## 10. 评估指标说明

已实现并输出：

- RMSE
- MAE
- Precision@10
- Recall@10
- HitRate@10
- NDCG@10
- Coverage

输出位置：

- 表格：`reports/tables/evaluation_results.csv`
- 图像：`reports/figures/metrics_comparison.png`

## 11. 前端页面说明

- `Home`：Hero + For You + Trending + Highly Rated + Genre Rows
- `Discover`：类型/关键词/年份冷启动推荐
- `Profile`：用户画像与偏好图表
- `MovieDetail`：详情 + 相似电影
- `SimilarMovies`：按算法查相似
- `AlgorithmLab`：同屏对比六种算法 + Hybrid 权重调节
- `Evaluation`：指标表格 + Recharts 图表

## 12. API 概览

- `GET /api/home?user_id=1`
- `GET /api/recommend/{user_id}?model=hybrid&top_k=12`
- `GET /api/users/{user_id}/profile`
- `GET /api/movies/{movie_id}`
- `GET /api/movies/{movie_id}/similar?method=hybrid&top_k=12`
- `GET /api/discover?genres=Action,Drama&keywords=space,love&year_min=2000&year_max=2020&top_k=12`
- `GET /api/search?q=toy+story`
- `GET /api/evaluation`
- `GET /api/algorithm-lab?user_id=1&top_k=12&popularity=0.1&usercf=0.2&itemcf=0.25&mf=0.3&content=0.15`

## 13. 输出与缓存

模型输出：

- `data/outputs/models/popularity.pkl`
- `data/outputs/models/usercf.pkl`
- `data/outputs/models/itemcf.pkl`
- `data/outputs/models/mf.pkl`
- `data/outputs/models/content.pkl`
- `data/outputs/models/hybrid.pkl`

缓存输出：

- `data/outputs/cache/home_cache.json`
- `data/outputs/cache/popular_movies.json`
- `data/outputs/cache/evaluation_results.json`

## 14. 常见问题

1. `surprise` 安装失败怎么办？

- 项目已内置回退方案，会自动使用自实现 MF。

2. The Movies Dataset 缺失时能运行吗？

- 可以，系统会降级为 MovieLens-only 元数据模式（推荐仍可运行）。

3. 没有 TMDB API key 能跑吗？

- 可以，使用本地元数据和占位图，不强制外部 API。

4. 前端看不到数据？

- 先执行 `python main.py all`，再启动 `uvicorn` 和 `npm run dev`。
