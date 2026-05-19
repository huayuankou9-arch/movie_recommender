import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { MovieCard as Movie } from "../types";
import { PLACEHOLDER_POSTER, sanitizeBackdropUrl, sanitizePosterUrl, sanitizeTitle } from "../utils/movie";

export function HeroBanner({ movie }: { movie: Movie | null }) {
  if (!movie) return null;

  const title = sanitizeTitle(movie.title) || "Untitled";
  const safeBackdrop = sanitizeBackdropUrl(movie.backdrop_url);
  const safePoster = sanitizePosterUrl(movie.poster_url);
  const initialBg = safeBackdrop || safePoster || "";
  const [bgSrc, setBgSrc] = useState(initialBg);
  const [bgFailed, setBgFailed] = useState(false);

  useEffect(() => {
    setBgSrc(initialBg);
    setBgFailed(false);
  }, [movie.movieId, initialBg]);

  const hasBackdrop = Boolean(safeBackdrop);
  const hasPoster = Boolean(safePoster && safePoster !== PLACEHOLDER_POSTER);
  const reason = movie.reason || "综合相似用户、相似电影和内容特征推荐";
  const scoreText = typeof movie.score === "number" ? movie.score.toFixed(2) : "N/A";

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-panel"
    >
      {bgSrc ? (
        <img
          src={bgSrc}
          alt={title}
          className={`h-[300px] w-full object-cover md:h-[440px] ${!hasBackdrop && hasPoster ? "scale-110 blur-sm" : ""}`}
          onError={() => {
            if (bgFailed) return;
            setBgFailed(true);
            if (bgSrc !== safePoster && safePoster && safePoster !== PLACEHOLDER_POSTER) {
              setBgSrc(safePoster);
              return;
            }
            setBgSrc("");
          }}
        />
      ) : (
        <div className="h-[300px] w-full bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 md:h-[440px]" />
      )}
      <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/45 to-transparent" />
      <div className="absolute bottom-0 left-0 max-w-2xl space-y-3 p-5 md:p-8">
        <p className="inline-flex rounded-full bg-neon/20 px-3 py-1 text-xs text-neon">Top Pick For You</p>
        <h1 className="text-3xl font-bold md:text-5xl">{title}</h1>
        <p className="text-sm text-slate-200 md:text-base">
          {movie.year || "Unknown Year"} - {movie.genres || "Unknown Genre"}
        </p>
        <p className="line-clamp-3 text-sm text-slate-200 md:text-base">{movie.overview || "No overview available."}</p>
        <p className="text-sm text-cyan-200">推荐理由：{reason}</p>
        <p className="text-xs text-gold/90">黄色分数表示推荐模型分（越高越可能喜欢），当前：{scoreText}</p>
        <div className="flex gap-3">
          <Link to={`/movie/${movie.movieId}`} className="rounded-md bg-neon px-4 py-2 text-sm font-semibold text-ink">
            View Detail
          </Link>
          <Link to={`/similar?movieId=${movie.movieId}`} className="rounded-md border border-white/30 px-4 py-2 text-sm text-white">
            Similar Movies
          </Link>
        </div>
      </div>
    </motion.section>
  );
}

