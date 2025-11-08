import React, { useState } from "react";
import { AppLayout } from "./components/layout";
import {
  AnalysisSummaryCard,
  DetectedRisksList,
  RecommendedContributionsList,
} from "./components/analysis";

function App() {
  const [selectedActions, setSelectedActions] = useState([]);

  const mockData = {
    score: 82,
    stars: 1250,
    forks: 234,
    contributors: 45,
    risks: [
      {
        id: 1,
        type: "security",
        severity: "high",
        description: "보안 취약점 발견",
      },
      {
        id: 2,
        type: "maintenance",
        severity: "medium",
        description: "6개월 이상 업데이트 없음",
      },
    ],
    actions: [
      {
        id: 1,
        title: "의존성 업데이트",
        description: "npm 패키지 업데이트",
        duration: "2시간",
        priority: "high",
      },
      {
        id: 2,
        title: "문서 번역",
        description: "한국어 문서 추가",
        duration: "1시간",
        priority: "medium",
      },
    ],
  };

  const toggleAction = (id) => {
    setSelectedActions((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <AppLayout notification={{ type: "success", message: "테스트 알림!" }}>
      <div className="container mx-auto px-4 py-16">
        <AnalysisSummaryCard
          score={mockData.score}
          stars={mockData.stars}
          forks={mockData.forks}
          contributors={mockData.contributors}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <DetectedRisksList risks={mockData.risks} />
          <RecommendedContributionsList
            actions={mockData.actions}
            selectedActions={selectedActions}
            onToggleAction={toggleAction}
          />
        </div>
      </div>
    </AppLayout>
  );
}

export default App;
