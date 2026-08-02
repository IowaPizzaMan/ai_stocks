import { Route, Routes } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import Sidebar from "./components/layout/Sidebar";
import EarningsScan from "./pages/EarningsScan";
import Feed from "./pages/Feed";
import InstitutionalFlow from "./pages/InstitutionalFlow";
import Sectors from "./pages/Sectors";
import StockDetail from "./pages/StockDetail";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <Navbar />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6">
          <Routes>
            <Route path="/" element={<Feed />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/sectors/:sector?" element={<Sectors />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/earnings" element={<EarningsScan />} />
            <Route path="/institutional-flow" element={<InstitutionalFlow />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
