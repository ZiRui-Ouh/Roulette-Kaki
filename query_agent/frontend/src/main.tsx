import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import App from "./App";
import QueryPage from "./pages/QueryPage";
import FeedPage from "./pages/FeedPage";
import DetailPage from "./pages/DetailPage";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<QueryPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/debates" element={<FeedPage />} />
          <Route path="/debates/:date" element={<DetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
