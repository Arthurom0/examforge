import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "katex/dist/katex.min.css";
import "./index.css";
import Layout from "./components/Layout";
import Library from "./pages/Library";
import BookletReview from "./pages/BookletReview";
import Exercises from "./pages/Exercises";
import Generate from "./pages/Generate";
import Sets from "./pages/Sets";
import Practice from "./pages/Practice";
import PrintSet from "./pages/PrintSet";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/sets/:id/print" element={<PrintSet />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Library />} />
          <Route path="/booklets/:docId" element={<BookletReview />} />
          <Route path="/exercises" element={<Exercises />} />
          <Route path="/generate" element={<Generate />} />
          <Route path="/sets" element={<Sets />} />
          <Route path="/sets/:id" element={<Practice />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
