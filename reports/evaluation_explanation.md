# Evaluation Explanation

## Why RMSE/MAE are mainly for rating prediction
RMSE and MAE compare predicted explicit ratings against held-out ratings on the 0.5-5.0 scale. They are most meaningful for models that directly predict ratings, especially MatrixFactorization and UserCF. Popularity, ContentBased, and Hybrid often output ranking scores rather than calibrated ratings, so their RMSE/MAE are not emphasized.

## Why Top-N recommendation uses Precision@K, Recall@K, HitRate@K, and NDCG@K
A recommender product is usually judged by whether the top shelf contains relevant items. Precision@K measures concentration of relevant movies, Recall@K measures how much held-out preference is recovered, HitRate@K measures whether at least one positive appears, and NDCG@K rewards placing positives near the top.

## Full-ranking vs sampled-ranking
Full-ranking evaluates recommendations against the whole movie catalog and is strict. Sampled-ranking compares held-out positives against sampled negatives for each user, which is a common way to isolate ranking ability while keeping evaluation practical.

## Why Hybrid improves stability
Hybrid combines popularity, user-neighborhood, item-neighborhood, latent-factor, and content signals. This reduces the chance that one weak signal dominates and usually improves stability across users.

## Current strongest models
- Best rating prediction model: MatrixFactorization
- Best Top-N model under full ranking: MatrixFactorization
- Best Top-N model under sampled ranking: Hybrid
- Best coverage model: ItemCF
