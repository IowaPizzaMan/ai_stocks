import { Route, Routes } from "react-router-dom";
import Navbar from "./components/layout/Navbar";
import Sidebar from "./components/layout/Sidebar";
import Congress from "./pages/Congress";
import EarningsScan from "./pages/EarningsScan";
import InstitutionalFlow from "./pages/InstitutionalFlow";
import Macro from "./pages/Macro";
import News from "./pages/News";
import NotFound from "./pages/NotFound";
import Sectors from "./pages/Sectors";
import StockDetail from "./pages/StockDetail";
import Stocks from "./pages/Stocks";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <Navbar />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6">
          <Routes>
            <Route path="/" element={<Stocks />} />
            <Route path="/news" element={<News />} />
            <Route path="/macro" element={<Macro />} />
            <Route path="/stock/:ticker" element={<StockDetail />} />
            <Route path="/sectors/:sector?" element={<Sectors />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/earnings" element={<EarningsScan />} />
            <Route path="/institutional-flow" element={<InstitutionalFlow />} />
            <Route path="/congress" element={<Congress />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
