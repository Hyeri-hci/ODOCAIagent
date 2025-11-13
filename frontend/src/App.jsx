import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { AppLayout } from "./components/layout";
import { HomePage, AnalyzePage } from "./pages";

function App() {
  const [notification, setNotification] = useState(null);

  return (
    <AppLayout notification={notification}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
