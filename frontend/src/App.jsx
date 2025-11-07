import React from "react";
import { useAnalysisFlow } from "./hooks/useAnalysisFlow";
import { PrimaryButton, LoadingOverlay } from "./components/common";

function App() {
  const { isLoading, analysisResult, startAnalysis } = useAnalysisFlow();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-6">ODOC AI Agent</h1>

        <PrimaryButton onClick={() => startAnalysis("facebook/react")}>
          분석 시작
        </PrimaryButton>

        {analysisResult && (
          <div className="mt-6 p-4 bg-white rounded-xl shadow">
            <p className="text-2xl font-bold">점수: {analysisResult.score}</p>
          </div>
        )}
      </div>

      <LoadingOverlay isVisible={isLoading} />
    </div>
  );
}

export default App;
