# Evaluation Explanation

## Algorithm roles
- Popularity: a non-personalized baseline for cold start and trending shelves.
- UserCF: user-neighborhood collaborative filtering, useful when similar users have overlapping history.
- ItemCF: item-neighborhood collaborative filtering, strong for explainable recommendations such as "Because you liked ...".
- MatrixFactorization / SVD: rating prediction model that captures latent user and movie factors.
- ContentBased: semantic matching from genres, tags, keywords, cast, director, and overview; best suited for cold start, Discover, and Similar Movies.
- Hybrid: blends all signals to improve ranking stability and product usefulness.

## Metrics
Precision@K measures how many of the top K recommendations are positive. Recall@K measures how many held-out positives are recovered. HitRate@K checks whether at least one positive appears. NDCG@K rewards placing positives near the top. Coverage measures catalog breadth. RMSE/MAE measure explicit rating prediction error and are mainly meaningful for MF/UserCF/ItemCF.

## Full-ranking vs sampled-ranking
Full-ranking evaluates recommendations from the full catalog, so it is strict and closer to a production retrieval task. Random sampled-ranking compares positives against random unseen negatives and is easier. Popularity-aware sampled-ranking samples negatives from similar popularity buckets, making the task harder and reducing the unfair advantage of simple popularity.

## Why Hybrid is the comprehensive model
Hybrid normalizes each model's score per user and combines popularity, UserCF, ItemCF, MF, and content evidence. This helps it stay strong when one individual signal is weak while preserving explanations through score_breakdown and reason_type.

## Popularity and ContentBased interpretation
Popularity can achieve high recall when held-out positives are mainstream, but it has weak personalization and often low coverage. ContentBased may not dominate full-ranking metrics, but it is important for cold-start discovery, semantic similar-movie pages, and explanation quality.

## Current strongest models
- Best rating prediction model: MatrixFactorization
- Best full-ranking model: Popularity
- Best random sampled-ranking model: Hybrid
- Best popularity-aware sampled-ranking model: ItemCF
- Best coverage model: ItemCF
