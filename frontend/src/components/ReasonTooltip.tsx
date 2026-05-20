import { MovieCard } from "../types";

function labelForReason(movie: MovieCard): string {
  if (movie.evidence) return movie.evidence;
  if (movie.reason_type === "item_similarity") return "Because you liked related movies.";
  if (movie.reason_type === "user_similarity") return "Similar users also rated it highly.";
  if (movie.reason_type === "predicted_rating" && typeof movie.score === "number") {
    return `Predicted recommendation score ${movie.score.toFixed(2)}.`;
  }
  if (movie.reason_type === "content_match") return "Genres, tags, and story signals match your profile.";
  if (movie.reason_type === "popularity") return "High ratings and broad audience interest.";
  return movie.reason || "";
}

export function ReasonTooltip({ movie, reason }: { movie?: MovieCard; reason?: string }) {
  const text = movie ? labelForReason(movie) : reason || "";
  if (!text) return null;
  const breakdown = movie?.score_breakdown;
  const title = [
    text,
    breakdown?.rating_avg != null ? `Average rating: ${breakdown.rating_avg}` : "",
    breakdown?.rating_count != null ? `Ratings: ${breakdown.rating_count}` : "",
    breakdown?.recommendation != null ? `Recommendation score: ${breakdown.recommendation.toFixed(2)}` : ""
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <span
      className="line-clamp-2 max-w-full rounded-md border border-neon/30 bg-neon/10 px-2 py-1 text-[11px] leading-4 text-cyan-100"
      title={title}
    >
      {text}
    </span>
  );
}

