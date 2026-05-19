import { motion } from "framer-motion";
import { MovieCard as Movie } from "../types";
import { MovieCard } from "./MovieCard";

export function MovieRow({ title, movies }: { title: string; movies: Movie[] }) {
  if (!movies?.length) return null;
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white md:text-xl">{title}</h2>
        <span className="text-xs text-slate-400">左右拖动滚动条浏览更多</span>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="movie-row-scrollbar flex gap-4 overflow-x-auto pb-3"
      >
        {movies.map((m) => (
          <MovieCard key={`${title}-${m.movieId}`} movie={m} />
        ))}
      </motion.div>
    </section>
  );
}
