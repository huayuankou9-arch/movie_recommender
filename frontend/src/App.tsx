import { Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { AlgorithmLab } from "./pages/AlgorithmLab";
import { Discover } from "./pages/Discover";
import { Evaluation } from "./pages/Evaluation";
import { Home } from "./pages/Home";
import { MovieDetail } from "./pages/MovieDetail";
import { Profile } from "./pages/Profile";
import { SimilarMovies } from "./pages/SimilarMovies";
import { Watchlist } from "./pages/Watchlist";

export default function App() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-[1600px] px-4 pb-20 pt-6 md:px-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/movie/:movieId" element={<MovieDetail />} />
          <Route path="/similar" element={<SimilarMovies />} />
          <Route path="/algorithm-lab" element={<AlgorithmLab />} />
          <Route path="/evaluation" element={<Evaluation />} />
        </Routes>
      </main>
    </div>
  );
}
