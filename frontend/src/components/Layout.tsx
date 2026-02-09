import { Outlet, useNavigate, Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { endpoints } from "../config";


export default function Layout() {
  const navigate = useNavigate();
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/login");
      return;
    }

    // Fetch credits
    const fetchCredits = async () => {
      try {
        const response = await fetch(endpoints.profile, {
          headers: { Authorization: `Token ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setCredits(data.credits);
        }
      } catch (error) {
        console.error("Error fetching usage:", error);
      }
    };

    fetchCredits();
    // Poll every 10 seconds to keep credits updated
    const interval = setInterval(fetchCredits, 10000);

    return () => clearInterval(interval);
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_id");
    navigate("/login");
  };

  return (
    <div className="h-screen bg-white text-black flex flex-col">
      {/* Header */}
      <header className="h-16 border-b border-black flex items-center justify-between px-6 bg-white z-10">
        <div className="flex items-center gap-8">
          <h1 className="text-xl font-bold tracking-tight">Chatbot App</h1>
          <nav className="hidden md:flex gap-6 text-sm font-medium">
            <Link to="/" className="hover:text-gray-600">
              Documents
            </Link>
            <Link to="/chat" className="hover:text-gray-600">
              Chatbot
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-6">
          {credits !== null && (
            <div className="bg-gray-100 px-3 py-1 rounded-full border border-gray-200 text-sm font-medium flex items-center gap-2" title="Remaining Credits">
              <span className="text-gray-500 text-xs">Credits:</span>
              <span className={`${credits < 20 ? 'text-red-600' : 'text-gray-900'}`}>
                {credits.toFixed(2)}
              </span>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="text-sm font-medium hover:text-red-600"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex flex-1 relative overflow-hidden">
        {/* Page Content */}
        <main className="flex-1 overflow-hidden bg-white flex flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
