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

## Why there are three ranking evaluations
Full-ranking asks a model to find the user's future high-rated movies from the entire movie catalog. This is the strictest setup, so Precision@10, Recall@10, and NDCG@10 are naturally low: the model has thousands of plausible candidates and only a few held-out positives.

Random sampled-ranking builds a smaller candidate set from held-out positives plus random unseen negatives. Scores are usually higher because many random negatives are obscure or weakly related to the user.

Popularity-aware sampled-ranking is stricter than random sampled-ranking. It samples negatives from similar or harder popularity buckets, so a Popularity model cannot win only by ranking globally popular movies above obscure negatives. This setting better tests personalized ranking ability.

## Why MF/SVD is strong for rating prediction
MF/SVD directly optimizes explicit rating prediction, so RMSE and MAE are the right metrics for it. In the current run, the best rating prediction model is MatrixFactorization.

## Why ItemCF is strong for explainable recommendation
ItemCF supports source-movie explanations such as "Because you liked ...". It also tends to produce broader catalog exposure, which is why it is often a strong coverage and interpretability baseline.

## Why Hybrid is the comprehensive framework
Hybrid normalizes each model's score per user and combines popularity, UserCF, ItemCF, MF, and content evidence. It is a fusion framework rather than a guarantee of winning every metric. Hybrid can be strongest under one evaluation, while stricter popularity-aware evaluation may favor ItemCF or another specialized model. This is useful in a course defense because it shows the complementary strengths of different recommenders.

## Popularity and ContentBased interpretation
Popularity can achieve high recall when held-out positives are mainstream, but it has weak personalization and often low coverage. ContentBased may not dominate full-ranking metrics, but it is important for cold-start discovery, semantic similar-movie pages, and explanation quality.

## Current strongest models
- Best rating prediction model: MatrixFactorization
- Best full-ranking model: Popularity
- Best random sampled-ranking model: Hybrid
- Best popularity-aware sampled-ranking model: ItemCF
- Best coverage model: ItemCF (full_ranking)
- Best interpretable model: ItemCF
- Best cold-start models: Popularity / ContentBased
