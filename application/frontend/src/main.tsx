import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import App from "./App";
import PolicyNewsFeed from "./pages/PolicyNewsFeed";
import PolicyArticlePage from "./pages/PolicyArticlePage";
import QueryPage from "./pages/QueryPage";
import FeedPage from "./pages/FeedPage";
import DetailPage from "./pages/DetailPage";
import { LanguageProvider } from "./contexts/LanguageContext";
import "./index.css";

// The browser starts here. Providers are placed around the router so every
// page can share the selected language and the same URL-based navigation.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <BrowserRouter>
        {/* App supplies the shared header, page area, and footer. */}
        <Routes>
          <Route element={<App />}>
            {/* Each route selects the page shown inside App's Outlet. */}
            <Route index element={<PolicyNewsFeed />} />
            <Route path="/policy/:id" element={<PolicyArticlePage />} />
            <Route path="/query" element={<QueryPage />} />
            <Route path="/debates" element={<FeedPage />} />
            <Route path="/debates/:date" element={<DetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LanguageProvider>
  </React.StrictMode>,
);
