import { Outlet, useNavigate, Link } from "react-router-dom";

export default function Layout() {
  const navigate = useNavigate();

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

        <div className="flex items-center gap-4">
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
